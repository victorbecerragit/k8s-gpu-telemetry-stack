###############################################################################
# In-cluster deployment root for the GPU telemetry demo.
#
# Mirrors the vllm-inference-platform `terraform/incluster` pattern: it targets
# an existing GKE cluster (created by ../main.tf) and installs the Helm chart
# plus the demo workloads through the Kubernetes/Helm providers.
#
# Usage:
#   cp terraform.tfvars.example terraform.tfvars
#   terraform -chdir=terraform/incluster init
#   terraform -chdir=terraform/incluster apply --var-file=terraform.tfvars
###############################################################################

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.30"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.13"
    }
  }
}

provider "google" {
  project = var.gcp_project_id
  region  = var.gcp_region
}

data "google_client_config" "default" {}

data "google_container_cluster" "primary" {
  name     = var.cluster_name
  location = var.cluster_location
}

locals {
  cluster_host      = "https://${data.google_container_cluster.primary.endpoint}"
  cluster_ca_cert   = base64decode(data.google_container_cluster.primary.master_auth[0].cluster_ca_certificate)
  cluster_token     = data.google_client_config.default.access_token
  chart_path        = abspath("${path.module}/../../charts/gpu-telemetry-stack")
  demo_manifest_dir = abspath("${path.module}/../../demo")

  # The demo manifests are plain, kubectl-applicable YAML. Terraform only
  # overrides the namespace, image and replica count so the same files work for
  # both `kubectl apply -f demo/` and `terraform apply`.
  gpu_workload = yamldecode(file("${local.demo_manifest_dir}/gpu-workload.yaml"))
  network_latency_docs = [
    for doc in split("\n---\n", file("${local.demo_manifest_dir}/network-latency.yaml")) :
    yamldecode(doc)
  ]
}

provider "kubernetes" {
  host                   = local.cluster_host
  token                  = local.cluster_token
  cluster_ca_certificate = local.cluster_ca_cert
}

provider "helm" {
  kubernetes {
    host                   = local.cluster_host
    token                  = local.cluster_token
    cluster_ca_certificate = local.cluster_ca_cert
  }
}

# ---------------------------------------------------------------------------
# Telemetry stack
# ---------------------------------------------------------------------------
resource "helm_release" "gpu_telemetry" {
  name             = var.release_name
  chart            = local.chart_path
  namespace        = var.namespace
  create_namespace = true

  # Base values first, then the GKE overlay so it wins.
  values = [
    file("${local.chart_path}/values.yaml"),
    file("${local.chart_path}/values-gke.yaml"),
  ]

  set {
    name  = "global.clusterName"
    value = var.cluster_name
  }

  set {
    name  = "global.namespace"
    value = var.namespace
  }

  dynamic "set" {
    # `for_each` requires a map or set, not a list. A ternary between a tuple
    # and an empty list also produces inconsistent types on older Terraform
    # versions, so build a set explicitly.
    for_each = toset(var.grafana_admin_password == "" ? [] : [var.grafana_admin_password])
    content {
      name  = "grafana.grafana.adminPassword"
      value = set.value
    }
  }

  # The GPU Operator is disabled on GKE (GKE manages the driver + device
  # plugin), so the release should settle without waiting on it.
  timeout = var.helm_timeout_seconds
  wait    = true
}

# ---------------------------------------------------------------------------
# Demo workloads (optional)
# ---------------------------------------------------------------------------
resource "kubernetes_namespace" "demo" {
  count = var.install_demo_workloads ? 1 : 0

  metadata {
    name = var.demo_namespace
    labels = {
      "app.kubernetes.io/part-of"    = "gpu-telemetry-stack"
      "app.kubernetes.io/managed-by" = "terraform"
    }
  }

  depends_on = [helm_release.gpu_telemetry]
}

resource "kubernetes_manifest" "gpu_workload" {
  count = var.install_demo_workloads ? 1 : 0

  manifest = merge(local.gpu_workload, {
    metadata = merge(local.gpu_workload.metadata, {
      namespace = var.demo_namespace
    })
    spec = merge(local.gpu_workload.spec, {
      replicas = var.gpu_workload_replicas
      template = merge(local.gpu_workload.spec.template, {
        spec = merge(local.gpu_workload.spec.template.spec, {
          containers = [
            for c in local.gpu_workload.spec.template.spec.containers : merge(c, {
              image = var.gpu_workload_image
              resources = {
                limits = {
                  "nvidia.com/gpu" = var.gpu_workload_gpu_count
                }
              }
            })
          ]
        })
      })
    })
  })

  depends_on = [kubernetes_namespace.demo]
}

resource "kubernetes_manifest" "network_latency" {
  for_each = var.install_demo_workloads ? tomap({
    for doc in local.network_latency_docs : "${doc.kind}-${doc.metadata.name}" => doc
  }) : tomap({})

  manifest = merge(each.value, {
    metadata = merge(each.value.metadata, {
      namespace = var.demo_namespace
    })
  })

  depends_on = [kubernetes_namespace.demo]
}
