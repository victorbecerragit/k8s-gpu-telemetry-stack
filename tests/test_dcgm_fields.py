"""DCGM field-collection tests.

The exporter is invoked with `-f <custom-fields.csv>`, which REPLACES the
image's built-in default-counters.csv. That makes the field list a single point
of failure: an omitted entry silently removes a metric from Prometheus, the
dashboard and the alert rules. These tests pin the contract.
"""

from __future__ import annotations

import yaml

from conftest import CHART_DIR

DCGM_VALUES = CHART_DIR / "charts" / "dcgm-exporter" / "values.yaml"

# Fields the stack must export. Mirrors tests/test_dashboard_alerts.py.
REQUIRED_FIELDS = {
    "DCGM_FI_DEV_SM_CLOCK",
    "DCGM_FI_DEV_GPU_UTIL",
    "DCGM_FI_DEV_MEM_COPY_UTIL",
    "DCGM_FI_DEV_FB_FREE",
    "DCGM_FI_DEV_FB_USED",
    "DCGM_FI_DEV_GPU_TEMP",
    "DCGM_FI_DEV_PCIE_TX_THROUGHPUT",
    "DCGM_FI_DEV_PCIE_RX_THROUGHPUT",
    "DCGM_FI_DEV_XID_ERRORS",
    "DCGM_FI_DEV_NVLINK_BANDWIDTH_TOTAL",
    "DCGM_FI_DEV_NVLINK_RECOVERABLE_ERRORS",
    "DCGM_FI_DEV_NVLINK_INVAL_ERRORS",
}

# DCGM field IDs for the NVLink additions.
NVLINK_FIELD_IDS = {
    "DCGM_FI_DEV_NVLINK_BANDWIDTH_TOTAL": 435,
    "DCGM_FI_DEV_NVLINK_RECOVERABLE_ERRORS": 440,
    "DCGM_FI_DEV_NVLINK_INVAL_ERRORS": 441,
}


def _fields() -> list[dict]:
    with open(DCGM_VALUES) as f:
        values = yaml.safe_load(f)
    return values["fieldCollection"]["fields"]


def test_field_collection_is_enabled():
    with open(DCGM_VALUES) as f:
        values = yaml.safe_load(f)
    assert values["fieldCollection"]["enabled"] is True
    assert values["fieldCollection"]["mountPath"].endswith(".csv")


def test_field_collection_covers_every_required_metric():
    """`-f` replaces the default file, so the list must be complete."""
    names = {f["name"] for f in _fields()}
    missing = REQUIRED_FIELDS - names
    assert not missing, f"field collection is missing {sorted(missing)}"


def test_nvlink_fields_carry_their_dcgm_ids():
    by_name = {f["name"]: f for f in _fields()}
    for name, field_id in NVLINK_FIELD_IDS.items():
        assert name in by_name, f"{name} missing from field collection"
        assert by_name[name]["id"] == field_id, (
            f"{name} must declare DCGM field ID {field_id}"
        )


def test_every_field_declares_type_and_help():
    for field in _fields():
        assert field.get("type") in {"gauge", "counter"}, field
        assert field.get("help"), f"{field['name']} has no help text"


def test_field_names_are_unique():
    names = [f["name"] for f in _fields()]
    assert len(names) == len(set(names)), "duplicate field names"


def test_dcgm_configmap_renders_the_csv(base_render):
    """The rendered ConfigMap must contain the NVLink lines verbatim."""
    configmaps = [
        d
        for d in base_render
        if d.get("kind") == "ConfigMap" and d["metadata"]["name"].endswith("-fields")
    ]
    assert configmaps, "DCGM field-collection ConfigMap not rendered"
    csv = configmaps[0]["data"]["custom-fields.csv"]
    for name in NVLINK_FIELD_IDS:
        assert name in csv, f"{name} missing from rendered CSV"
    # The core metrics must survive too — this is the regression that matters.
    assert "DCGM_FI_DEV_GPU_UTIL" in csv
    assert "DCGM_FI_DEV_XID_ERRORS" in csv


def test_dcgm_daemonset_passes_the_field_file(base_render):
    daemonsets = [
        d
        for d in base_render
        if d.get("kind") == "DaemonSet"
        and d["metadata"]["name"].endswith("dcgm-exporter")
    ]
    assert daemonsets, "DCGM exporter DaemonSet not rendered"
    container = daemonsets[0]["spec"]["template"]["spec"]["containers"][0]
    args = container["args"]
    assert "-f" in args, "exporter must be told to use the custom field file"
    field_path = args[args.index("-f") + 1]
    assert field_path.endswith(".csv")

    mounts = {m["name"]: m for m in container["volumeMounts"]}
    assert "dcgm-fields" in mounts, "field ConfigMap is not mounted"
    assert mounts["dcgm-fields"]["mountPath"] == field_path
    assert mounts["dcgm-fields"]["readOnly"] is True
