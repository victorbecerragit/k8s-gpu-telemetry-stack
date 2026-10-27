#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHART_DIR="${SCRIPT_DIR}/../charts/gpu-telemetry-stack"

echo "==> Linting parent chart..."
helm lint "${CHART_DIR}"

echo ""
echo "==> Linting sub-charts..."
for subchart in "${CHART_DIR}"/charts/*/; do
  if [[ -f "${subchart}/Chart.yaml" ]]; then
    if grep -q "^dependencies:" "${subchart}/Chart.yaml"; then
      helm dependency build "${subchart}" >/dev/null
    fi
    echo "  -> $(basename "${subchart}")"
    helm lint "${subchart}"
  fi
done

echo ""
echo "✔ All charts passed linting."
