#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHART_DIR="${SCRIPT_DIR}/../charts/gpu-telemetry-stack"

# Ensure nested wrapper sub-charts are populated before linting, otherwise the
# parent chart lints against empty wrappers and renders almost nothing.
if [[ "${SKIP_DEPS:-false}" != "true" ]]; then
  echo "==> Building chart dependencies (recursive)"
  "${SCRIPT_DIR}/build-deps.sh"
  echo ""
fi

echo "==> Linting parent chart..."
helm lint "${CHART_DIR}"

echo ""
echo "==> Linting sub-charts..."
for subchart in "${CHART_DIR}"/charts/*/; do
  if [[ -f "${subchart}/Chart.yaml" ]]; then
    echo "  -> $(basename "${subchart}")"
    helm lint "${subchart}"
  fi
done

echo ""
echo "✔ All charts passed linting."
