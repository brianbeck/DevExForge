#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DEPLOY_DIR="${PROJECT_DIR}/../DevExForge-deploy"

STAGE_CTX="${STAGE_CTX:-beck-stage-admin@beck-stage}"
ARGOCD_SERVER="${ARGOCD_SERVER:-argocd-stage.brianbeck.net}"

# Argo CD CLI flags for self-signed certs behind Traefik
export ARGOCD_OPTS="--grpc-web --insecure"
ARGOCD_FLAGS="--server $ARGOCD_SERVER"

echo "=== DevExForge Stage Bootstrap ==="
echo ""
echo "Stage cluster context: ${STAGE_CTX}"
echo "Argo CD server:        ${ARGOCD_SERVER}"
echo ""

# Preflight checks
for cmd in kubectl argocd; do
    if ! command -v "$cmd" &>/dev/null; then
        echo "Error: $cmd is not installed"
        exit 1
    fi
done

if [ ! -d "$DEPLOY_DIR" ]; then
    echo "Error: Deploy repo not found at ${DEPLOY_DIR}"
    echo "Run ./dev/init-deploy-repo.sh first, or clone DevExForge-deploy alongside this repo."
    exit 1
fi

echo "--- Step 0: Log in to Argo CD ---"
argocd login "$ARGOCD_SERVER"
echo "Logged in to Argo CD."

echo ""
echo "--- Step 1: Verify cluster access ---"
if ! kubectl --context "$STAGE_CTX" cluster-info &>/dev/null; then
    echo "Error: Cannot connect to stage cluster with context ${STAGE_CTX}"
    exit 1
fi
echo "Connected to stage cluster."

echo ""
echo "--- Step 2: Apply CRDs ---"
kubectl --context "$STAGE_CTX" apply -f "${PROJECT_DIR}/crds/"
echo "CRDs applied."

echo ""
echo "--- Step 3: Create engineering-platform namespace ---"
kubectl --context "$STAGE_CTX" create namespace engineering-platform --dry-run=client -o yaml \
  | kubectl --context "$STAGE_CTX" apply -f -
echo "Namespace ready."

echo ""
echo "--- Step 4: Add deploy repo to Argo CD ---"
echo "Checking if repo is already registered..."
if argocd repo get https://github.com/brianbeck/DevExForge-deploy.git $ARGOCD_FLAGS &>/dev/null 2>&1; then
    echo "Repo already registered in Argo CD."
else
    echo ""
    echo "The deploy repo needs to be added to Argo CD."
    echo "You need a GitHub PAT with read access to DevExForge-deploy."
    read -sp "GitHub PAT: " GITHUB_PAT
    echo ""
    argocd repo add https://github.com/brianbeck/DevExForge-deploy.git \
        --username x-access-token \
        --password "$GITHUB_PAT" \
        $ARGOCD_FLAGS
    echo "Repo added to Argo CD."
fi

echo ""
echo "--- Step 5: Also add source repo (for Helm chart) ---"
if argocd repo get https://github.com/brianbeck/DevExForge.git $ARGOCD_FLAGS &>/dev/null 2>&1; then
    echo "Source repo already registered."
else
    echo "Adding public source repo..."
    argocd repo add https://github.com/brianbeck/DevExForge.git \
        $ARGOCD_FLAGS || true
    echo "Source repo added."
fi

echo ""
echo "--- Step 6: Apply Argo CD Application ---"
kubectl --context "$STAGE_CTX" apply -f "${DEPLOY_DIR}/apps/devexforge-stage.yaml"
echo "Argo CD Application created."

echo ""
echo "--- Step 7: Wait for sync ---"
echo "Waiting for Argo CD to sync (up to 120s)..."
argocd app wait devexforge-stage \
    $ARGOCD_FLAGS \
    --timeout 120 \
    --health || echo "Warning: Sync not complete yet. Check Argo CD dashboard."

echo ""
echo "--- Step 8: Verify operator is running ---"
echo "Checking operator pod..."
kubectl --context "$STAGE_CTX" -n engineering-platform get pods -l app.kubernetes.io/name=devexforge-operator

echo ""
echo "=== Bootstrap Complete ==="
echo ""
echo "Argo CD dashboard: https://${ARGOCD_SERVER}"
echo ""
echo "Next steps:"
echo "  1. Run smoke tests: ./dev/smoke-test-stage.sh"
echo "  2. When ready for prod: ./dev/bootstrap-prod.sh"
