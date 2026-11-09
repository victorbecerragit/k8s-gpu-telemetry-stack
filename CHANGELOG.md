# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.5] - 2026-11-09

### Added

#### GHCR (OCI) dual-publishing

- The umbrella chart is now published to **two** registries from the same tag: the GitHub Pages Helm repository and GHCR as an OCI artifact. Install with `helm install gpu-telemetry oci://ghcr.io/victorbecerragit/charts/gpu-telemetry-stack --version 0.1.5` — no `helm repo add` required.
- `publish-helm-chart.yml` logs in to `ghcr.io` with `GITHUB_TOKEN` (`permissions: packages: write`), packages the chart under `charts/gpu-telemetry-stack`, asserts exactly one `.tgz` was produced, and pushes it to `oci://ghcr.io/<owner>/charts`.
- `Chart.yaml` carries the full set of `artifacthub.io/*` annotations (license, category, changes, links, screenshots, recommendations) so the chart can be listed on Artifact Hub without further metadata work.

### Changed

#### Multi-cloud Terraform layout

- `terraform/` is now a collection of independent root modules: `terraform/gke/` (GCP cluster), `terraform/eks/` (AWS cluster), and `terraform/incluster/` (Helm release + demo workloads). The previous single-cloud root is archived under `terraform/old/`.
- The GKE root restores the telemetry demo configuration: VPC-native subnet with pod/service ranges, Workload Identity, a `workload=observability` system pool, and a `workload=gpu-telemetry` GPU pool tainted `nvidia.com/gpu=present:NoSchedule` with the GKE-managed NVIDIA driver.
- The EKS root provisions a matching topology on AWS: `m6i.large` system node group and a tainted `g6.xlarge` (L4, Spot) GPU node group on the AL2023 NVIDIA AMI, aligned with `values-eks.yaml`.
- `terraform/incluster/` is now cloud-agnostic: it authenticates through the active kubeconfig context and selects the `values-gke.yaml` or `values-eks.yaml` overlay via the new `cloud` variable.
- `scripts/demo-gke.sh` targets the new `terraform/gke/` root and writes kubeconfig-based in-cluster tfvars.

### Added

- `terraform/README.md`, `terraform/gke/setup.txt`, and `terraform/eks/setup.txt` document per-root init/plan/apply workflows.
- `tests/test_terraform.py` validates all three roots and pins the node-label/taint contract between Terraform and the chart overlays.

## [0.1.4] - 2026-11-06

### Added

#### NVLink Fabric Telemetry

- **New**: `DCGM_FI_DEV_NVLINK_BANDWIDTH_TOTAL` (DCGM field `435`) — total NVLink bandwidth counter across all lanes
- **New**: `DCGM_FI_DEV_NVLINK_RECOVERABLE_ERRORS` (field `440`) — NVLink recoverable error counter
- **New**: `DCGM_FI_DEV_NVLINK_INVAL_ERRORS` (field `441`) — NVLink invalid packet error counter
- **New**: Custom DCGM field collection ConfigMap, mounted at `/etc/dcgm-exporter/custom-fields.csv` and passed to the exporter with `-f`
- **New**: *NVLink Fabric* dashboard row with two panels — per-GPU throughput (`rate(...[5m])`) and per-GPU error deltas (`increase(...[5m])`)

**Impact**: NVLink-attached GPU pairs (A100/H100/H200, GB200 NVL) now expose fabric saturation and link-error counters, so interconnect degradation is visible before it shows up as a training slowdown.

> [!IMPORTANT]
> `-f` **replaces** the exporter's built-in `default-counters.csv` rather than appending to it. The field list in `dcgm-exporter.fieldCollection.fields` is therefore the complete set of exported metrics. Removing an entry removes that metric from Prometheus, the dashboard and the alert rules. `tests/test_dcgm_fields.py` pins this contract.

**Migration**: Existing deployments receive a rolling update. The DaemonSet pod template changes (new `-f` argument and ConfigMap volume), so pods restart once:

```bash
helm upgrade gpu-telemetry ./charts/gpu-telemetry-stack --reuse-values
```

### Changed

- Updated `dcgm-exporter` subchart from `0.1.1` to `0.1.2`
- `scripts/build-deps.sh` now falls back to `helm dependency update` when `Chart.lock` is out of sync, so bumping a local sub-chart version no longer fails the build

### Configuration

New configurable options under `dcgm-exporter`:

| Key | Default | Description |
| --- | --- | --- |
| `dcgm-exporter.fieldCollection.enabled` | `true` | Render the field-collection ConfigMap and pass `-f` to the exporter |
| `dcgm-exporter.fieldCollection.mountPath` | `/etc/dcgm-exporter/custom-fields.csv` | Where the CSV is mounted in the container |
| `dcgm-exporter.fieldCollection.fields` | 12 fields | List of `{name, type, help, id?}` entries written to the CSV |

### Notes

- NVLink counters are only emitted on GPUs with NVLink bridges. On PCIe-only instances (e.g. `g2-standard-4` / L4) the series is absent — the panels render empty rather than erroring.
- `DCGM_FI_DEV_NVLINK_BANDWIDTH_TOTAL` is a cumulative counter, so the dashboard applies `rate()`; the error panels use `increase()` to show new errors per interval.

---

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
