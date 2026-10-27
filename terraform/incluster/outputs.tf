output "helm_release_name" {
  description = "Name of the installed Helm release"
  value       = helm_release.gpu_telemetry.name
}

output "helm_release_namespace" {
  description = "Namespace of the installed Helm release"
  value       = helm_release.gpu_telemetry.namespace
}

output "helm_release_status" {
  description = "Status reported by Helm after apply"
  value       = helm_release.gpu_telemetry.status
}

output "demo_workloads_enabled" {
  description = "Whether the demo workloads were deployed"
  value       = var.install_demo_workloads
}

output "demo_namespace" {
  description = "Namespace holding the demo workloads"
  value       = var.install_demo_workloads ? kubernetes_namespace.demo[0].metadata[0].name : null
}

output "grafana_port_forward_command" {
  description = "Command to reach Grafana locally"
  value       = "kubectl port-forward -n ${var.namespace} svc/${var.release_name}-grafana 3000:80"
}

output "prometheus_port_forward_command" {
  description = "Command to reach Prometheus locally"
  value       = "kubectl port-forward -n ${var.namespace} svc/${var.release_name}-prometheus-kube-prometheus-prometheus 9090:9090"
}
