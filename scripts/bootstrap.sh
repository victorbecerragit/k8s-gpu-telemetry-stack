#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
CHART_DIR="${ROOT_DIR}/charts/gpu-telemetry-stack"

echo "==> Adding required Helm repositories"
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts >/dev/null
helm repo add grafana https://grafana.github.io/helm-charts >/dev/null
helm repo add nvidia https://helm.ngc.nvidia.com/nvidia >/dev/null
helm repo update >/dev/null

echo "==> Building chart dependencies"
helm dependency build "${CHART_DIR}"

echo "==> Rendering a dry-run manifest"
helm template gpu-telemetry "${CHART_DIR}" \
  -f "${CHART_DIR}/values.yaml" \
  -f "${CHART_DIR}/values-dev.yaml" >/dev/null

echo "✔ Bootstrap complete."
echo "Next: helm install gpu-telemetry ${CHART_DIR} -n gpu-telemetry --create-namespace"
