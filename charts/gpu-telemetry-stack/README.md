# gpu-telemetry-stack

Production-grade GPU observability for Kubernetes in a single umbrella chart.

It bundles four things that are usually wired together by hand:

| Component | What it gives you |
| --- | --- |
| **DCGM exporter** | Hardware-level GPU metrics: SM utilization, VRAM, PCIe throughput, temperature, XID errors |
| **eBPF probes** | Kernel-level pod-to-pod TCP round-trip latency histograms, no sidecars |
| **Prometheus** | `kube-prometheus-stack` plus five GPU/network SRE alert rules |
| **Grafana** | Pre-built *GPU Telemetry — Fleet & Network* dashboard, auto-provisioned |
| **GPU Operator** | NVIDIA driver + device plugin (EKS only; GKE manages its own) |

## Install

```bash
helm repo add gpu-telemetry-stack https://victorbecerragit.github.io/k8s-gpu-telemetry-stack
helm repo update

# GKE — GKE owns the NVIDIA driver and device plugin
helm install gpu-telemetry gpu-telemetry-stack/gpu-telemetry-stack \
  -n gpu-telemetry --create-namespace \
  -f https://raw.githubusercontent.com/victorbecerragit/k8s-gpu-telemetry-stack/main/charts/gpu-telemetry-stack/values-gke.yaml

# EKS — the GPU Operator installs drivers
helm install gpu-telemetry gpu-telemetry-stack/gpu-telemetry-stack \
  -n gpu-telemetry --create-namespace \
  -f https://raw.githubusercontent.com/victorbecerragit/k8s-gpu-telemetry-stack/main/charts/gpu-telemetry-stack/values-eks.yaml
```

Or from a clone:

```bash
helm install gpu-telemetry ./charts/gpu-telemetry-stack \
  -n gpu-telemetry --create-namespace \
  -f ./charts/gpu-telemetry-stack/values.yaml \
  -f ./charts/gpu-telemetry-stack/values-gke.yaml
```

## Requirements

- Kubernetes >= 1.27
- A GPU node pool with the NVIDIA device plugin (GKE: managed; EKS: GPU Operator)
- Prometheus Operator CRDs (installed by the bundled `kube-prometheus-stack`)
- For eBPF: kernel >= 5.4 and privileged pods

## Values

### Global

| Key | Default | Description |
| --- | --- | --- |
| `global.clusterName` | `gpu-cluster` | Cluster label used in dashboards |
| `global.namespace` | `""` | Namespace override; defaults to the release namespace |

### DCGM exporter

| Key | Default | Description |
| --- | --- | --- |
| `dcgm-exporter.enabled` | `true` | Deploy the DCGM exporter DaemonSet |
| `dcgm-exporter.image.repository` | `nvcr.io/nvidia/k8s/dcgm-exporter` | Image |
| `dcgm-exporter.image.tag` | `3.3.8-3.6.0-ubuntu22.04` | Image tag |
| `dcgm-exporter.serviceMonitor.enabled` | `true` | Create a ServiceMonitor |
| `dcgm-exporter.serviceMonitor.interval` | `15s` | Scrape interval |
| `dcgm-exporter.extraEnv` | field IDs `203,204,251,252,100,101,150,230` | DCGM field IDs to export |

Field IDs map to: SM utilization (203), memory-copy utilization (204), VRAM
free/used (251/252), PCIe TX/RX (100/101), temperature (150), XID errors (230).

### eBPF probes

| Key | Default | Description |
| --- | --- | --- |
| `ebpf-probes.enabled` | `true` | Deploy the tracing DaemonSet |
| `ebpf-probes.inspektorGadget.enabled` | `true` | Use Inspektor Gadget |
| `ebpf-probes.inspektorGadget.image.tag` | `latest` | Pin this in production |

The gadget is `profile_tcprtt`, which emits a native histogram of
kernel-smoothed TCP RTT in microseconds. The exported series is:

```text
latency_bucket{otel_scope_name="gadget_tcp_latency_us"}
```

### Prometheus

| Key | Default | Description |
| --- | --- | --- |
| `prometheus.enabled` | `true` | Deploy kube-prometheus-stack |
| `prometheus.rules.enabled` | `true` | Render the GPU/network alert rules |
| `prometheus.rules.thresholds.temperatureCelsius` | `85` | Thermal throttling threshold |
| `prometheus.rules.thresholds.vramPercent` | `90` | VRAM exhaustion threshold |
| `prometheus.rules.thresholds.tcpLatencyMicros` | `5000` | p99 TCP RTT threshold |
| `prometheus.kube-prometheus-stack.prometheus.prometheusSpec.retention` | `15d` | Retention |

### Grafana

| Key | Default | Description |
| --- | --- | --- |
| `grafana.enabled` | `true` | Deploy Grafana |
| `grafana.dashboards.enabled` | `true` | Ship the dashboard ConfigMap |
| `grafana.dashboards.folder` | `GPU Telemetry` | Dashboard folder |
| `grafana.grafana.adminPassword` | `""` | Set via secret, not `--set` |

### GPU Operator

| Key | Default | Description |
| --- | --- | --- |
| `gpu-operator.enabled` | `true` | Deploy the NVIDIA GPU Operator |
| `gpu-operator.gpu-operator.driver.enabled` | `false` | Enable only if the OS lacks drivers |
| `gpu-operator.gpu-operator.mig.strategy` | `""` | `single` or `mixed` for MIG |

> **GKE users:** set `gpu-operator.enabled=false`. GKE installs the driver and
> device plugin on GPU node pools; running the operator too creates a second
> device plugin competing for the same devices. `values-gke.yaml` does this for
> you.

## Alerts

| Alert | Severity | Trigger |
| --- | --- | --- |
| `GpuXidError` | critical | Any new `DCGM_FI_DEV_XID_ERRORS` in 5m |
| `GpuThermalThrottling` | warning | GPU temp > 85 °C for 5m |
| `GpuVramExhaustion` | warning | VRAM > 90 % for 10m |
| `GpuNotReporting` | critical | DCGM scrape target down 5m |
| `GpuPodTcpLatencyHigh` | warning | p99 pod-to-pod TCP RTT > 5000 µs for 10m |

## Accessing the UIs

```bash
kubectl port-forward -n gpu-telemetry svc/gpu-telemetry-grafana 3000:80
kubectl port-forward -n gpu-telemetry svc/gpu-telemetry-prometheus-kube-prometheus-prometheus 9090:9090
```

## Notes

- The eBPF DaemonSet needs privileged access to `/sys/fs/bpf`,
  `/sys/kernel/debug`, and `/sys/fs/cgroup`.
- `profile_tcprtt` only observes **established** connections, so it measures
  steady-state RTT, not handshake latency.
- Set Grafana credentials through a secret manager or sealed-secrets.

## License

Apache-2.0. See [LICENSE](https://github.com/victorbecerragit/k8s-gpu-telemetry-stack/blob/main/LICENSE).
