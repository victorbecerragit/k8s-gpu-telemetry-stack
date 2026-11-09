variable "aws_region" {
  description = "AWS region for the EKS demo cluster"
  type        = string
  default     = "us-west-2"
}

variable "cluster_name" {
  description = "Name of the EKS cluster"
  type        = string
  default     = "gpu-telemetry-demo"
}

variable "cluster_version" {
  description = "Kubernetes version for EKS"
  type        = string
  default     = "1.30"
}

variable "vpc_cidr" {
  description = "CIDR block for the EKS VPC"
  type        = string
  default     = "10.20.0.0/16"
}

# -- System node group ------------------------------------------------------

variable "system_node_instance_types" {
  description = "Instance types for the observability node group"
  type        = list(string)
  default     = ["m6i.large"]
}

variable "system_capacity_type" {
  description = "System node capacity type (ON_DEMAND or SPOT)"
  type        = string
  default     = "ON_DEMAND"
}

variable "system_node_desired_count" {
  description = "Desired system node count"
  type        = number
  default     = 1
}

variable "system_node_min_count" {
  description = "Minimum system node count"
  type        = number
  default     = 1
}

variable "system_node_max_count" {
  description = "Maximum system node count"
  type        = number
  default     = 3
}

# -- GPU node group ---------------------------------------------------------

variable "gpu_node_instance_types" {
  description = "GPU node group instance types (g6 family uses NVIDIA L4 GPUs)"
  type        = list(string)
  default     = ["g6.xlarge"]
}

variable "gpu_capacity_type" {
  description = "GPU node capacity type (SPOT recommended for cost control)"
  type        = string
  default     = "SPOT"
}

variable "gpu_node_desired_count" {
  description = "Desired GPU node count (set >0 after quota approval)"
  type        = number
  default     = 1
}

variable "gpu_node_min_count" {
  description = "Minimum GPU node count"
  type        = number
  default     = 0
}

variable "gpu_node_max_count" {
  description = "Maximum GPU node count"
  type        = number
  default     = 1
}

variable "tags" {
  description = "Additional tags applied to EKS resources"
  type        = map(string)
  default     = {}
}
