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
- Tier-to-cluster mapping: dev/staging -> beck-stage, production -> beck-prod.
- Application promotion via Argo CD Application CRs (forward-only: dev -> staging -> production).

## Infrastructure Available (from PlatformForge)
- Stage cluster: beck-stage-admin@beck-stage
- Prod cluster: beck-prod-admin@beck-prod
- Traefik ingress: *.brianbeck.net
- Argo CD: argocd-stage.brianbeck.net / argocd-prod.brianbeck.net
- Grafana: grafana-stage.brianbeck.net / grafana-prod.brianbeck.net
- Prometheus: prometheus-stage.brianbeck.net / prometheus-prod.brianbeck.net
- Gatekeeper enforcing policies on application namespaces
- Trivy Operator scanning all running workloads

## Local Development
```bash
./dev/setup.sh           # Start Postgres + Keycloak, install deps, run migrations
cd api && uvicorn app.main:app --reload   # API on :8000
cd portal && npm run dev                   # Portal on :5173
```
