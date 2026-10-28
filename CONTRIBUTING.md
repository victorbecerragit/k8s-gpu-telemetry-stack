# Contributing

Thanks for taking the time to contribute. This project is a Helm chart plus a
demo environment, so most contributions fall into one of three buckets: chart
changes, telemetry/query changes, or documentation.

## Development setup

Requirements:

| Tool | Version | Why |
| --- | --- | --- |
| Helm | >= 3.15 | chart rendering and packaging |
| Python | >= 3.10 | test suite and demo tooling |
| Terraform | >= 1.5 | only if you touch `terraform/` |
| kubectl | any recent | only for the live demo |

```bash
git clone https://github.com/victorbecerragit/k8s-gpu-telemetry-stack.git
cd k8s-gpu-telemetry-stack

./scripts/build-deps.sh   # recursive dependency build (required)
./scripts/lint.sh         # lint root chart + every sub-chart
python3 -m pytest -q      # full test suite
```

> `helm dependency build` on the root chart does **not** recurse into the
> wrapper sub-charts. Always use `./scripts/build-deps.sh`, otherwise the parent
> renders ~13 resources instead of ~178 and the tests fail with a confusing
> message.

## Before opening a pull request

1. `./scripts/lint.sh` passes.
2. `python3 -m pytest -q` passes.
3. If you changed the dashboard or alert rules, confirm the PromQL still
   matches the series the stack actually emits. The regression guards in
   `tests/test_dashboard_alerts.py` encode the important ones.
4. If you changed `demo/snapshots/example.json`, regenerate the SVGs:
   ```bash
   python3 scripts/render-demo-charts.py \
     --input demo/snapshots/example.json \
     --output-dir docs/images
   ```
   CI diffs `docs/images/` against a fresh render and fails on drift.

## Chart versioning

The chart follows [Semantic Versioning](https://semver.org/):

- **MAJOR** — breaking values changes (renamed or removed keys, changed defaults
  that alter behaviour).
- **MINOR** — new components, new values, new dashboards or alerts.
- **PATCH** — bug fixes, image bumps, documentation.

Bump `version` in `charts/gpu-telemetry-stack/Chart.yaml` in the same PR as the
change. Publishing is triggered by a `v*` git tag that matches the chart
version.

## Telemetry correctness

Two rules matter more than style:

1. **The eBPF gadget must be `profile_tcprtt`.** `trace_tcp` emits
   connect/accept/close events and carries no latency data.
2. **The exported series is `latency_bucket{otel_scope_name="gadget_tcp_latency_us"}`.**
   Not `gadget_tcp_latency_us_bucket`. Dashboards and alerts must query the real
   name.

If you add a metric, add a test that asserts the dashboard or alert references
it.

## Commit messages

[Conventional Commits](https://www.conventionalcommits.org/) are appreciated but
not enforced:

```text
feat(dcgm): add PCIe replay counter panel
fix(ebpf): use tcprtt datasource name in otel annotation
docs: clarify GKE quota requirements
```

## Reporting bugs

Open an issue with:

- chart version (`helm list -n gpu-telemetry`)
- Kubernetes distribution and version
- the rendered manifest for the affected component
  (`helm template ... --show-only charts/...`)
- relevant pod logs or `kubectl describe` output

## Security issues

Please do **not** open a public issue. See [SECURITY.md](SECURITY.md).
