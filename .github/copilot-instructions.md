# Project Context: k8s-gpu-telemetry-stack

## Objective
Demonstrate production-grade observability for GPU-accelerated Kubernetes clusters. Target metrics include hardware-level GPU stats via DCGM and kernel-level tracing via eBPF.

## Primary Tech Stack
- Kubernetes (GKE / EKS / Helm)
- NVIDIA GPU Operator & DCGM Exporter
- Cilium / Inspektor Gadget (eBPF)
- Prometheus & Grafana
- Terraform (GKE demo environment)

## Key Architectural Principles
- Infrastructure as Code using Helm / Kustomize / Terraform.
- DCGM metrics must monitor SM utilization, VRAM usage, PCIe bandwidth, and temperature.
- eBPF probes must monitor socket-level TCP latencies between pods without sidecar overhead.
- Dashboards must highlight actionable SRE alerts (e.g., GPU XID errors, thermal throttling, VRAM exhaustion).

## Code Style & Conventions
- Use standard Helm values layout with clean modular sub-charts.
- Include automated validation scripts for DCGM metric scraping endpoints.
- Keep the pytest suite green: `python3 -m pytest -q`.

## Platform Differences
- **GKE**: GKE manages the NVIDIA driver and device plugin, so `values-gke.yaml`
  disables the GPU Operator. The GPU pool is tainted
  `nvidia.com/gpu=present:NoSchedule`.
- **EKS**: relies on the GPU Operator for drivers.

## eBPF Network Telemetry
- Use `profile_tcprtt` (not `trace_tcp`) for TCP RTT histograms.
- The gadget data source is named `tcprtt`; both `--annotate` and
  `--otel-metrics-name` must use that name.
- Exported series is `latency_bucket{otel_scope_name="gadget_tcp_latency_us"}`.
  Dashboard and alerts must query that exact name.
