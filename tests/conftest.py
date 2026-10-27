"""Shared fixtures for the GPU telemetry stack test suite."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
CHART_DIR = REPO_ROOT / "charts" / "gpu-telemetry-stack"
DASHBOARD = CHART_DIR / "charts" / "grafana" / "dashboards" / "gpu-telemetry.json"
PROMETHEUS_RULE = CHART_DIR / "charts" / "prometheus" / "templates" / "prometheusrule.yaml"
EBPF_VALUES = CHART_DIR / "charts" / "ebpf-probes" / "values.yaml"
DEMO_DIR = REPO_ROOT / "demo"
TERRAFORM_DIR = REPO_ROOT / "terraform"
IMAGES_DIR = REPO_ROOT / "docs" / "images"


def _require(tool: str) -> str:
    path = shutil.which(tool)
    if not path:
        pytest.skip(f"{tool} is not installed")
    return path


@pytest.fixture(scope="session")
def helm() -> str:
    return _require("helm")


@pytest.fixture(scope="session")
def terraform() -> str:
    return _require("terraform")


def render_chart(helm_bin: str, *value_files: str) -> list[dict]:
    """Render the chart and return the parsed Kubernetes documents."""
    cmd = [helm_bin, "template", "gpu-telemetry", str(CHART_DIR)]
    for vf in value_files:
        cmd += ["-f", str(vf)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    assert proc.returncode == 0, f"helm template failed:\n{proc.stderr}"
    return [doc for doc in yaml.safe_load_all(proc.stdout) if doc]


@pytest.fixture(scope="session")
def base_render(helm: str) -> list[dict]:
    return render_chart(helm, str(CHART_DIR / "values.yaml"))


@pytest.fixture(scope="session")
def gke_render(helm: str) -> list[dict]:
    return render_chart(
        helm,
        str(CHART_DIR / "values.yaml"),
        str(CHART_DIR / "values-gke.yaml"),
    )


@pytest.fixture(scope="session")
def eks_render(helm: str) -> list[dict]:
    return render_chart(
        helm,
        str(CHART_DIR / "values.yaml"),
        str(CHART_DIR / "values-eks.yaml"),
    )


@pytest.fixture(scope="session")
def dashboard() -> dict:
    with open(DASHBOARD) as f:
        return json.load(f)


@pytest.fixture(scope="session")
def example_snapshot() -> dict:
    path = DEMO_DIR / "snapshots" / "example.json"
    if not path.exists():
        pytest.skip("example snapshot not generated")
    with open(path) as f:
        return json.load(f)


def find_docs(docs: list[dict], kind: str, name_contains: str = "") -> list[dict]:
    return [
        d
        for d in docs
        if d.get("kind") == kind and name_contains in d.get("metadata", {}).get("name", "")
    ]
