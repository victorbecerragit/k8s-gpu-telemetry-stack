###############################################################################
# GKE demo infrastructure for the GPU telemetry stack.
#
# Mirrors the layout of the vllm-inference-platform terraform root:
#   - minimal VPC + subnet
#   - zonal GKE cluster with the default pool removed
#   - a small system node pool
#   - a dedicated GPU node pool (tainted) for DCGM / eBPF telemetry
#
# The in-cluster Helm deployment lives in ./incluster so that the cluster can
# be created and destroyed independently of the observability stack.
###############################################################################

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.gcp_project_id
  region  = var.gcp_region
}

data "google_client_config" "default" {}

# ---------------------------------------------------------------------------
# Required GCP APIs
# ---------------------------------------------------------------------------
resource "google_project_service" "required" {
  for_each = toset([
    "container.googleapis.com",
    "compute.googleapis.com",
    "cloudresourcemanager.googleapis.com",
  ])

  service            = each.value
  disable_on_destroy = false
}

# ---------------------------------------------------------------------------
# Minimal VPC network
# ---------------------------------------------------------------------------
resource "google_compute_network" "vpc" {
  name                    = "${var.cluster_name}-vpc"
  auto_create_subnetworks = false

  depends_on = [google_project_service.required]
}

resource "google_compute_subnetwork" "subnet" {
  name          = "${var.cluster_name}-subnet"
  ip_cidr_range = var.subnet_cidr
  region        = var.gcp_region
  network       = google_compute_network.vpc.name

  secondary_ip_range {
    range_name    = "pods"
    ip_cidr_range = var.pods_cidr
  }

  secondary_ip_range {
    range_name    = "services"
    ip_cidr_range = var.services_cidr
  }
}

# ---------------------------------------------------------------------------
# GKE cluster (default pool removed so pools can autoscale independently)
# ---------------------------------------------------------------------------
resource "google_container_cluster" "primary" {
  name     = var.cluster_name
  location = "${var.gcp_region}-a" # zonal cluster to minimize demo cost

  network    = google_compute_network.vpc.name
  subnetwork = google_compute_subnetwork.subnet.name

  remove_default_node_pool = true
  initial_node_count       = 1

  # VPC-native cluster mode (required for the secondary ranges above)
  ip_allocation_policy {
    cluster_secondary_range_name  = "pods"
    services_secondary_range_name = "services"
  }

  release_channel {
    channel = var.release_channel
  }

  # Workload Identity lets the in-cluster stack use GCP IAM without key files.
  workload_identity_config {
    workload_pool = "${var.gcp_project_id}.svc.id.goog"
  }

  # Demo clusters are disposable; keep destroy fast and predictable.
  deletion_protection = false

  logging_config {
    enable_components = ["SYSTEM_COMPONENTS", "WORKLOADS"]
  }

  monitoring_config {
    enable_components = ["SYSTEM_COMPONENTS"]
  }

  depends_on = [google_project_service.required]
}

# ---------------------------------------------------------------------------
# System node pool (Prometheus / Grafana / operators)
# ---------------------------------------------------------------------------
resource "google_container_node_pool" "system" {
  name     = "${var.cluster_name}-system-pool"
  location = "${var.gcp_region}-a"
  cluster  = google_container_cluster.primary.name

  initial_node_count = var.system_node_count

  autoscaling {
    min_node_count = var.system_node_count
    max_node_count = var.system_node_count + 2
  }

  node_config {
    machine_type = var.system_machine_type
    spot         = var.use_spot_instances
    image_type   = "COS_CONTAINERD"

    oauth_scopes = ["https://www.googleapis.com/auth/cloud-platform"]

    labels = {
      environment = "demo"
      workload    = "observability"
    }
  }

  management {
    auto_repair  = true
    auto_upgrade = true
  }
}

# ---------------------------------------------------------------------------
# GPU node pool (DCGM exporter + eBPF probes + demo workload)
#
# GKE installs the NVIDIA driver and device plugin for this pool, so the
# GPU Operator sub-chart is disabled in values-gke.yaml to avoid a second
# device plugin fighting over the same devices.
# ---------------------------------------------------------------------------
resource "google_container_node_pool" "gpu" {
  name     = "${var.cluster_name}-gpu-pool"
  location = "${var.gcp_region}-a"
  cluster  = google_container_cluster.primary.name

  initial_node_count = var.gpu_node_count

  autoscaling {
    min_node_count = var.gpu_node_count
    max_node_count = var.gpu_node_count + var.gpu_node_max_extra
  }

  node_config {
    machine_type = var.gpu_machine_type
    spot         = var.use_spot_instances
    image_type   = "COS_CONTAINERD"

    guest_accelerator {
      type  = var.gpu_type
      count = var.gpu_count_per_node

      # GKE-managed NVIDIA driver (LATEST or a pinned version).
      gpu_driver_installation_config {
        gpu_driver_version = var.gpu_driver_version
      }
    }

    oauth_scopes = ["https://www.googleapis.com/auth/cloud-platform"]

    labels = {
      environment = "demo"
      workload    = "gpu-telemetry"
    }

    # Keep non-GPU workloads off the expensive pool.
    taint {
      key    = "nvidia.com/gpu"
      value  = "present"
      effect = "NO_SCHEDULE"
    }
  }

  management {
    auto_repair  = true
    auto_upgrade = true
  }

  # GKE requires the driver install to finish before the pool reports ready.
  timeouts {
    create = "30m"
    update = "30m"
    delete = "30m"
  }
}
