#!/bin/bash
set -euo pipefail

NAMESPACE="${NAMESPACE:-gpu-telemetry}"
LABEL_SELECTOR="app.kubernetes.io/name=ebpf-probes"

log_info()  { echo -e "\033[0;34m[INFO]\033[0m  $*"; }
log_ok()    { echo -e "\033[0;32m[PASS]\033[0m  $*"; }
log_fail()  { echo -e "\033[0;31m[FAIL]\033[0m  $*"; }

log_info "Checking eBPF probe pods in namespace '${NAMESPACE}'..."

PODS=$(kubectl get pods -n "${NAMESPACE}" -l "${LABEL_SELECTOR}" -o jsonpath='{.items[*].metadata.name}' 2>/dev/null || true)
if [[ -z "${PODS}" ]]; then
  log_fail "No eBPF probe pods found with selector '${LABEL_SELECTOR}'."
  exit 1
fi

FAIL=0
for POD in ${PODS}; do
  READY=$(kubectl get pod -n "${NAMESPACE}" "${POD}" -o jsonpath='{.status.containerStatuses[0].ready}')
  if [[ "${READY}" != "true" ]]; then
    log_fail "${POD} is not ready"
    FAIL=$((FAIL + 1))
    continue
  fi
  log_ok "${POD} is ready"

  # Verify the gadget trace process is actually running (not just a sleep placeholder)
  if kubectl exec -n "${NAMESPACE}" "${POD}" -- \
      sh -c 'pgrep -f "ig run|inspektor-gadget" >/dev/null 2>&1' 2>/dev/null; then
    log_ok "${POD} is running an active eBPF trace"
  else
    log_fail "${POD} has no active eBPF trace process"
    FAIL=$((FAIL + 1))
  fi
done

if [[ "${FAIL}" -gt 0 ]]; then
  log_fail "eBPF probe validation failed (${FAIL} issue(s))."
  exit 1
fi

log_ok "eBPF probe DaemonSet appears healthy."
