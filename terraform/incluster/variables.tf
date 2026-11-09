variable "cloud" {
  description = "Target platform: gke or eks (selects the Helm values overlay)"
  type        = string
  default     = "gke"

  validation {
    condition     = contains(["gke", "eks"], var.cloud)
    error_message = "cloud must be \"gke\" or \"eks\"."
  }
}

variable "cluster_name" {
  description = "Name of the existing cluster (used for global.clusterName)"
  type        = string
  default     = "gpu-telemetry-demo"
}

variable "kubeconfig_path" {
  description = "Path to the kubeconfig file (empty = default loading rules)"
  type        = string
  default     = ""
}

variable "kube_context" {
  description = "Kubeconfig context to target (empty = current context)"
  type        = string
  default     = ""
}

# -- Helm release -----------------------------------------------------------

variable "release_name" {
  description = "Helm release name for the telemetry stack"
  type        = string
  default     = "gpu-telemetry"
}

variable "namespace" {
  description = "Namespace for the telemetry stack"
  type        = string
  default     = "gpu-telemetry"
}

variable "grafana_admin_password" {
  description = "Grafana admin password (leave empty to use the chart default)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "helm_timeout_seconds" {
  description = "Timeout for the Helm release to become ready"
  type        = number
  default     = 900
}

# -- Demo workloads ---------------------------------------------------------

variable "install_demo_workloads" {
  description = "Deploy the GPU burn and pod-to-pod latency demo workloads"
  type        = bool
  default     = true
}

variable "demo_namespace" {
  description = "Namespace for the demo workloads"
  type        = string
  default     = "gpu-demo"
}

variable "gpu_workload_image" {
  description = "Container image used to generate sustained GPU load"
  type        = string
  default     = "nvcr.io/nvidia/pytorch:24.08-py3"
}

variable "gpu_workload_gpu_count" {
  description = "GPUs requested by each demo workload replica"
  type        = number
  default     = 1
}

variable "gpu_workload_replicas" {
  description = "Number of GPU load replicas"
  type        = number
  default     = 1
}
