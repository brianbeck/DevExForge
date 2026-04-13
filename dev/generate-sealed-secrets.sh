#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DEPLOY_DIR="${PROJECT_DIR}/../DevExForge-deploy"

echo "=== DevExForge Sealed Secrets Generator ==="
echo ""
echo "This script generates SealedSecrets for a target cluster."
echo "Requires: kubeseal CLI (brew install kubeseal)"
echo ""

if ! command -v kubeseal &>/dev/null; then
    echo "Error: kubeseal is not installed. Run: brew install kubeseal"
    exit 1
fi

# Select environment
read -p "Environment [stage/prod]: " ENV
if [[ "$ENV" != "stage" && "$ENV" != "prod" ]]; then
    echo "Error: must be 'stage' or 'prod'"
    exit 1
fi

if [[ "$ENV" == "stage" ]]; then
    CONTEXT="beck-stage-admin@beck-stage"
    EP_NAMESPACE="engineering-platform"
    KC_NAMESPACE="keycloak"
else
    CONTEXT="beck-prod-admin@beck-prod"
    EP_NAMESPACE="engineering-platform"
    KC_NAMESPACE="keycloak"
fi

OUTPUT_DIR="${DEPLOY_DIR}/environments/${ENV}/sealed-secrets"
mkdir -p "$OUTPUT_DIR"

echo ""
echo "Cluster context: ${CONTEXT}"
echo "Output: ${OUTPUT_DIR}"
echo ""

# --- Collect credentials ---
read -p "PostgreSQL username [devexforge]: " PG_USER
PG_USER=${PG_USER:-devexforge}
read -sp "PostgreSQL password: " PG_PASS
echo ""

read -p "PostgreSQL database [devexforge]: " PG_DB
PG_DB=${PG_DB:-devexforge}

read -p "Keycloak DB username [keycloak]: " KC_DB_USER
KC_DB_USER=${KC_DB_USER:-keycloak}
read -sp "Keycloak DB password: " KC_DB_PASS
echo ""

read -sp "Keycloak admin password: " KC_ADMIN_PASS
echo ""

DATABASE_URL="postgresql+asyncpg://${PG_USER}:${PG_PASS}@devexforge-postgres:5432/${PG_DB}"

# Fetch the sealing public key from the controller
echo "Fetching sealing certificate from cluster..."
CERT_FILE=$(mktemp)
kubeseal --controller-name=sealed-secrets-controller \
  --controller-namespace=sealed-secrets \
  --context="${CONTEXT}" \
  --fetch-cert > "$CERT_FILE" 2>/dev/null || \
  kubectl --context="${CONTEXT}" -n sealed-secrets get secret \
    -l sealedsecrets.bitnami.com/sealed-secrets-key \
    -o jsonpath='{.items[0].data.tls\.crt}' | base64 -d > "$CERT_FILE"

KUBESEAL_OPTS="--cert=${CERT_FILE} --format=yaml"

echo ""
echo "Generating SealedSecrets..."

# --- DevExForge API credentials (engineering-platform namespace) ---
kubectl create secret generic devexforge-api-credentials \
    --namespace="$EP_NAMESPACE" \
    --from-literal="database-url=${DATABASE_URL}" \
    --dry-run=client -o yaml \
  | kubeseal $KUBESEAL_OPTS > "${OUTPUT_DIR}/devexforge-api-credentials.yaml"
echo "  Created: devexforge-api-credentials.yaml"

# --- DevExForge PostgreSQL credentials (engineering-platform namespace) ---
kubectl create secret generic devexforge-postgres-credentials \
    --namespace="$EP_NAMESPACE" \
    --from-literal="POSTGRES_DB=${PG_DB}" \
    --from-literal="POSTGRES_USER=${PG_USER}" \
    --from-literal="POSTGRES_PASSWORD=${PG_PASS}" \
    --dry-run=client -o yaml \
  | kubeseal $KUBESEAL_OPTS > "${OUTPUT_DIR}/devexforge-postgres-credentials.yaml"
echo "  Created: devexforge-postgres-credentials.yaml"

# --- Keycloak DB credentials (keycloak namespace) ---
kubectl create secret generic keycloak-db-credentials \
    --namespace="$KC_NAMESPACE" \
    --from-literal="POSTGRES_DB=keycloak" \
    --from-literal="POSTGRES_USER=${KC_DB_USER}" \
    --from-literal="POSTGRES_PASSWORD=${KC_DB_PASS}" \
    --dry-run=client -o yaml \
  | kubeseal $KUBESEAL_OPTS > "${OUTPUT_DIR}/keycloak-db-credentials.yaml"
echo "  Created: keycloak-db-credentials.yaml"

# --- Keycloak admin credentials (keycloak namespace) ---
kubectl create secret generic keycloak-admin-credentials \
    --namespace="$KC_NAMESPACE" \
    --from-literal="admin-password=${KC_ADMIN_PASS}" \
    --dry-run=client -o yaml \
  | kubeseal $KUBESEAL_OPTS > "${OUTPUT_DIR}/keycloak-admin-credentials.yaml"
echo "  Created: keycloak-admin-credentials.yaml"

rm -f "$CERT_FILE"

echo ""
echo "=== Done ==="
echo ""
echo "SealedSecrets written to: ${OUTPUT_DIR}"
echo ""
echo "Next steps:"
echo "  1. Enable in values: set sealedSecrets.enabled=true in environments/${ENV}/values.yaml"
echo "  2. Remove plaintext passwords from environments/${ENV}/values.yaml"
echo "  3. Commit and push DevExForge-deploy:"
echo "     cd ${DEPLOY_DIR}"
echo "     git add -A && git commit -m 'Add sealed secrets for ${ENV}' && git push"
echo "  4. Apply SealedSecrets to the cluster (or let Argo CD sync):"
echo "     kubectl --context ${CONTEXT} apply -f ${OUTPUT_DIR}/"
