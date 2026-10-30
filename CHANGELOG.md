# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.3] - 2026-10-30

### Added

#### DCGM Exporter Kubernetes Mode

- **New**: Enable Kubernetes mode (`-k` flag) for pod/namespace attribution on GPU metrics
- **New**: Automatic mounting of Kubelet PodResources socket (`/var/lib/kubelet/pod-resources`)
- **New**: `DCGM_FI_DEV_*` metrics now include `pod`, `namespace`, and `container` labels

**Impact**: Users can now correlate GPU utilization with specific workloads without manual label mapping.

**Migration**: Existing deployments will receive a rolling update when upgrading:
```bash
helm upgrade gpu-telemetry ./charts/gpu-telemetry-stack --reuse-values
```

### Changed

- Updated `dcgm-exporter` subchart from `0.1.0` to `0.1.1`

### Configuration

New configurable options under `dcgm-exporter`:

| Key | Default | Description |
| --- | --- | --- |
| `dcgm-exporter.kubernetesMode.enabled` | `true` | Enable Kubernetes mode for pod attribution |
| `dcgm-exporter.kubernetesMode.arguments` | `["-k"]` | Arguments passed to DCGM exporter binary |
| `dcgm-exporter.volumeMounts` | pod-resources mount | Volume mounts for Kubelet socket |
| `dcgm-exporter.volumes` | hostPath volume | HostPath volume for pod-resources directory |

---

## [0.1.2] - Previous Release

- Initial production-ready release
- DCGM exporter for GPU hardware metrics
- eBPF probes for network latency
- Prometheus alert rules
- Grafana dashboard
