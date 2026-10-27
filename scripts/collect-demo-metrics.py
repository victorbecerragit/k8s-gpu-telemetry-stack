#!/usr/bin/env python3
"""Collect a GPU telemetry snapshot from Prometheus for the demo.

Queries the same PromQL expressions the Grafana dashboard uses, so the rendered
charts in the README reflect exactly what an operator sees in Grafana.

Usage:
    python3 scripts/collect-demo-metrics.py \
        --prometheus-url http://localhost:9090 \
        --cluster gpu-telemetry-demo \
        --output demo/snapshots/snapshot.json
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

# (key, title, unit, promql) — mirrors the dashboard panels.
RANGE_QUERIES: list[tuple[str, str, str, str]] = [
    (
        "sm_utilization",
        "SM Utilization per GPU",
        "%",
        'DCGM_FI_DEV_GPU_UTIL{cluster="$cluster"}',
    ),
    (
        "vram_used",
        "VRAM Used per GPU",
        "MiB",
        'DCGM_FI_DEV_FB_USED{cluster="$cluster"}',
    ),
    (
        "gpu_temperature",
        "GPU Temperature per GPU",
        "°C",
        'DCGM_FI_DEV_GPU_TEMP{cluster="$cluster"}',
    ),
    (
        "pcie_tx",
        "PCIe TX Throughput per GPU",
        "MB/s",
        'DCGM_FI_DEV_PCIE_TX_THROUGHPUT{cluster="$cluster"}',
    ),
    (
        "pcie_rx",
        "PCIe RX Throughput per GPU",
        "MB/s",
        'DCGM_FI_DEV_PCIE_RX_THROUGHPUT{cluster="$cluster"}',
    ),
    (
        "tcp_rtt_p99",
        "TCP Round-Trip Latency p99 (eBPF)",
        "µs",
        'histogram_quantile(0.99, sum(rate('
        'latency_bucket{otel_scope_name="gadget_tcp_latency_us", '
        'cluster="$cluster"}[5m])) by (le))',
    ),
    (
        "tcp_rtt_p50",
        "TCP Round-Trip Latency p50 (eBPF)",
        "µs",
        'histogram_quantile(0.50, sum(rate('
        'latency_bucket{otel_scope_name="gadget_tcp_latency_us", '
        'cluster="$cluster"}[5m])) by (le))',
    ),
]

INSTANT_QUERIES: list[tuple[str, str, str, str]] = [
    (
        "avg_sm_utilization",
        "Average SM Utilization",
        "%",
        'avg(DCGM_FI_DEV_GPU_UTIL{cluster="$cluster"})',
    ),
    (
        "vram_utilization",
        "VRAM Utilization",
        "%",
        '100 * sum(DCGM_FI_DEV_FB_USED{cluster="$cluster"}) / '
        'clamp_min(sum(DCGM_FI_DEV_FB_USED{cluster="$cluster"} + '
        'DCGM_FI_DEV_FB_FREE{cluster="$cluster"}), 1)',
    ),
    (
        "max_temperature",
        "Max GPU Temperature",
        "°C",
        'max(DCGM_FI_DEV_GPU_TEMP{cluster="$cluster"})',
    ),
    (
        "xid_errors_1h",
        "GPU XID Errors (1h)",
        "count",
        'sum(increase(DCGM_FI_DEV_XID_ERRORS{cluster="$cluster"}[1h]))',
    ),
]


def prom_query(base_url: str, expr: str, timeout: int = 30) -> dict[str, Any]:
    """Run an instant PromQL query."""
    params = urllib.parse.urlencode({"query": expr})
    url = f"{base_url.rstrip('/')}/api/v1/query?{params}"
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.load(resp)


def prom_query_range(
    base_url: str, expr: str, step: str = "30s", timeout: int = 60
) -> dict[str, Any]:
    """Run a range PromQL query over the last hour."""
    end = datetime.now(timezone.utc)
    start = end.timestamp() - 3600
    params = urllib.parse.urlencode(
        {"query": expr, "start": f"{start:.0f}", "end": f"{end.timestamp():.0f}", "step": step}
    )
    url = f"{base_url.rstrip('/')}/api/v1/query_range?{params}"
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.load(resp)


def series_from_range(result: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten a Prometheus range result into labelled series."""
    out = []
    for item in result.get("data", {}).get("result", []):
        metric = item.get("metric", {})
        label = (
            metric.get("gpu")
            or metric.get("GPU_I_ID")
            or metric.get("instance")
            or metric.get("Hostname")
            or "value"
        )
        points = [
            {"t": float(ts), "v": float(val)}
            for ts, val in item.get("values", [])
            if val not in ("NaN", "+Inf", "-Inf")
        ]
        if points:
            out.append({"label": label, "points": points})
    return out


def scalar_from_instant(result: dict[str, Any]) -> float | None:
    """Extract a single scalar from an instant query result."""
    items = result.get("data", {}).get("result", [])
    if not items:
        return None
    value = items[0].get("value")
    if not value:
        return None
    try:
        return float(value[1])
    except (TypeError, ValueError):
        return None


def collect(base_url: str, cluster: str) -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cluster": cluster,
        "source": base_url,
        "summary": {},
        "series": {},
        "errors": [],
    }

    for key, title, unit, expr in INSTANT_QUERIES:
        query = expr.replace("$cluster", cluster)
        try:
            value = scalar_from_instant(prom_query(base_url, query))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            snapshot["errors"].append(f"{key}: {exc}")
            value = None
        snapshot["summary"][key] = {"title": title, "unit": unit, "value": value}

    for key, title, unit, expr in RANGE_QUERIES:
        query = expr.replace("$cluster", cluster)
        try:
            result = prom_query_range(base_url, query)
            series = series_from_range(result)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            snapshot["errors"].append(f"{key}: {exc}")
            series = []
        snapshot["series"][key] = {"title": title, "unit": unit, "series": series}

    return snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prometheus-url", default="http://localhost:9090")
    parser.add_argument("--cluster", default="gpu-telemetry-demo")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    snapshot = collect(args.prometheus_url, args.cluster)

    with open(args.output, "w") as f:
        json.dump(snapshot, f, indent=2)
        f.write("\n")

    populated = sum(
        1 for s in snapshot["series"].values() if s["series"]
    )
    print(
        f"Wrote {args.output}: {populated}/{len(snapshot['series'])} "
        f"range series populated, {len(snapshot['errors'])} error(s)."
    )
    if snapshot["errors"]:
        for err in snapshot["errors"]:
            print(f"  - {err}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
