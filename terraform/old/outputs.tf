output "kubernetes_cluster_name" {
  description = "GKE cluster name"
  value       = google_container_cluster.primary.name
}

output "kubernetes_cluster_location" {
  description = "Zone the cluster runs in"
  value       = google_container_cluster.primary.location
}

output "gke_get_credentials_command" {
  description = "Command to configure kubectl authentication"
  value       = "gcloud container clusters get-credentials ${google_container_cluster.primary.name} --zone ${google_container_cluster.primary.location} --project ${var.gcp_project_id}"
}

output "gpu_node_pool_name" {
  description = "Name of the GPU node pool"
  value       = google_container_node_pool.gpu.name
}

output "gpu_node_pool_machine_type" {
  description = "Machine type backing the GPU node pool"
  value       = var.gpu_machine_type
}

output "gpu_type" {
  description = "Accelerator type attached to the GPU node pool"
  value       = var.gpu_type
}

output "helm_install_command" {
  description = "Command that installs the telemetry stack against the demo cluster"
  value       = "helm upgrade --install gpu-telemetry ./charts/gpu-telemetry-stack -n gpu-telemetry --create-namespace -f ./charts/gpu-telemetry-stack/values.yaml -f ./charts/gpu-telemetry-stack/values-gke.yaml"
}
