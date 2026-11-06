#!/usr/bin/env python3
"""Insert the NVLink panel into the GPU telemetry dashboard.

Kept as a script (rather than hand-editing JSON) so the panel is inserted with
correct gridPos arithmetic and the file stays valid JSON.

Usage: python3 scripts/add-nvlink-panel.py
"""

from __future__ import annotations

import json
from pathlib import Path

DASHBOARD = (
    Path(__file__).resolve().parent.parent
    / "charts/gpu-telemetry-stack/charts/grafana/dashboards/gpu-telemetry.json"
)

PANEL_ID = 10
ROW_ID = 103

DATASOURCE = {"type": "prometheus", "uid": "${datasource}"}


def _target(expr: str, legend: str, ref: str) -> dict:
    return {
        "datasource": DATASOURCE,
        "expr": expr,
        "legendFormat": legend,
        "refId": ref,
    }


def build_panels() -> list[dict]:
    row = {
        "collapsed": False,
        "gridPos": {"h": 1, "w": 24, "x": 0, "y": 32},
        "id": ROW_ID,
        "panels": [],
        "title": "NVLink Fabric",
        "type": "row",
    }

    bandwidth = {
        "datasource": DATASOURCE,
        "fieldConfig": {
            "defaults": {
                "color": {"mode": "palette-classic"},
                "custom": {
                    "axisCenteredZero": False,
                    "axisColorMode": "text",
                    "axisLabel": "",
                    "axisPlacement": "auto",
                    "drawStyle": "line",
                    "fillOpacity": 10,
                    "lineInterpolation": "linear",
                    "lineWidth": 1,
                    "pointSize": 5,
                    "showPoints": "never",
                    "spanNulls": False,
                    "stacking": {"group": "A", "mode": "none"},
                },
                "mappings": [],
                "thresholds": {
                    "mode": "absolute",
                    "steps": [{"color": "green", "value": None}],
                },
                "unit": "Bps",
            },
            "overrides": [],
        },
        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 33},
        "id": PANEL_ID,
        "options": {
            "legend": {
                "calcs": ["mean", "max"],
                "displayMode": "table",
                "placement": "bottom",
                "showLegend": True,
            },
            "tooltip": {"mode": "multi", "sort": "desc"},
        },
        "targets": [
            _target(
                'rate(DCGM_FI_DEV_NVLINK_BANDWIDTH_TOTAL{cluster="$cluster"}[5m])',
                "{{gpu}} {{Hostname}}",
                "A",
            )
        ],
        "title": "NVLink Throughput per GPU",
        "type": "timeseries",
    }

    errors = {
        "datasource": DATASOURCE,
        "fieldConfig": {
            "defaults": {
                "color": {"mode": "palette-classic"},
                "custom": {
                    "axisCenteredZero": False,
                    "axisColorMode": "text",
                    "axisLabel": "",
                    "axisPlacement": "auto",
                    "drawStyle": "line",
                    "fillOpacity": 10,
                    "lineInterpolation": "linear",
                    "lineWidth": 1,
                    "pointSize": 5,
                    "showPoints": "never",
                    "spanNulls": False,
                    "stacking": {"group": "A", "mode": "none"},
                },
                "mappings": [],
                "thresholds": {
                    "mode": "absolute",
                    "steps": [
                        {"color": "green", "value": None},
                        {"color": "red", "value": 1},
                    ],
                },
                "unit": "short",
            },
            "overrides": [],
        },
        "gridPos": {"h": 8, "w": 12, "x": 12, "y": 33},
        "id": PANEL_ID + 1,
        "options": {
            "legend": {
                "calcs": ["sum", "max"],
                "displayMode": "table",
                "placement": "bottom",
                "showLegend": True,
            },
            "tooltip": {"mode": "multi", "sort": "desc"},
        },
        "targets": [
            _target(
                'increase(DCGM_FI_DEV_NVLINK_RECOVERABLE_ERRORS{cluster="$cluster"}[5m])',
                "recoverable {{gpu}} {{Hostname}}",
                "A",
            ),
            _target(
                'increase(DCGM_FI_DEV_NVLINK_INVAL_ERRORS{cluster="$cluster"}[5m])',
                "invalid {{gpu}} {{Hostname}}",
                "B",
            ),
        ],
        "title": "NVLink Errors per GPU",
        "type": "timeseries",
    }

    return [row, bandwidth, errors]


def main() -> None:
    dashboard = json.loads(DASHBOARD.read_text())

    existing_ids = {p["id"] for p in dashboard["panels"]}
    if PANEL_ID in existing_ids or ROW_ID in existing_ids:
        raise SystemExit("NVLink panels already present; nothing to do")

    dashboard["panels"].extend(build_panels())
    DASHBOARD.write_text(json.dumps(dashboard, indent=2) + "\n")
    print(f"Added NVLink row + 2 panels to {DASHBOARD}")


if __name__ == "__main__":
    main()
