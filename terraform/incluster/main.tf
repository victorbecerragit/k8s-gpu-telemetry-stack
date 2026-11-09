###############################################################################
# In-cluster deployment root for the GPU telemetry demo.
#
# Cloud-agnostic: it targets whatever cluster your current kubeconfig points
# at (run `gcloud container clusters get-credentials ...` for GKE or
# `aws eks update-kubeconfig ...` for EKS first), then installs the Helm chart
# plus the demo workloads through the Kubernetes/Helm providers.
#
# Usage:
#   cp terraform.tfvars.example terraform.tfvars   # set `cloud` to gke or eks
#   terraform -chdir=terraform/incluster init
#   terraform -chdir=terraform/incluster apply --var-file=terraform.tfvars
###############################################################################

terraform {
  required_version = ">= 1.5.0"

  required_providers {
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

locals {
  # Pick the platform overlay: GKE disables the GPU Operator (GKE owns the
  # driver + device plugin); EKS runs it against the NVIDIA AMI.
  overlay = var.cloud == "gke" ? "values-gke.yaml" : "values-eks.yaml"

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

# Both providers authenticate through the active kubeconfig context, so this
# root works against GKE, EKS, or any reachable cluster (kind, k3s, ...).
provider "kubernetes" {
  config_path    = var.kubeconfig_path
  config_context = var.kube_context
}

provider "helm" {
  kubernetes {
    config_path    = var.kubeconfig_path
    config_context = var.kube_context
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

  # Base values first, then the cloud overlay so it wins.
  values = [
    file("${local.chart_path}/values.yaml"),
    file("${local.chart_path}/${local.overlay}"),
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

  # On GKE the GPU Operator is disabled (GKE manages the driver + device
  # plugin); on EKS the operator waits on its DaemonSets. Either way `wait`
  # keeps the release settled before the demo workloads are applied.
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
