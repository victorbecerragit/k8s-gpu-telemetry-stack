# Terraform roots

Each subfolder is an independent Terraform root module with its own state,
lock file, and `terraform.tfvars`.

| Folder | Purpose | Cloud |
| --- | --- | --- |
| `gke/` | VPC + subnet, zonal GKE cluster, `e2-standard-4` system pool, `g2-standard-4` + `nvidia-l4` GPU pool (tainted) | GCP |
| `eks/` | VPC, EKS cluster, `m6i.large` system node group, `g6.xlarge` GPU node group (tainted, Spot) | AWS |
| `incluster/` | Helm release of the telemetry chart + demo workloads | GCP or AWS |
| `old/` | Previous single-cloud GKE root, kept for reference only | — |

The cluster roots (`gke/`, `eks/`) provision the node pools the telemetry stack
expects: a `workload=observability` system pool and a `workload=gpu-telemetry`
GPU pool tainted `nvidia.com/gpu=present:NoSchedule`. The `incluster/` root
applies the matching chart overlay (`values-gke.yaml` / `values-eks.yaml`)
through the `cloud` variable.

## Usage

```bash
# GKE
cp terraform/gke/terraform.tfvars.example terraform/gke/terraform.tfvars
terraform -chdir=terraform/gke init
terraform -chdir=terraform/gke apply --var-file=terraform.tfvars
gcloud container clusters get-credentials gpu-telemetry-demo \
  --zone us-central1-a --project YOUR_GCP_PROJECT_ID

# EKS
cp terraform/eks/terraform.tfvars.example terraform/eks/terraform.tfvars
terraform -chdir=terraform/eks init
terraform -chdir=terraform/eks apply --var-file=terraform.tfvars
aws eks update-kubeconfig --name gpu-telemetry-demo --region us-west-2

# In-cluster stack (run after a cluster exists and kubectl is configured;
# set `cloud` in tfvars to gke or eks)
cp terraform/incluster/terraform.tfvars.example terraform/incluster/terraform.tfvars
terraform -chdir=terraform/incluster init
terraform -chdir=terraform/incluster apply --var-file=terraform.tfvars
```

For the scripted end-to-end GKE flow, use `./scripts/demo-gke.sh {up|status|snapshot|down}`.

Provider-specific setup notes live next to each root:

- `gke/setup.txt` — gcloud auth, API enablement, cluster credentials
- `eks/setup.txt` — AWS CLI config, GPU Spot quota increase, kubeconfig

## Notes

- State files and `.terraform/` caches are git-ignored per root.
- `incluster/` authenticates through the active kubeconfig context, so it
  targets whatever cluster `kubectl` is pointed at.
- Destroy order: `incluster/` first (removes the Helm release + workloads),
  then the cluster root.
