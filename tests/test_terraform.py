"""Terraform configuration tests.

Runs `terraform fmt -check` and `terraform validate` on each root. Validation
requires provider downloads, so these tests skip cleanly when the providers are
not cached and the network is unavailable.
"""

from __future__ import annotations

import subprocess

import pytest

from conftest import TERRAFORM_DIR

GKE_DIR = TERRAFORM_DIR / "gke"
EKS_DIR = TERRAFORM_DIR / "eks"
ROOTS = [GKE_DIR, EKS_DIR, TERRAFORM_DIR / "incluster"]


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


def test_gke_root_defines_gpu_node_pool():
    main = (GKE_DIR / "main.tf").read_text()
    assert "google_container_node_pool" in main
    assert "guest_accelerator" in main
    assert "gpu_driver_installation_config" in main
    assert "nvidia.com/gpu" in main, "GPU pool must be tainted"


def test_gke_root_removes_default_node_pool():
    main = (GKE_DIR / "main.tf").read_text()
    assert "remove_default_node_pool = true" in main


def test_gke_root_enables_workload_identity():
    main = (GKE_DIR / "main.tf").read_text()
    assert "workload_identity_config" in main


def test_gke_root_node_labels_match_chart_selectors():
    """values-gke.yaml schedules on these labels; the pools must carry them."""
    main = (GKE_DIR / "main.tf").read_text()
    assert 'workload    = "observability"' in main, "system pool must label workload=observability"
    assert 'workload    = "gpu-telemetry"' in main, "GPU pool must label workload=gpu-telemetry"


def test_eks_root_defines_tainted_gpu_node_group():
    main = (EKS_DIR / "main.tf").read_text()
    assert 'ami_type       = "AL2023_x86_64_NVIDIA"' in main or "AL2023_x86_64_NVIDIA" in main
    assert "nvidia.com/gpu" in main, "GPU node group must be tainted"
    assert 'workload    = "gpu-telemetry"' in main
    assert 'workload    = "observability"' in main


def test_incluster_root_selects_cloud_overlay():
    main = (TERRAFORM_DIR / "incluster" / "main.tf").read_text()
    assert "helm_release" in main
    assert "values-gke.yaml" in main, "in-cluster root must support the GKE overlay"
    assert "values-eks.yaml" in main, "in-cluster root must support the EKS overlay"


def test_incluster_root_is_cloud_agnostic():
    """The in-cluster root authenticates via kubeconfig, not cloud providers."""
    main = (TERRAFORM_DIR / "incluster" / "main.tf").read_text()
    assert 'source  = "hashicorp/google"' not in main


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
        assert "vllm-inference-platform" not in text, "example must not contain a real project id"
    assert "YOUR_GCP_PROJECT_ID" in (GKE_DIR / "terraform.tfvars.example").read_text()
