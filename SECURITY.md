# Security Policy

## Supported versions

Only the latest published chart version receives fixes.

| Chart version | Supported |
| --- | --- |
| latest `0.x` | ✅ |
| older | ❌ |

## Reporting a vulnerability

Please **do not** open a public GitHub issue for security problems.

Report privately via GitHub's
[private vulnerability reporting](https://github.com/victorbecerragit/k8s-gpu-telemetry-stack/security/advisories/new)
or by email to the maintainer listed in `Chart.yaml`.

Include:

- affected chart version
- a description of the issue and its impact
- reproduction steps or a proof of concept
- any suggested remediation

You can expect an acknowledgement within 72 hours and a remediation plan within
7 days for confirmed issues.

## Scope notes

This chart deploys third-party components. Vulnerabilities in those upstream
projects should be reported upstream, but we will bump pinned versions promptly
when a fix is released.

Components with elevated privileges by design:

- **eBPF probes** run privileged with host mounts of `/sys/fs/bpf`,
  `/sys/kernel/debug`, and `/sys/fs/cgroup`. This is required for kernel-level
  tracing and cannot be avoided. Restrict who can deploy to the namespace.
- **DCGM exporter** requires access to NVIDIA device nodes.
- **GPU Operator** (EKS only) installs kernel modules and a device plugin.

## Hardening checklist for operators

- Set Grafana admin credentials through a secret, never `--set` in shell history.
- Enable NetworkPolicies around the `gpu-telemetry` namespace.
- Pin image tags; avoid `latest` in production overlays.
- Restrict `ClusterRole` bindings created by the eBPF sub-chart to the nodes
  that actually need tracing.
