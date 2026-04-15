# DevExForge Operator

Kopf-based Kubernetes operator that watches `Team` and `Environment` custom
resources and reconciles the cluster state that backs a team namespace. One
instance is deployed per cluster via the DevExForge Helm chart.

See the top-level [README](../README.md) for how the API, CRDs, and operator
fit together.

## Watched Resources

| Kind          | API Group / Version                        |
| ------------- | ------------------------------------------ |
| `Team`        | `devexforge.brianbeck.net/v1alpha1`        |
| `Environment` | `devexforge.brianbeck.net/v1alpha1`        |

CRD manifests live in `../crds/`. Gatekeeper constraint *templates* (e.g.
`FalcoRootPrevention`, `VulnerabilityScan`) are owned by PlatformForge; the
operator only creates *instances* of those templates scoped to team
namespaces.

## What Gets Reconciled per Environment

| Resource                      | Details                                                                    |
| ----------------------------- | -------------------------------------------------------------------------- |
| Namespace                     | Named `{team-slug}-{tier}`, labeled with team and tier                     |
| `ResourceQuota`               | From the environment spec                                                  |
| `LimitRange`                  | From the environment spec                                                  |
| `NetworkPolicy`               | Default-deny plus ingress allowance and optional inter-namespace rules     |
| `RoleBinding`s                | Bind team members to `devexforge-namespace-admin` / `devexforge-namespace-viewer` ClusterRoles |
| Gatekeeper constraint instances | `FalcoRootPrevention`, `VulnerabilityScan` scoped to the namespace       |
| Argo CD `AppProject`          | Scoped to the team namespace, repos, and destination cluster               |

### Phase 1 RBAC Tightening

The `devexforge-namespace-admin` ClusterRole intentionally does **not** grant
create/update/delete on `Deployments`, `StatefulSets`, or `ReplicaSets`. Team
members cannot mutate workloads directly with `kubectl` -- all changes must
flow through the DevExForge API, which writes Argo CD `Application` CRs.
This keeps the audit trail and promotion gates authoritative.

## Layout

| Path                                  | Contents                                          |
| ------------------------------------- | ------------------------------------------------- |
| `main.py`                             | Kopf entrypoint and startup/config                |
| `handlers/team_handler.py`            | `Team` create/update/delete handlers              |
| `handlers/environment_handler.py`    | `Environment` create/update/delete handlers      |
| `helpers.py`                          | Shared helpers: kube client init, name sanitization, quota/limit/rolebinding/networkpolicy/constraint/appproject builders |
| `deploy/`                             | Raw manifests for standalone / debugging use      |
| `Dockerfile`                          | Container image build                             |

## Local Development

The operator needs a kubeconfig with access to the target cluster. From the
repo root:

```bash
python operator/main.py
```

Kopf will fall back to `load_kube_config()` when not running in-cluster.
Tail the logs and edit a `Team` or `Environment` CR to exercise the
handlers.

## Deployment

Deployed via the DevExForge Helm chart (`../deploy/helm/devexforge/`), one
release per cluster. See the top-level README for the full install flow.
