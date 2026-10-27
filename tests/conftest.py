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


# Wrapper sub-charts that vendor an upstream chart. If these are not built, the
# parent chart renders almost nothing and every render assertion fails with a
# confusing message. Check up front and fail with an actionable one instead.
WRAPPER_SUBCHARTS = ("prometheus", "grafana", "gpu-operator")


def _missing_nested_deps() -> list[str]:
    missing = []
    for name in WRAPPER_SUBCHARTS:
        chart_yaml = CHART_DIR / "charts" / name / "Chart.yaml"
        if not chart_yaml.exists():
            continue
        if "dependencies:" not in chart_yaml.read_text():
            continue
        vendored = list((CHART_DIR / "charts" / name / "charts").glob("*.tgz"))
        if not vendored:
            missing.append(name)
    return missing


def _assert_nested_deps_built() -> None:
    """Fail with an actionable message when wrapper deps were never built."""
    missing = _missing_nested_deps()
    if missing:
        pytest.fail(
            "Nested chart dependencies are missing for: "
            + ", ".join(missing)
            + ".\n`helm dependency build` on the root chart does NOT recurse into "
            "wrapper sub-charts, so the parent renders almost nothing.\n"
            "Run: ./scripts/build-deps.sh",
            pytrace=False,
        )


@pytest.fixture(scope="session")
def helm() -> str:
    return _require("helm")


@pytest.fixture(scope="session")
def terraform() -> str:
    return _require("terraform")


def render_chart(helm_bin: str, *value_files: str) -> list[dict]:
    """Render the chart and return the parsed Kubernetes documents."""
    _assert_nested_deps_built()
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
