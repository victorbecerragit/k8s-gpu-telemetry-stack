#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# -- Configuration (override via env vars)
NAMESPACE="${NAMESPACE:-gpu-telemetry}"
DCGM_PORT="${DCGM_PORT:-9400}"
METRICS_PATH="${METRICS_PATH:-/metrics}"
EXPECTED_METRICS=(
  "DCGM_FI_DEV_SM_CLOCK"
  "DCGM_FI_DEV_GPU_UTIL"
  "DCGM_FI_DEV_MEM_COPY_UTIL"
  "DCGM_FI_DEV_FB_USED"
  "DCGM_FI_DEV_FB_FREE"
  "DCGM_FI_DEV_PCIE_TX_THROUGHPUT"
  "DCGM_FI_DEV_PCIE_RX_THROUGHPUT"
  "DCGM_FI_DEV_GPU_TEMP"
  "DCGM_FI_DEV_XID_ERRORS"
)

PASS=0
FAIL=0
WARN=0

log_info()  { echo -e "\033[0;34m[INFO]\033[0m  $*"; }
log_ok()    { echo -e "\033[0;32m[PASS]\033[0m  $*"; }
log_fail()  { echo -e "\033[0;31m[FAIL]\033[0m  $*"; }
log_warn()  { echo -e "\033[0;33m[WARN]\033[0m  $*"; }

# -- Discover DCGM exporter pods
log_info "Discovering DCGM Exporter pods in namespace '${NAMESPACE}'..."
PODS=$(kubectl get pods -n "${NAMESPACE}" \
  -l app.kubernetes.io/name=dcgm-exporter \
  -o jsonpath='{.items[*].metadata.name}' 2>/dev/null || true)

if [[ -z "${PODS}" ]]; then
  log_fail "No DCGM Exporter pods found in namespace '${NAMESPACE}'."
  log_info "Ensure the GPU telemetry stack is deployed and the namespace is correct."
  exit 1
fi

log_info "Found pods: ${PODS}"

# -- Scrape and validate each pod
for POD in ${PODS}; do
  log_info "--------------------------------------"
  log_info "Validating pod: ${POD}"

  METRICS_OUTPUT=$(kubectl exec -n "${NAMESPACE}" "${POD}" -- \
    wget -qO- "http://localhost:${DCGM_PORT}${METRICS_PATH}" 2>/dev/null || true)

  if [[ -z "${METRICS_OUTPUT}" ]]; then
    log_fail "Could not scrape metrics from ${POD}:${DCGM_PORT}${METRICS_PATH}"
    FAIL=$((FAIL + 1))
    continue
  fi

  for METRIC in "${EXPECTED_METRICS[@]}"; do
    if echo "${METRICS_OUTPUT}" | grep -q "^${METRIC}"; then
      log_ok "${METRIC} — present"
      PASS=$((PASS + 1))
    else
      log_warn "${METRIC} — NOT FOUND (may require active GPU workload)"
      WARN=$((WARN + 1))
    fi
  done
done

# -- Summary
echo ""
log_info "======================================"
log_info "Validation Summary"
log_info "======================================"
log_info "  Passed : ${PASS}"
log_info "  Warnings: ${WARN}"
log_info "  Failed : ${FAIL}"

if [[ "${FAIL}" -gt 0 ]]; then
  log_fail "Validation completed with failures."
  exit 1
fi

log_ok "All checks passed."
exit 0
