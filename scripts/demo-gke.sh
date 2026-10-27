#!/bin/bash
#
# End-to-end GKE demo driver.
#
# Creates a disposable GKE cluster with a GPU node pool, installs the telemetry
# stack, deploys the demo workloads, waits for metrics to accumulate, captures a
# snapshot, and (optionally) tears everything down.
#
# Usage:
#   ./scripts/demo-gke.sh up          # provision + install + deploy workloads
#   ./scripts/demo-gke.sh snapshot    # capture metrics into demo/snapshots/
#   ./scripts/demo-gke.sh down        # destroy everything
#   ./scripts/demo-gke.sh status      # show cluster + workload state
#
# Environment:
#   GCP_PROJECT_ID   (required) GCP project that owns the demo cluster
#   GCP_REGION       (default: us-central1)
#   CLUSTER_NAME     (default: gpu-telemetry-demo)
#   NAMESPACE        (default: gpu-telemetry)
#   DEMO_NAMESPACE   (default: gpu-demo)
#   SKIP_TERRAFORM   (default: false) reuse an existing cluster
#   WAIT_SECONDS     (default: 300) metric warm-up before snapshot
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
TF_DIR="${ROOT_DIR}/terraform"
TF_INCLUSTER_DIR="${TF_DIR}/incluster"
CHART_DIR="${ROOT_DIR}/charts/gpu-telemetry-stack"
SNAPSHOT_DIR="${ROOT_DIR}/demo/snapshots"

GCP_PROJECT_ID="${GCP_PROJECT_ID:-}"
GCP_REGION="${GCP_REGION:-us-central1}"
CLUSTER_NAME="${CLUSTER_NAME:-gpu-telemetry-demo}"
CLUSTER_ZONE="${CLUSTER_ZONE:-${GCP_REGION}-a}"
NAMESPACE="${NAMESPACE:-gpu-telemetry}"
DEMO_NAMESPACE="${DEMO_NAMESPACE:-gpu-demo}"
SKIP_TERRAFORM="${SKIP_TERRAFORM:-false}"
WAIT_SECONDS="${WAIT_SECONDS:-300}"

log_info() { echo -e "\033[0;34m[INFO]\033[0m  $*"; }
log_ok()   { echo -e "\033[0;32m[ OK ]\033[0m  $*"; }
log_warn() { echo -e "\033[0;33m[WARN]\033[0m  $*"; }
log_fail() { echo -e "\033[0;31m[FAIL]\033[0m  $*"; }

require_project() {
  if [[ -z "${GCP_PROJECT_ID}" ]]; then
    log_fail "GCP_PROJECT_ID is not set."
    log_info "Export it first: export GCP_PROJECT_ID=your-project-id"
    exit 1
  fi
}

require_tools() {
  local missing=()
  for tool in gcloud kubectl helm terraform; do
    command -v "${tool}" >/dev/null 2>&1 || missing+=("${tool}")
  done
  if [[ ${#missing[@]} -gt 0 ]]; then
    log_fail "Missing required tools: ${missing[*]}"
    exit 1
  fi
}

write_tfvars() {
  local file="$1"
  cat >"${file}" <<EOF
gcp_project_id = "${GCP_PROJECT_ID}"
gcp_region     = "${GCP_REGION}"
cluster_name   = "${CLUSTER_NAME}"
EOF
}

cmd_up() {
  require_project
  require_tools

  log_info "Provisioning GKE cluster '${CLUSTER_NAME}' in ${CLUSTER_ZONE}..."
  write_tfvars "${TF_DIR}/terraform.tfvars"
  terraform -chdir="${TF_DIR}" init -input=false >/dev/null
  terraform -chdir="${TF_DIR}" apply -auto-approve -input=false \
    -var-file=terraform.tfvars

  log_info "Fetching cluster credentials..."
  gcloud container clusters get-credentials "${CLUSTER_NAME}" \
    --zone "${CLUSTER_ZONE}" --project "${GCP_PROJECT_ID}"

  log_info "Waiting for the GPU node pool to become ready..."
  kubectl wait --for=condition=Ready nodes \
    -l workload=gpu-telemetry --timeout=900s || \
    log_warn "GPU nodes not Ready yet; continuing anyway."

  log_info "Installing the telemetry stack via Terraform (in-cluster root)..."
  write_tfvars "${TF_INCLUSTER_DIR}/terraform.tfvars"
  cat >>"${TF_INCLUSTER_DIR}/terraform.tfvars" <<EOF
cluster_location       = "${CLUSTER_ZONE}"
namespace              = "${NAMESPACE}"
demo_namespace         = "${DEMO_NAMESPACE}"
install_demo_workloads = true
EOF
  terraform -chdir="${TF_INCLUSTER_DIR}" init -input=false >/dev/null
  terraform -chdir="${TF_INCLUSTER_DIR}" apply -auto-approve -input=false \
    -var-file=terraform.tfvars

  log_ok "Demo environment is up."
  log_info "Grafana:    kubectl port-forward -n ${NAMESPACE} svc/gpu-telemetry-grafana 3000:80"
  log_info "Prometheus: kubectl port-forward -n ${NAMESPACE} svc/gpu-telemetry-prometheus-kube-prometheus-prometheus 9090:9090"
  log_info "Next: ./scripts/demo-gke.sh snapshot"
}

cmd_snapshot() {
  require_project
  require_tools

  log_info "Waiting ${WAIT_SECONDS}s for metrics to accumulate..."
  sleep "${WAIT_SECONDS}"

  mkdir -p "${SNAPSHOT_DIR}"
  local stamp
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  local out="${SNAPSHOT_DIR}/snapshot-${stamp}.json"

  log_info "Port-forwarding Prometheus..."
  kubectl port-forward -n "${NAMESPACE}" \
    svc/gpu-telemetry-prometheus-kube-prometheus-prometheus 9090:9090 \
    >/dev/null 2>&1 &
  local pf_pid=$!
  trap 'kill ${pf_pid} 2>/dev/null || true' EXIT

  for _ in $(seq 1 30); do
    if curl -sf http://localhost:9090/-/ready >/dev/null 2>&1; then break; fi
    sleep 1
  done

  log_info "Capturing metrics snapshot -> ${out}"
  python3 "${SCRIPT_DIR}/collect-demo-metrics.py" \
    --prometheus-url http://localhost:9090 \
    --cluster "${CLUSTER_NAME}" \
    --output "${out}"

  log_ok "Snapshot written to ${out}"
  log_info "Render charts: python3 scripts/render-demo-charts.py --input ${out}"
}

cmd_status() {
  require_project
  require_tools

  log_info "Nodes:"
  kubectl get nodes -o wide || true
  echo ""
  log_info "Telemetry stack (${NAMESPACE}):"
  kubectl get pods -n "${NAMESPACE}" || true
  echo ""
  log_info "Demo workloads (${DEMO_NAMESPACE}):"
  kubectl get pods -n "${DEMO_NAMESPACE}" || true
}

cmd_down() {
  require_project
  require_tools

  log_warn "Destroying the demo cluster '${CLUSTER_NAME}'..."
  if [[ -f "${TF_INCLUSTER_DIR}/terraform.tfvars" ]]; then
    terraform -chdir="${TF_INCLUSTER_DIR}" destroy -auto-approve -input=false \
      -var-file=terraform.tfvars || log_warn "In-cluster destroy reported errors."
  fi
  if [[ -f "${TF_DIR}/terraform.tfvars" ]]; then
    terraform -chdir="${TF_DIR}" destroy -auto-approve -input=false \
      -var-file=terraform.tfvars
  fi
  log_ok "Demo environment destroyed."
}

usage() {
  cat <<EOF
Usage: $(basename "$0") <command>

Commands:
  up         Provision the GKE cluster, install the stack, deploy demo workloads
  snapshot   Capture a Prometheus metrics snapshot into demo/snapshots/
  status     Show cluster and workload state
  down       Destroy the demo cluster and all resources

Environment:
  GCP_PROJECT_ID   (required)
  GCP_REGION       default: us-central1
  CLUSTER_NAME     default: gpu-telemetry-demo
  NAMESPACE        default: gpu-telemetry
  DEMO_NAMESPACE   default: gpu-demo
  WAIT_SECONDS     default: 300
EOF
}

case "${1:-}" in
  up)       cmd_up ;;
  snapshot) cmd_snapshot ;;
  status)   cmd_status ;;
  down)     cmd_down ;;
  *)        usage; exit 1 ;;
esac
