"""Demo manifest and script tests."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from conftest import DEMO_DIR, IMAGES_DIR, REPO_ROOT

SCRIPTS = REPO_ROOT / "scripts"


def _load_docs(path: Path) -> list[dict]:
    return [d for d in yaml.safe_load_all(path.read_text()) if d]


def test_gpu_workload_requests_a_gpu():
    docs = _load_docs(DEMO_DIR / "gpu-workload.yaml")
    deploy = next(d for d in docs if d["kind"] == "Deployment")
    container = deploy["spec"]["template"]["spec"]["containers"][0]
    assert container["resources"]["limits"]["nvidia.com/gpu"] == 1


def test_gpu_workload_tolerates_gpu_taint():
    docs = _load_docs(DEMO_DIR / "gpu-workload.yaml")
    deploy = next(d for d in docs if d["kind"] == "Deployment")
    tolerations = deploy["spec"]["template"]["spec"]["tolerations"]
    assert any(t.get("key") == "nvidia.com/gpu" for t in tolerations)


def test_gpu_workload_targets_gpu_pool():
    docs = _load_docs(DEMO_DIR / "gpu-workload.yaml")
    deploy = next(d for d in docs if d["kind"] == "Deployment")
    selector = deploy["spec"]["template"]["spec"]["nodeSelector"]
    assert selector.get("workload") == "gpu-telemetry"


def test_network_latency_has_server_and_client():
    docs = _load_docs(DEMO_DIR / "network-latency.yaml")
    names = {d["metadata"]["name"] for d in docs}
    assert "latency-server" in names
    assert "latency-client" in names
    assert any(d["kind"] == "Service" for d in docs)


def test_network_latency_client_spreads_across_nodes():
    docs = _load_docs(DEMO_DIR / "network-latency.yaml")
    client = next(
        d for d in docs if d["kind"] == "Deployment" and d["metadata"]["name"] == "latency-client"
    )
    constraints = client["spec"]["template"]["spec"]["topologySpreadConstraints"]
    assert any(c["topologyKey"] == "kubernetes.io/hostname" for c in constraints)


def test_demo_manifests_use_plain_namespace():
    """Manifests must be directly kubectl-applicable (no template placeholders)."""
    for name in ("gpu-workload.yaml", "network-latency.yaml"):
        text = (DEMO_DIR / name).read_text()
        assert "${" not in text, f"{name} still contains template placeholders"
        for doc in _load_docs(DEMO_DIR / name):
            assert doc["metadata"]["namespace"] == "gpu-demo"


@pytest.mark.parametrize(
    "script",
    [
        "bootstrap.sh",
        "lint.sh",
        "validate-dcgm-metrics.sh",
        "validate-ebpf-probes.sh",
        "demo-gke.sh",
    ],
)
def test_shell_scripts_are_executable_and_parse(script):
    path = SCRIPTS / script
    assert path.exists(), f"{script} missing"
    assert os.access(path, os.X_OK), f"{script} is not executable"
    proc = subprocess.run(["bash", "-n", str(path)], capture_output=True, text=True)
    assert proc.returncode == 0, f"{script} has a syntax error:\n{proc.stderr}"


@pytest.mark.parametrize(
    "script",
    ["collect-demo-metrics.py", "render-demo-charts.py", "generate-example-snapshot.py"],
)
def test_python_scripts_compile(script):
    path = SCRIPTS / script
    assert path.exists(), f"{script} missing"
    proc = subprocess.run(
        [sys.executable, "-m", "py_compile", str(path)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, f"{script} does not compile:\n{proc.stderr}"


def test_demo_gke_script_has_all_subcommands():
    text = (SCRIPTS / "demo-gke.sh").read_text()
    for cmd in ("up)", "snapshot)", "status)", "down)"):
        assert cmd in text, f"demo-gke.sh missing {cmd} handler"


def test_demo_gke_script_requires_project_id():
    text = (SCRIPTS / "demo-gke.sh").read_text()
    assert "GCP_PROJECT_ID" in text
    assert "require_project" in text


def test_example_snapshot_is_marked_synthetic(example_snapshot):
    assert example_snapshot.get("synthetic") is True, (
        "the committed example must be flagged synthetic so it is never mistaken "
        "for captured telemetry"
    )
    assert "not captured" in example_snapshot.get("note", "").lower()


def test_example_snapshot_matches_collector_schema(example_snapshot):
    """The example must be renderable by the same code path as real snapshots."""
    assert set(example_snapshot["summary"]) == {
        "avg_sm_utilization",
        "vram_utilization",
        "max_temperature",
        "xid_errors_1h",
    }
    assert set(example_snapshot["series"]) == {
        "sm_utilization",
        "vram_used",
        "gpu_temperature",
        "pcie_tx",
        "pcie_rx",
        "tcp_rtt_p99",
        "tcp_rtt_p50",
    }
    for meta in example_snapshot["series"].values():
        assert meta["series"], "every series must have data"
        for s in meta["series"]:
            assert s["points"], "series must have points"
            for p in s["points"]:
                assert isinstance(p["t"], (int, float))
                assert isinstance(p["v"], (int, float))


def test_renderer_produces_valid_svg(tmp_path):
    snapshot = DEMO_DIR / "snapshots" / "example.json"
    if not snapshot.exists():
        pytest.skip("example snapshot missing")

    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "render-demo-charts.py"),
            "--input",
            str(snapshot),
            "--output-dir",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr

    svgs = sorted(tmp_path.glob("*.svg"))
    assert len(svgs) == 8, f"expected 8 charts, got {len(svgs)}"

    import xml.etree.ElementTree as ET

    for svg in svgs:
        root = ET.parse(svg).getroot()
        assert root.tag.endswith("svg")
        assert root.get("width") and root.get("height")


def test_committed_images_are_valid_svg():
    svgs = sorted(IMAGES_DIR.glob("*.svg"))
    assert svgs, "no committed visualizations found"
    import xml.etree.ElementTree as ET

    for svg in svgs:
        ET.parse(svg)  # raises on malformed XML


def test_committed_images_are_watermarked_illustrative():
    """Committed charts come from the synthetic snapshot and must say so."""
    for svg in sorted(IMAGES_DIR.glob("*.svg")):
        text = svg.read_text()
        assert "ILLUSTRATIVE DATA" in text, f"{svg.name} is missing the watermark"


def test_collector_queries_match_dashboard(dashboard):
    """The collector must query the same series the dashboard does."""
    collector = (SCRIPTS / "collect-demo-metrics.py").read_text()
    assert 'otel_scope_name="gadget_tcp_latency_us"' in collector
    assert "DCGM_FI_DEV_GPU_UTIL" in collector
    assert "DCGM_FI_DEV_FB_USED" in collector
    assert "DCGM_FI_DEV_GPU_TEMP" in collector
    assert "gadget_tcp_latency_us_bucket" not in collector
