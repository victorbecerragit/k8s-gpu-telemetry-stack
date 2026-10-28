"""Chart rendering tests: structure, GKE overlay, and eBPF metrics wiring."""

from __future__ import annotations

import pytest

from conftest import find_docs


def test_base_render_has_expected_kinds(base_render):
    kinds = {d["kind"] for d in base_render}
    for expected in (
        "DaemonSet",
        "Deployment",
        "Service",
        "ServiceMonitor",
        "PrometheusRule",
        "ConfigMap",
    ):
        assert expected in kinds, f"missing {expected} in base render"


def test_dcgm_daemonset_uses_expected_field_ids(base_render):
    ds = find_docs(base_render, "DaemonSet", "dcgm")
    assert ds, "DCGM DaemonSet not rendered"
    container = ds[0]["spec"]["template"]["spec"]["containers"][0]
    env = {e["name"]: e.get("value") for e in container.get("env", [])}
    field_ids = env.get("DCGM_EXPORTER_FIELD_IDS", "")
    # SM util, mem-copy, FB free/used, PCIe TX/RX, temp, XID
    for fid in ("203", "204", "251", "252", "100", "101", "150", "230"):
        assert fid in field_ids.split(","), f"DCGM field id {fid} missing"


def test_dcgm_servicemonitor_targets_metrics_port(base_render):
    sm = find_docs(base_render, "ServiceMonitor", "dcgm")
    assert sm, "DCGM ServiceMonitor not rendered"
    endpoints = sm[0]["spec"]["endpoints"]
    assert any(e.get("port") == "metrics" for e in endpoints)


def test_ebpf_daemonset_runs_tcprtt_gadget(base_render):
    ds = find_docs(base_render, "DaemonSet", "ebpf")
    assert ds, "eBPF DaemonSet not rendered"
    container = ds[0]["spec"]["template"]["spec"]["containers"][0]
    args = " ".join(container.get("args", []))
    assert "profile_tcprtt" in args, "must use profile_tcprtt for RTT histograms"
    assert "trace_tcp" not in args, "trace_tcp emits events, not latency"


def test_ebpf_gadget_exports_metrics_with_matching_name(base_render):
    ds = find_docs(base_render, "DaemonSet", "ebpf")
    container = ds[0]["spec"]["template"]["spec"]["containers"][0]
    args = " ".join(container.get("args", []))
    # The datasource is `tcprtt`; both the annotation and the name mapping must
    # use it, otherwise the OTel operator silently exports nothing.
    assert "tcprtt:metrics.collect=true" in args
    assert "tcprtt:gadget_tcp_latency_us" in args
    assert "--otel-metrics-listen" in args


def test_ebpf_exposes_metrics_port_and_probes(base_render):
    ds = find_docs(base_render, "DaemonSet", "ebpf")
    container = ds[0]["spec"]["template"]["spec"]["containers"][0]
    ports = {p["name"]: p["containerPort"] for p in container.get("ports", [])}
    assert ports.get("metrics") == 2224
    assert container.get("readinessProbe", {}).get("httpGet", {}).get("path") == "/metrics"


def test_ebpf_uses_the_ig_cli_image_not_the_daemon_image(base_render):
    """`inspektor-gadget` is the daemon image and has no `ig` binary.

    Using it produces `exec: "ig": executable file not found in $PATH` at
    container start, which surfaces as CrashLoopBackOff.
    """
    ds = find_docs(base_render, "DaemonSet", "ebpf")
    image = ds[0]["spec"]["template"]["spec"]["containers"][0]["image"]
    assert image.startswith("ghcr.io/inspektor-gadget/ig:"), (
        f"expected the ig CLI image, got {image}"
    )
    assert not image.startswith("ghcr.io/inspektor-gadget/inspektor-gadget:")


def test_ebpf_image_tag_is_pinned(base_render):
    """`latest` drifts silently and defeats reproducibility."""
    ds = find_docs(base_render, "DaemonSet", "ebpf")
    image = ds[0]["spec"]["template"]["spec"]["containers"][0]["image"]
    tag = image.rsplit(":", 1)[-1]
    assert tag != "latest", "pin the gadget image tag"
    assert tag.startswith("v"), f"expected a version tag, got {tag}"


def test_ebpf_does_not_wrap_command_in_a_shell(base_render):
    """The ig image is distroless — there is no /bin/sh to exec."""
    ds = find_docs(base_render, "DaemonSet", "ebpf")
    container = ds[0]["spec"]["template"]["spec"]["containers"][0]
    command = container.get("command", [])
    assert command, "container must set an explicit command"
    assert command[0] == "ig", f"expected `ig` as entrypoint, got {command}"
    assert "/bin/sh" not in command, "the ig image has no /bin/sh"
    assert "sh" not in command


def test_ebpf_liveness_probe_avoids_shell(base_render):
    ds = find_docs(base_render, "DaemonSet", "ebpf")
    container = ds[0]["spec"]["template"]["spec"]["containers"][0]
    probe = container.get("livenessProbe", {})
    cmd = probe.get("exec", {}).get("command", [])
    assert cmd, "liveness probe must be defined"
    assert "/bin/sh" not in cmd, "distroless image has no shell for `test -x`"
    assert cmd[0] == "ig"


def test_ebpf_service_and_servicemonitor_rendered(base_render):
    svc = find_docs(base_render, "Service", "ebpf")
    assert svc, "eBPF metrics Service not rendered"
    assert svc[0]["spec"]["ports"][0]["name"] == "metrics"

    sm = find_docs(base_render, "ServiceMonitor", "ebpf")
    assert sm, "eBPF ServiceMonitor not rendered"
    assert sm[0]["spec"]["endpoints"][0]["port"] == "metrics"


def test_gke_overlay_disables_gpu_operator(gke_render):
    # GKE manages the NVIDIA driver + device plugin itself.
    assert not find_docs(gke_render, "Deployment", "gpu-operator"), (
        "GPU Operator must be disabled on GKE to avoid a duplicate device plugin"
    )


def test_gke_overlay_tolerates_gpu_taint(gke_render):
    ds = find_docs(gke_render, "DaemonSet", "dcgm")
    assert ds, "DCGM DaemonSet missing in GKE render"
    tolerations = ds[0]["spec"]["template"]["spec"]["tolerations"]
    assert any(t.get("key") == "nvidia.com/gpu" for t in tolerations)


def test_gke_overlay_pins_dcgm_to_gpu_pool(gke_render):
    ds = find_docs(gke_render, "DaemonSet", "dcgm")
    selector = ds[0]["spec"]["template"]["spec"].get("nodeSelector", {})
    assert selector.get("workload") == "gpu-telemetry"


def test_eks_overlay_keeps_gpu_operator(eks_render):
    # The operator chart renders its controller as a Deployment; the GPU
    # DaemonSets it owns are created at runtime by the operator itself.
    assert find_docs(eks_render, "Deployment", "gpu-operator"), (
        "EKS relies on the GPU Operator for drivers"
    )


@pytest.mark.parametrize("overlay", ["values-gke.yaml", "values-eks.yaml", "values-dev.yaml"])
def test_overlays_render_without_error(helm, overlay):
    from conftest import CHART_DIR, render_chart

    docs = render_chart(helm, str(CHART_DIR / "values.yaml"), str(CHART_DIR / overlay))
    assert len(docs) > 50, f"{overlay} produced suspiciously few resources"
