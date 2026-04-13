# DevExForge

Developer Experience platform built on top of PlatformForge.

## Related Project
- PlatformForge (~/src/PlatformForge) provides the underlying platform: Kubernetes clusters with Traefik (ingress), Argo CD (GitOps), Gatekeeper (policy), Falco (runtime security), Trivy Operator (vulnerability scanning), and Observability Stack (Prometheus, Grafana, Alertmanager).
- DevExForge consumes PlatformForge services -- it does not manage infrastructure.
- Gatekeeper constraint templates (FalcoRootPrevention, VulnerabilityScan) are defined and deployed by PlatformForge. The DevExForge operator creates constraint *instances* scoped to team namespaces.

## Architecture
- **API** (`api/`): FastAPI + PostgreSQL + Alembic, Keycloak JWT auth. Runs in production cluster, manages both stage and prod via multi-cluster kubeconfig.
- **Portal** (`portal/`): Vite + React + TypeScript with Keycloak auth.
- **Operator** (`operator/`): Kopf-based K8s operator. Deployed per-cluster. Watches Team/Environment CRDs and reconciles namespaces, quotas, RBAC, NetworkPolicies, Gatekeeper constraints, and Argo CD AppProjects.
- **CLI** (`cli/`): Python CLI with Click and Rich.
- **CRDs** (`crds/`): Team and Environment custom resources (`devexforge.brianbeck.net/v1alpha1`).
- **Helm Chart** (`deploy/helm/devexforge/`): Full deployment chart.

## Key Design Decisions
- API-first with CRD as projection (API writes PostgreSQL, then syncs CRDs to cluster).
- Tiered policy floors: platform enforces minimum security per tier (dev < staging < production). Teams can only make policies stricter.
- Namespace naming: `{team-slug}-{tier}` (e.g. `backend-platform-dev`).
- Tier-to-cluster mapping configurable via TIER_CLUSTER_MAP env var.
- Application promotion via Argo CD Application CRs (forward-only: dev -> staging -> production).
- Secrets managed via Sealed Secrets (encrypted in Git, decrypted by controller in cluster).
- TLS certificates managed by cert-manager with Let's Encrypt.

## Infrastructure Available (from PlatformForge)
- Stage and prod Kubernetes clusters (contexts configured in kubeconfig)
- Traefik ingress controller
- Argo CD for GitOps
- Grafana, Prometheus, Alertmanager for observability
- Gatekeeper enforcing policies on application namespaces
- Trivy Operator scanning all running workloads
- Sealed Secrets controller for secret management
- cert-manager with Let's Encrypt ClusterIssuer

## Configuration
- Environment-specific values are in the private DevExForge-deploy repo
- Hostnames, cluster contexts, and credentials are NOT stored in this public repo
- Default values.yaml uses example.com placeholders

## Local Development
```bash
./dev/setup.sh           # Start Postgres + Keycloak, install deps, run migrations
cd api && uvicorn app.main:app --reload   # API on :8000
cd portal && npm run dev                   # Portal on :5173
```
