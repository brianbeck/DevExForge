#!/usr/bin/env bash
set -euo pipefail

echo "=== DevExForge Deploy Repo Setup ==="
echo ""

# Collect configuration
read -p "GitHub username or org: " GITHUB_USER
read -p "Deploy repo name [DevExForge-deploy]: " DEPLOY_REPO
DEPLOY_REPO=${DEPLOY_REPO:-DevExForge-deploy}
read -p "Docker Hub username [${GITHUB_USER}]: " DOCKER_USER
DOCKER_USER=${DOCKER_USER:-${GITHUB_USER}}
read -p "Stage cluster context [beck-stage-admin@beck-stage]: " STAGE_CTX
STAGE_CTX=${STAGE_CTX:-beck-stage-admin@beck-stage}
read -p "Prod cluster context [beck-prod-admin@beck-prod]: " PROD_CTX
PROD_CTX=${PROD_CTX:-beck-prod-admin@beck-prod}
read -p "Domain for ingress [brianbeck.net]: " DOMAIN
DOMAIN=${DOMAIN:-brianbeck.net}
read -p "Keycloak internal URL [http://keycloak-service.keycloak.svc.cluster.local:8080]: " KC_URL
KC_URL=${KC_URL:-http://keycloak-service.keycloak.svc.cluster.local:8080}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DEPLOY_DIR="${PROJECT_DIR}/../${DEPLOY_REPO}"

if [ -d "$DEPLOY_DIR" ]; then
    echo ""
    echo "Error: ${DEPLOY_DIR} already exists."
    echo "Remove it first or choose a different name."
    exit 1
fi

echo ""
echo "Creating deploy repo at ${DEPLOY_DIR}..."
mkdir -p "${DEPLOY_DIR}"/{apps,environments/{stage,prod}}

# --- Argo CD Application: Stage ---
cat > "${DEPLOY_DIR}/apps/devexforge-stage.yaml" <<EOF
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: devexforge-stage
  namespace: argocd
  labels:
    app.kubernetes.io/part-of: devexforge
    environment: stage
spec:
  project: default
  source:
    repoURL: https://github.com/${GITHUB_USER}/DevExForge.git
    targetRevision: main
    path: deploy/helm/devexforge
    helm:
      valueFiles:
        - https://raw.githubusercontent.com/${GITHUB_USER}/${DEPLOY_REPO}/main/environments/stage/values.yaml
  destination:
    server: https://kubernetes.default.svc
    namespace: engineering-platform
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
      - ServerSideApply=true
EOF

# --- Argo CD Application: Prod ---
cat > "${DEPLOY_DIR}/apps/devexforge-prod.yaml" <<EOF
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: devexforge-prod
  namespace: argocd
  labels:
    app.kubernetes.io/part-of: devexforge
    environment: prod
spec:
  project: default
  source:
    repoURL: https://github.com/${GITHUB_USER}/DevExForge.git
    targetRevision: main
    path: deploy/helm/devexforge
    helm:
      valueFiles:
        - https://raw.githubusercontent.com/${GITHUB_USER}/${DEPLOY_REPO}/main/environments/prod/values.yaml
  destination:
    server: https://kubernetes.default.svc
    namespace: engineering-platform
  syncPolicy:
    syncOptions:
      - CreateNamespace=true
      - ServerSideApply=true
EOF

# --- Stage values (operator only) ---
cat > "${DEPLOY_DIR}/environments/stage/values.yaml" <<EOF
namespace: engineering-platform

api:
  enabled: false

portal:
  enabled: false

postgres:
  enabled: false

operator:
  image:
    repository: ${DOCKER_USER}/devexforge-operator
    tag: "latest"  # operator
    pullPolicy: Always
  replicas: 1
  resources:
    requests:
      cpu: 100m
      memory: 128Mi
    limits:
      cpu: 200m
      memory: 256Mi
  env:
    logLevel: INFO
    ingressNamespace: traefik
    argocdNamespace: argocd
EOF

# --- Prod values (full stack) ---
cat > "${DEPLOY_DIR}/environments/prod/values.yaml" <<EOF
namespace: engineering-platform

api:
  image:
    repository: ${DOCKER_USER}/devexforge-api
    tag: "latest"  # api
    pullPolicy: Always
  replicas: 2
  resources:
    requests:
      cpu: 100m
      memory: 128Mi
    limits:
      cpu: 500m
      memory: 256Mi
  env:
    databaseUrl: postgresql+asyncpg://devexforge:devexforge@devexforge-postgres:5432/devexforge
    keycloakUrl: ${KC_URL}
    keycloakRealm: teams
    keycloakClientId: devexforge-api
    corsOrigins: '["https://devexforge.${DOMAIN}"]'
    k8sInCluster: "true"
    k8sStageContext: ${STAGE_CTX}
    k8sProdContext: ${PROD_CTX}
  ingress:
    host: devexforge-api.${DOMAIN}

portal:
  image:
    repository: ${DOCKER_USER}/devexforge-portal
    tag: "latest"  # portal
    pullPolicy: Always
  replicas: 2
  resources:
    requests:
      cpu: 50m
      memory: 64Mi
    limits:
      cpu: 200m
      memory: 128Mi
  ingress:
    host: devexforge.${DOMAIN}

operator:
  image:
    repository: ${DOCKER_USER}/devexforge-operator
    tag: "latest"  # operator
    pullPolicy: Always
  replicas: 1
  resources:
    requests:
      cpu: 100m
      memory: 128Mi
    limits:
      cpu: 200m
      memory: 256Mi
  env:
    logLevel: INFO
    ingressNamespace: traefik
    argocdNamespace: argocd

postgres:
  enabled: true
  image:
    repository: postgres
    tag: "16-alpine"
  resources:
    requests:
      cpu: 100m
      memory: 256Mi
    limits:
      cpu: 500m
      memory: 512Mi
  storage:
    size: 10Gi
    storageClass: ""
  credentials:
    database: devexforge
    username: devexforge
    password: devexforge
EOF

# --- README ---
cat > "${DEPLOY_DIR}/README.md" <<EOF
# ${DEPLOY_REPO}

GitOps deployment repository for [DevExForge](https://github.com/${GITHUB_USER}/DevExForge). Managed by Argo CD.

## Structure

\`\`\`
${DEPLOY_REPO}/
  apps/
    devexforge-stage.yaml      # Stage cluster (auto-sync)
    devexforge-prod.yaml       # Prod cluster (manual sync)
  environments/
    stage/values.yaml          # Operator only
    prod/values.yaml           # Full stack: API, portal, operator, PostgreSQL
\`\`\`

## Argo CD Setup

\`\`\`bash
# Stage cluster
kubectl --context ${STAGE_CTX} apply -f apps/devexforge-stage.yaml

# Prod cluster
kubectl --context ${PROD_CTX} apply -f apps/devexforge-prod.yaml
\`\`\`

## Promoting to Production

1. Check the image tag in \`environments/stage/values.yaml\`
2. Update \`environments/prod/values.yaml\` with the same tag
3. Open a PR, get approval, merge
4. Sync in Argo CD: \`argocd app sync devexforge-prod\`
EOF

# --- .gitignore ---
echo ".DS_Store" > "${DEPLOY_DIR}/.gitignore"

# --- Init git ---
cd "${DEPLOY_DIR}"
git init
git add -A
git commit -m "Initial deploy repo structure"

echo ""
echo "=== Deploy repo created at ${DEPLOY_DIR} ==="
echo ""
echo "Next steps:"
echo "  1. Create a private repo on GitHub: ${GITHUB_USER}/${DEPLOY_REPO}"
echo "  2. Push:"
echo "     cd ${DEPLOY_DIR}"
echo "     git remote add origin git@github.com:${GITHUB_USER}/${DEPLOY_REPO}.git"
echo "     git branch -M main"
echo "     git push -u origin main"
echo "  3. Apply Argo CD Applications:"
echo "     kubectl --context ${STAGE_CTX} apply -f apps/devexforge-stage.yaml"
echo "     kubectl --context ${PROD_CTX} apply -f apps/devexforge-prod.yaml"
echo "  4. Set Travis CI env vars in the DevExForge repo:"
echo "     DOCKER_USERNAME, DOCKER_PASSWORD, GITHUB_TOKEN"
