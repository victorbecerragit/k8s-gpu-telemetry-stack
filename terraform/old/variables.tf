variable "gcp_project_id" {
  description = "GCP project ID that owns the demo cluster"
  type        = string
}

variable "gcp_region" {
  description = "GCP region for the demo cluster"
  type        = string
  default     = "us-central1"
}

variable "cluster_name" {
  description = "Name of the GKE cluster"
  type        = string
  default     = "gpu-telemetry-demo"
}

variable "release_channel" {
  description = "GKE release channel (RAPID, REGULAR, STABLE)"
  type        = string
  default     = "REGULAR"
}

# -- Networking -------------------------------------------------------------

variable "subnet_cidr" {
  description = "Primary CIDR for the cluster subnet"
  type        = string
  default     = "10.10.0.0/20"
}

variable "pods_cidr" {
  description = "Secondary CIDR used for pod IPs"
  type        = string
  default     = "10.20.0.0/16"
}

variable "services_cidr" {
  description = "Secondary CIDR used for service IPs"
  type        = string
  default     = "10.30.0.0/20"
}

# -- System node pool -------------------------------------------------------

variable "system_machine_type" {
  description = "Machine type for the observability node pool"
  type        = string
  default     = "e2-standard-4"
}

variable "system_node_count" {
  description = "Initial (and minimum) node count for the system pool"
  type        = number
  default     = 1
}

# -- GPU node pool ----------------------------------------------------------

variable "gpu_machine_type" {
  description = "Machine type for the GPU pool (g2-standard-4 pairs with nvidia-l4)"
  type        = string
  default     = "g2-standard-4"
}

variable "gpu_type" {
  description = "GPU accelerator type (nvidia-l4, nvidia-tesla-t4, nvidia-tesla-a100)"
  type        = string
  default     = "nvidia-l4"
}

variable "gpu_count_per_node" {
  description = "Number of GPUs attached to each GPU node"
  type        = number
  default     = 1
}

variable "gpu_driver_version" {
  description = "GKE-managed NVIDIA driver version (LATEST or a pinned version)"
  type        = string
  default     = "LATEST"
}

variable "gpu_node_count" {
  description = "Initial (and minimum) node count for the GPU pool"
  type        = number
  default     = 1
}

variable "gpu_node_max_extra" {
  description = "Extra nodes the GPU pool may autoscale to above gpu_node_count"
  type        = number
  default     = 1
}

variable "use_spot_instances" {
  description = "Use Spot VMs to minimize demo cost"
  type        = bool
  default     = true
}
