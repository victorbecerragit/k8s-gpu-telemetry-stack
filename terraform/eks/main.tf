###############################################################################
# EKS demo infrastructure for the GPU telemetry stack.
#
# Layout mirrors the GKE root (../gke) so the same Helm chart + demo workloads
# run on either cloud:
#   - VPC with public/private subnets (terraform-aws-modules/vpc)
#   - EKS cluster (terraform-aws-modules/eks)
#   - a system node group for Prometheus / Grafana / operators
#   - a GPU node group (tainted, L4 on g6, Spot by default)
#
# Unlike GKE, AWS does not install the NVIDIA driver for you, so the GPU node
# group uses the AL2023 NVIDIA AMI (driver preinstalled) and the GPU Operator
# sub-chart runs with driver.enabled=false (see values-eks.yaml).
#
# The in-cluster Helm deployment lives in ../incluster.
###############################################################################

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  azs = slice(data.aws_availability_zones.available.names, 0, 3)

  common_tags = merge(
    {
      Environment = "demo"
      Project     = "k8s-gpu-telemetry-stack"
      ManagedBy   = "terraform"
    },
    var.tags
  )
}

# ---------------------------------------------------------------------------
# VPC
# ---------------------------------------------------------------------------
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = "${var.cluster_name}-vpc"
  cidr = var.vpc_cidr

  azs             = local.azs
  private_subnets = [for k, az in local.azs : cidrsubnet(var.vpc_cidr, 4, k)]
  public_subnets  = [for k, az in local.azs : cidrsubnet(var.vpc_cidr, 8, k + 48)]

  enable_nat_gateway   = true
  single_nat_gateway   = true # demo-scale: one NAT gateway to keep cost down
  enable_dns_hostnames = true
  enable_dns_support   = true

  public_subnet_tags = {
    "kubernetes.io/role/elb" = "1"
  }

  private_subnet_tags = {
    "kubernetes.io/role/internal-elb" = "1"
  }

  tags = local.common_tags
}

# ---------------------------------------------------------------------------
# EKS cluster + node groups
# ---------------------------------------------------------------------------
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.0"

  cluster_name    = var.cluster_name
  cluster_version = var.cluster_version

  cluster_endpoint_public_access = true
  # Grants the Terraform caller kubectl access on a brand-new cluster.
  enable_cluster_creator_admin_permissions = true

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  cluster_addons = {
    coredns    = {}
    kube-proxy = {}
    vpc-cni    = {}
  }

  eks_managed_node_groups = {
    # Observability plane: Prometheus / Grafana / operators.
    system = {
      instance_types = var.system_node_instance_types
      capacity_type  = var.system_capacity_type

      min_size     = var.system_node_min_count
      max_size     = var.system_node_max_count
      desired_size = var.system_node_desired_count

      labels = {
        environment = "demo"
        workload    = "observability"
      }

      tags = merge(local.common_tags, {
        Name     = "${var.cluster_name}-system"
        NodeRole = "system"
      })
    }

    # GPU plane: DCGM exporter + demo workloads. The taint matches the
    # tolerations shipped in values-eks.yaml and demo/gpu-workload.yaml.
    gpu = {
      instance_types = var.gpu_node_instance_types
      capacity_type  = var.gpu_capacity_type
      # Amazon Linux 2023 with the NVIDIA driver preinstalled; the GPU
      # Operator then only adds the toolkit + device plugin (driver disabled).
      ami_type = "AL2023_x86_64_NVIDIA"

      min_size     = var.gpu_node_min_count
      max_size     = var.gpu_node_max_count
      desired_size = var.gpu_node_desired_count

      labels = {
        environment = "demo"
        workload    = "gpu-telemetry"
      }

      taints = [
        {
          key    = "nvidia.com/gpu"
          value  = "present"
          effect = "NO_SCHEDULE"
        }
      ]

      tags = merge(local.common_tags, {
        Name     = "${var.cluster_name}-gpu"
        NodeRole = "gpu"
      })
    }
  }

  tags = local.common_tags
}
