#!/bin/bash
#
# Recursively build Helm chart dependencies.
#
# `helm dependency build` only resolves the dependencies of the chart you point
# it at. The wrapper sub-charts (prometheus, grafana, gpu-operator) vendor their
# own upstream charts, so building only the root chart leaves those wrappers
# empty and the rendered output silently collapses to a handful of resources.
#
# This script walks the tree bottom-up so every chart is built before its parent.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
CHART_DIR="${ROOT_DIR}/charts/gpu-telemetry-stack"

echo "==> Adding required Helm repositories"
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts >/dev/null 2>&1 || true
helm repo add grafana https://grafana.github.io/helm-charts >/dev/null 2>&1 || true
helm repo add nvidia https://helm.ngc.nvidia.com/nvidia >/dev/null 2>&1 || true
helm repo update >/dev/null

# Build a chart and, first, every chart nested beneath it.
build_recursive() {
  local chart="$1"

  # Recurse into nested charts first (deepest dependencies build first).
  local nested
  for nested in "${chart}"/charts/*/; do
    [[ -d "${nested}" && -f "${nested}/Chart.yaml" ]] || continue
    build_recursive "${nested%/}"
  done

  if grep -q "^dependencies:" "${chart}/Chart.yaml" 2>/dev/null; then
    # `helm dependency build` reuses an existing .tgz when the lock digest still
    # matches, so edits inside a local sub-chart directory are silently ignored
    # and the stale package keeps shadowing the source. Drop the local packages
    # first so they are always rebuilt from the working tree.
    local dep
    while IFS= read -r dep; do
      [[ -n "${dep}" ]] || continue
      rm -f "${chart}/charts/${dep}"-*.tgz
    done < <(
      awk '
        /^dependencies:/ { in_deps = 1; next }
        in_deps && /^[^[:space:]-]/ { in_deps = 0 }
        in_deps && /^[[:space:]]*-[[:space:]]*name:/ { name = $3 }
        in_deps && /repository:[[:space:]]*file:/ && name { print name; name = "" }
      ' "${chart}/Chart.yaml"
    )

    echo "  -> building $(basename "${chart}")"
    helm dependency build "${chart}" >/dev/null
  fi
}

echo "==> Building chart dependencies (recursive)"
build_recursive "${CHART_DIR}"

echo "✔ All chart dependencies built."
