"""Release metadata tests: chart packaging, Artifact Hub annotations, publishing.

These guard the public distribution surface. A broken Chart.yaml or a workflow
that packages the wrong directory silently breaks `helm repo add` for every
consumer, so the checks are deliberately strict.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest
import yaml

from conftest import CHART_DIR, REPO_ROOT

WORKFLOWS = REPO_ROOT / ".github" / "workflows"
PUBLISH_WORKFLOW = WORKFLOWS / "publish-helm-chart.yml"
PAGES_INDEX = REPO_ROOT / "docs" / "pages" / "index.html"
CHART_README = CHART_DIR / "README.md"


@pytest.fixture(scope="module")
def chart_meta() -> dict:
    with open(CHART_DIR / "Chart.yaml") as f:
        return yaml.safe_load(f)


def test_chart_has_artifacthub_metadata(chart_meta):
    """Artifact Hub annotations are optional but must be valid if present.

    They are inert until the repository is registered at artifacthub.io, and
    they do not affect `helm repo add` against GitHub Pages. Keeping them
    correct means listing later requires no chart changes.
    """
    assert chart_meta["home"].startswith("https://github.com/")
    assert chart_meta["sources"], "sources must be set for Artifact Hub"
    assert chart_meta["maintainers"], "maintainers must be set"
    assert chart_meta["keywords"], "keywords drive Artifact Hub search"

    annotations = chart_meta["annotations"]
    assert annotations["artifacthub.io/license"] == "Apache-2.0"
    assert annotations["artifacthub.io/category"] == "monitoring-logging"
    assert "artifacthub.io/changes" in annotations
    assert "artifacthub.io/links" in annotations


def test_chart_icon_exists_locally(chart_meta):
    """The icon URL must point at a file that is actually committed."""
    icon = chart_meta["icon"]
    assert "raw.githubusercontent.com" in icon
    rel = icon.split("/main/", 1)[1]
    assert (REPO_ROOT / rel).is_file(), f"icon {rel} is missing from the repo"


def test_chart_readme_exists_for_artifact_hub():
    assert CHART_README.is_file(), "Artifact Hub renders charts/<name>/README.md"
    text = CHART_README.read_text()
    assert "helm repo add" in text
    assert "values-gke.yaml" in text


def test_chart_version_is_semver(chart_meta):
    assert re.fullmatch(r"\d+\.\d+\.\d+", chart_meta["version"]), (
        "chart version must be plain semver; the publish workflow compares it "
        "against the git tag"
    )


def test_license_file_present():
    license_file = REPO_ROOT / "LICENSE"
    assert license_file.is_file()
    assert "Apache License" in license_file.read_text()


def test_publish_workflow_packages_umbrella_chart():
    text = PUBLISH_WORKFLOW.read_text()
    assert "charts/gpu-telemetry-stack" in text
    assert "helm package" in text
    assert "helm repo index" in text
    assert "--merge" in text, "must merge with the existing index to keep old versions"
    assert "gh-pages" in text


def test_publish_workflow_verifies_tag_matches_chart_version():
    text = PUBLISH_WORKFLOW.read_text()
    assert "does not match Chart.yaml version" in text


def test_publish_workflow_builds_deps_recursively():
    """Packaging without nested deps ships an empty umbrella chart."""
    text = PUBLISH_WORKFLOW.read_text()
    assert "./scripts/build-deps.sh" in text


def test_publish_workflow_runs_tests_before_publishing():
    text = PUBLISH_WORKFLOW.read_text()
    assert "pytest" in text
    validate_idx = text.index("name: Validate chart")
    publish_idx = text.index("name: Publish to GitHub Pages")
    assert validate_idx < publish_idx


def test_readme_documents_github_pages_as_the_helm_repo():
    """GitHub Pages is the registry; Artifact Hub is only optional discovery."""
    text = (REPO_ROOT / "README.md").read_text()
    assert "helm repo add gpu-telemetry-stack https://victorbecerragit.github.io" in text
    assert "GitHub Pages **is** the Helm repository" in text


def test_readme_has_no_artifacthub_badge_before_registration():
    """The endpoint badge 404s until the repo is registered at artifacthub.io.

    The README documents the badge inside a fenced code block for later use;
    only a real badge line (outside a fence) would render as a broken image.
    """
    lines = (REPO_ROOT / "README.md").read_text().splitlines()
    in_fence = False
    for line in lines:
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        assert not line.lstrip().startswith("[![Artifact Hub]"), (
            "Do not add the Artifact Hub badge until the repository is "
            "registered; it renders as a broken image until then."
        )


def test_pages_landing_page_exists():
    assert PAGES_INDEX.is_file()
    html = PAGES_INDEX.read_text()
    assert "helm repo add gpu-telemetry-stack" in html
    assert "index.yaml" in html


def test_pages_landing_page_has_no_unclosed_placeholders():
    html = PAGES_INDEX.read_text()
    assert "{{" not in html and "}}" not in html, "template placeholders leaked into HTML"


def test_workflow_yaml_is_parseable():
    for wf in WORKFLOWS.glob("*.y*ml"):
        with open(wf) as f:
            doc = yaml.safe_load(f)
        assert "jobs" in doc, f"{wf.name} has no jobs"


def test_packaged_chart_contains_subcharts(helm, tmp_path):
    """A packaged umbrella chart must embed its sub-charts."""
    proc = subprocess.run(
        [helm, "package", str(CHART_DIR), "--destination", str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert proc.returncode == 0, proc.stderr

    tgz = next(tmp_path.glob("gpu-telemetry-stack-*.tgz"))
    listing = subprocess.run(
        ["tar", "-tzf", str(tgz)], capture_output=True, text=True, check=True
    ).stdout

    for sub in ("dcgm-exporter", "ebpf-probes", "prometheus", "grafana", "gpu-operator"):
        assert f"gpu-telemetry-stack/charts/{sub}/Chart.yaml" in listing, (
            f"{sub} missing from the packaged chart"
        )
