"""Terraform configuration tests.

Runs `terraform fmt -check` and `terraform validate` on both roots. Validation
requires provider downloads, so these tests skip cleanly when the providers are
not cached and the network is unavailable.
"""

from __future__ import annotations

import subprocess

import pytest

from conftest import TERRAFORM_DIR

ROOTS = [TERRAFORM_DIR, TERRAFORM_DIR / "incluster"]


@pytest.mark.parametrize("root", ROOTS, ids=lambda p: p.name)
def test_terraform_fmt_is_clean(terraform, root):
    proc = subprocess.run(
        [terraform, "fmt", "-check", "-recursive", "-diff", str(root)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, f"terraform fmt needed in {root}:\n{proc.stdout}"


@pytest.mark.parametrize("root", ROOTS, ids=lambda p: p.name)
def test_terraform_validate(terraform, root):
    init = subprocess.run(
        [terraform, f"-chdir={root}", "init", "-backend=false", "-input=false"],
        capture_output=True,
        text=True,
        timeout=300,
    )
    if init.returncode != 0:
        pytest.skip(f"terraform init failed (offline?): {init.stderr.strip()[:200]}")

    proc = subprocess.run(
        [terraform, f"-chdir={root}", "validate", "-no-color"],
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert proc.returncode == 0, f"terraform validate failed in {root}:\n{proc.stdout}"


def test_infra_root_defines_gpu_node_pool():
    main = (TERRAFORM_DIR / "main.tf").read_text()
    assert "google_container_node_pool" in main
    assert "guest_accelerator" in main
    assert "gpu_driver_installation_config" in main
    assert "nvidia.com/gpu" in main, "GPU pool must be tainted"


def test_infra_root_removes_default_node_pool():
    main = (TERRAFORM_DIR / "main.tf").read_text()
    assert "remove_default_node_pool = true" in main


def test_infra_root_enables_workload_identity():
    main = (TERRAFORM_DIR / "main.tf").read_text()
    assert "workload_identity_config" in main


def test_incluster_root_installs_chart_with_gke_overlay():
    main = (TERRAFORM_DIR / "incluster" / "main.tf").read_text()
    assert "helm_release" in main
    assert "values-gke.yaml" in main, "in-cluster root must apply the GKE overlay"


def test_incluster_root_does_not_use_count_and_for_each_together():
    """Terraform forbids count and for_each on the same resource."""
    main = (TERRAFORM_DIR / "incluster" / "main.tf").read_text()
    for block in main.split("resource ")[1:]:
        assert not ("count" in block and "for_each" in block), (
            "a resource block mixes count and for_each"
        )


def test_tfvars_examples_exist_and_are_not_real_projects():
    for root in ROOTS:
        example = root / "terraform.tfvars.example"
        assert example.exists(), f"missing {example}"
        text = example.read_text()
        assert "YOUR_GCP_PROJECT_ID" in text, "example must not contain a real project id"
