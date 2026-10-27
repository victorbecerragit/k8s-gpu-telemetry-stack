#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
CHART_DIR="${ROOT_DIR}/charts/gpu-telemetry-stack"

echo "==> Adding required Helm repositories"
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts >/dev/null 2>&1 || true
helm repo add grafana https://grafana.github.io/helm-charts >/dev/null 2>&1 || true
helm repo add nvidia https://helm.ngc.nvidia.com/nvidia >/dev/null 2>&1 || true
helm repo update >/dev/null

# Builds the root chart AND every nested wrapper sub-chart. Building only the
# root leaves the prometheus/grafana/gpu-operator wrappers empty.
echo "==> Building chart dependencies (recursive)"
"${SCRIPT_DIR}/build-deps.sh"

echo "==> Rendering a dry-run manifest"
helm template gpu-telemetry "${CHART_DIR}" \
  -f "${CHART_DIR}/values.yaml" \
  -f "${CHART_DIR}/values-dev.yaml" >/dev/null

echo "✔ Bootstrap complete."
echo "Next: helm install gpu-telemetry ${CHART_DIR} -n gpu-telemetry --create-namespace"
