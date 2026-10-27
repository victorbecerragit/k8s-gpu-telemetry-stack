"""Dashboard and alert-rule consistency tests.

The dashboard and the PrometheusRule must query the same series names the
gadget actually exports. These tests catch the class of bug where a panel or
alert silently queries a metric that nothing emits.
"""

from __future__ import annotations

import re

import pytest
import yaml

from conftest import PROMETHEUS_RULE, find_docs

# Series the stack is expected to produce.
DCGM_METRICS = {
    "DCGM_FI_DEV_GPU_UTIL",
    "DCGM_FI_DEV_FB_USED",
    "DCGM_FI_DEV_FB_FREE",
    "DCGM_FI_DEV_GPU_TEMP",
    "DCGM_FI_DEV_PCIE_TX_THROUGHPUT",
    "DCGM_FI_DEV_PCIE_RX_THROUGHPUT",
    "DCGM_FI_DEV_XID_ERRORS",
}

# The OTel Prometheus exporter names the histogram after the field (`latency`)
# and scopes it with otel_scope_name set to the configured metrics name.
EBPF_SERIES = "latency_bucket"
EBPF_SCOPE = "gadget_tcp_latency_us"


def _all_exprs(dashboard: dict) -> list[str]:
    exprs = []
    for panel in dashboard.get("panels", []):
        for target in panel.get("targets", []):
            expr = target.get("expr")
            if expr:
                exprs.append(expr)
    return exprs


def test_dashboard_is_valid_json_with_uid(dashboard):
    assert dashboard.get("uid") == "gpu-telemetry-fleet"
    assert dashboard.get("title")


def test_dashboard_panels_have_unique_ids(dashboard):
    ids = [p["id"] for p in dashboard["panels"]]
    assert len(ids) == len(set(ids)), "duplicate panel ids"


def test_dashboard_queries_only_known_series(dashboard):
    """Every metric referenced must be one the stack actually emits."""
    known = DCGM_METRICS | {EBPF_SERIES}
    for expr in _all_exprs(dashboard):
        for name in re.findall(r"\b([A-Za-z_:][A-Za-z0-9_:]*)\{", expr):
            if name.startswith(("DCGM_", "latency_", "gadget_")):
                assert name in known, f"dashboard queries unknown series {name}"


def test_dashboard_does_not_query_legacy_gadget_metric(dashboard):
    """Regression guard: the old inert metric name must be gone."""
    for expr in _all_exprs(dashboard):
        assert "gadget_tcp_latency_us_bucket" not in expr, (
            "dashboard still queries the legacy metric that no gadget emits"
        )


def test_dashboard_network_panel_uses_otel_scope(dashboard):
    network = [p for p in dashboard["panels"] if p.get("id") == 9]
    assert network, "network latency panel missing"
    exprs = [t["expr"] for t in network[0]["targets"]]
    assert exprs, "network panel has no queries"
    for expr in exprs:
        assert EBPF_SERIES in expr
        assert f'otel_scope_name="{EBPF_SCOPE}"' in expr


def test_dashboard_has_fleet_and_per_gpu_rows(dashboard):
    titles = {p.get("title") for p in dashboard["panels"]}
    assert "GPU Fleet Overview" in titles
    assert "Per-GPU Detail" in titles
    assert "Network Latency (eBPF)" in titles


def test_dashboard_uses_cluster_template_variable(dashboard):
    names = {v["name"] for v in dashboard["templating"]["list"]}
    assert "cluster" in names
    assert "datasource" in names


def _gpu_rule_group(rendered: list[dict]) -> dict:
    rules = [
        d
        for d in rendered
        if d.get("kind") == "PrometheusRule" and "gpu-alerts" in d["metadata"]["name"]
    ]
    assert rules, "GPU PrometheusRule not rendered"
    groups = {g["name"]: g for g in rules[0]["spec"]["groups"]}
    return groups


def test_all_expected_alerts_present(base_render):
    groups = _gpu_rule_group(base_render)
    alerts = {r["alert"] for g in groups.values() for r in g["rules"] if "alert" in r}
    assert alerts == {
        "GpuXidError",
        "GpuThermalThrottling",
        "GpuVramExhaustion",
        "GpuNotReporting",
        "GpuPodTcpLatencyHigh",
    }


def test_alerts_have_severity_and_runbook_context(base_render):
    groups = _gpu_rule_group(base_render)
    for group in groups.values():
        for rule in group["rules"]:
            if "alert" not in rule:
                continue
            assert rule["labels"]["severity"] in {"critical", "warning"}
            assert rule["annotations"]["summary"]
            assert rule["annotations"]["description"]


def test_network_alert_uses_exported_series(base_render):
    groups = _gpu_rule_group(base_render)
    rule = next(
        r for r in groups["gpu.network"]["rules"] if r.get("alert") == "GpuPodTcpLatencyHigh"
    )
    expr = " ".join(rule["expr"].split())
    assert EBPF_SERIES in expr
    assert f'otel_scope_name="{EBPF_SCOPE}"' in expr
    assert "gadget_tcp_latency_us_bucket" not in expr


def test_thresholds_are_configurable(helm):
    """Overriding thresholds must change the rendered expressions."""
    import subprocess

    from conftest import CHART_DIR

    proc = subprocess.run(
        [
            helm,
            "template",
            "gpu-telemetry",
            str(CHART_DIR),
            "-f",
            str(CHART_DIR / "values.yaml"),
            "--set",
            "prometheus.rules.thresholds.temperatureCelsius=70",
            "--set",
            "prometheus.rules.thresholds.vramPercent=80",
            "--set",
            "prometheus.rules.thresholds.tcpLatencyMicros=1234",
        ],
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert proc.returncode == 0, proc.stderr
    docs = [d for d in yaml.safe_load_all(proc.stdout) if d]
    groups = _gpu_rule_group(docs)
    exprs = " ".join(
        " ".join(r["expr"].split()) for g in groups.values() for r in g["rules"]
    )
    assert "> 70" in exprs
    assert "> 80" in exprs
    assert "> 1234" in exprs


def test_prometheusrule_template_contains_all_alerts():
    """The template source must define every alert the README documents."""
    raw = PROMETHEUS_RULE.read_text()
    for alert in (
        "GpuXidError",
        "GpuThermalThrottling",
        "GpuVramExhaustion",
        "GpuNotReporting",
        "GpuPodTcpLatencyHigh",
    ):
        assert f"alert: {alert}" in raw, f"{alert} missing from template source"
