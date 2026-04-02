#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DEPLOY_DIR="${PROJECT_DIR}/../DevExForge-deploy"

PROD_CTX="${PROD_CTX:-beck-prod-admin@beck-prod}"
ARGOCD_SERVER="${ARGOCD_SERVER:-argocd-prod.brianbeck.net}"

export ARGOCD_OPTS="--grpc-web --insecure"
ARGOCD_FLAGS="--server $ARGOCD_SERVER"

echo "=== DevExForge Production Bootstrap ==="
echo ""
echo "Prod cluster context: ${PROD_CTX}"
echo "Argo CD server:       ${ARGOCD_SERVER}"
echo ""

for cmd in kubectl argocd; do
    if ! command -v "$cmd" &>/dev/null; then
        echo "Error: $cmd is not installed"
        exit 1
    fi
done

if [ ! -d "$DEPLOY_DIR" ]; then
    echo "Error: Deploy repo not found at ${DEPLOY_DIR}"
    exit 1
fi

echo "--- Step 0: Log in to Argo CD ---"
argocd login "$ARGOCD_SERVER"
echo "Logged in to Argo CD."

echo ""
echo "--- Step 1: Verify cluster access ---"
if ! kubectl --context "$PROD_CTX" cluster-info &>/dev/null; then
    echo "Error: Cannot connect to prod cluster with context ${PROD_CTX}"
    exit 1
fi
echo "Connected to prod cluster."

echo ""
echo "--- Step 2: Apply CRDs ---"
kubectl --context "$PROD_CTX" apply -f "${PROJECT_DIR}/crds/"
echo "CRDs applied."

echo ""
echo "--- Step 3: Create engineering-platform namespace ---"
kubectl --context "$PROD_CTX" create namespace engineering-platform --dry-run=client -o yaml \
  | kubectl --context "$PROD_CTX" apply -f -
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
kubectl --context "$PROD_CTX" apply -f "${DEPLOY_DIR}/apps/devexforge-prod.yaml"
echo "Argo CD Application created."

echo ""
echo "--- Step 7: Sync (production is manual) ---"
read -p "Sync now? [y/N] " SYNC
if [[ "$SYNC" =~ ^[Yy]$ ]]; then
    argocd app sync devexforge-prod $ARGOCD_FLAGS
    echo "Waiting for sync (up to 180s)..."
    argocd app wait devexforge-prod \
        $ARGOCD_FLAGS \
        --timeout 180 \
        --health || echo "Warning: Sync not complete yet. Check Argo CD dashboard."
else
    echo "Skipped. Run manually: argocd app sync devexforge-prod $ARGOCD_FLAGS"
fi

echo ""
echo "--- Step 8: Verify pods ---"
kubectl --context "$PROD_CTX" -n engineering-platform get pods

echo ""
echo "=== Bootstrap Complete ==="
echo ""
echo "Argo CD dashboard: https://${ARGOCD_SERVER}"
echo ""
echo "Next steps:"
echo "  1. Run smoke tests: ./dev/smoke-test-prod.sh"
echo "  2. Run Alembic migrations against the prod database"
