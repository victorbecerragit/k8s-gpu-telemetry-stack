variable "gcp_project_id" {
  description = "GCP project ID that owns the demo cluster"
  type        = string
}

variable "gcp_region" {
  description = "GCP region where the existing GKE cluster runs"
  type        = string
  default     = "us-central1"
}

variable "cluster_name" {
  description = "Existing GKE cluster name"
  type        = string
  default     = "gpu-telemetry-demo"
}

variable "cluster_location" {
  description = "Zone of the existing GKE cluster"
  type        = string
  default     = "us-central1-a"
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
