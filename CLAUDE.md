  # DevExForge

  Developer Experience platform built on top of PlatformForge.

  ## Related Project
  - PlatformForge (~/src/PlatformForge) provides the underlying platform: Kubernetes clusters with Traefik (ingress), Argo CD (GitOps), Gatekeeper (policy), Falco (runtime security), Trivy Operator (vulnerability scanning), and Observability Stack (Prometheus, Grafana, Alertmanager).
  - DevExForge consumes PlatformForge services -- it does not manage infrastructure.

  ## Architecture Goals
  - Python API (FastAPI) for team/namespace management with long-term state storage
  - React Developer Portal with Keycloak identity management
  - K8s Operator that watches API state and reconciles cluster resources
  - CLI for developer self-service

  ## Existing Code
  - teams-management/ -- existing API, CLI, and developer portal (Keycloak-based)

  ## Infrastructure Available (from PlatformForge)
  - Stage cluster: beck-stage-admin@beck-stage
  - Prod cluster: beck-prod-admin@beck-prod
  - Traefik ingress: *.brianbeck.net
  - Argo CD: argocd-stage.brianbeck.net / argocd-prod.brianbeck.net
  - Grafana: grafana-stage.brianbeck.net / grafana-prod.brianbeck.net
  - Prometheus: prometheus-stage.brianbeck.net / prometheus-prod.brianbeck.net
  - Gatekeeper enforcing policies on application namespaces
  - Trivy Operator scanning all running workloads
