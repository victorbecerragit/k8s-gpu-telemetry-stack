output "kubernetes_cluster_name" {
  description = "EKS cluster name"
  value       = module.eks.cluster_name
}

output "kubernetes_cluster_endpoint" {
  description = "EKS API server endpoint"
  value       = module.eks.cluster_endpoint
}

output "aws_region" {
  description = "AWS region where the cluster is deployed"
  value       = var.aws_region
}

output "eks_update_kubeconfig_command" {
  description = "Command to configure kubectl authentication"
  value       = "aws eks update-kubeconfig --name ${module.eks.cluster_name} --region ${var.aws_region}"
}

output "gpu_node_group_name" {
  description = "Managed node group name for GPU telemetry workloads"
  value       = module.eks.eks_managed_node_groups["gpu"].node_group_name
}

output "helm_install_command" {
  description = "Command that installs the telemetry stack against the demo cluster"
  value       = "helm upgrade --install gpu-telemetry ./charts/gpu-telemetry-stack -n gpu-telemetry --create-namespace -f ./charts/gpu-telemetry-stack/values.yaml -f ./charts/gpu-telemetry-stack/values-eks.yaml"
}
