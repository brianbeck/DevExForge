#!/usr/bin/env bash
set -uo pipefail

PROD_CTX="${PROD_CTX:-beck-prod-admin@beck-prod}"
API_URL="${API_URL:-https://devexforge-api.brianbeck.net}"
PORTAL_URL="${PORTAL_URL:-https://devexforge.brianbeck.net}"
KEYCLOAK_URL="${KEYCLOAK_URL:-https://keycloak.brianbeck.net}"
CRD_GROUP="devexforge.brianbeck.net"
TEST_TEAM="smoke-test-prod"
TEST_TIER="production"
NAMESPACE="${TEST_TEAM}-${TEST_TIER}"

PASSED=0
FAILED=0
TESTS=()

pass() {
    PASSED=$((PASSED + 1))
    TESTS+=("PASS: $1")
    echo "  PASS: $1"
}

fail() {
    FAILED=$((FAILED + 1))
    TESTS+=("FAIL: $1")
    echo "  FAIL: $1"
}

echo "=== DevExForge Production Smoke Tests ==="
echo ""
echo "Cluster: ${PROD_CTX}"
echo "API:     ${API_URL}"
echo "Portal:  ${PORTAL_URL}"
echo ""

# --- Infrastructure ---
echo "--- Infrastructure ---"

# Cluster access
if kubectl --context "$PROD_CTX" cluster-info &>/dev/null; then
    pass "Cluster reachable"
else
    fail "Cluster reachable"
fi

# CRDs
if kubectl --context "$PROD_CTX" get crd teams.${CRD_GROUP} &>/dev/null; then
    pass "Team CRD installed"
else
    fail "Team CRD installed"
fi

if kubectl --context "$PROD_CTX" get crd environments.${CRD_GROUP} &>/dev/null; then
    pass "Environment CRD installed"
else
    fail "Environment CRD installed"
fi

# Pods
echo ""
echo "--- Pods ---"

POD_PHASE=$(kubectl --context "$PROD_CTX" -n engineering-platform get pods -l app.kubernetes.io/name=devexforge-operator -o jsonpath='{.items[0].status.phase}' 2>/dev/null || echo "")
if [ "$POD_PHASE" = "Running" ]; then
    pass "Operator pod running"
else
    fail "Operator pod status is '${POD_PHASE}'"
fi

POD_PHASE=$(kubectl --context "$PROD_CTX" -n engineering-platform get pods -l app.kubernetes.io/name=devexforge-api -o jsonpath='{.items[0].status.phase}' 2>/dev/null || echo "")
if [ "$POD_PHASE" = "Running" ]; then
    pass "API pod running"
else
    fail "API pod status is '${POD_PHASE}'"
fi

POD_PHASE=$(kubectl --context "$PROD_CTX" -n engineering-platform get pods -l app.kubernetes.io/name=devexforge-portal -o jsonpath='{.items[0].status.phase}' 2>/dev/null || echo "")
if [ "$POD_PHASE" = "Running" ]; then
    pass "Portal pod running"
else
    fail "Portal pod status is '${POD_PHASE}'"
fi

POD_PHASE=$(kubectl --context "$PROD_CTX" -n engineering-platform get pods -l app.kubernetes.io/name=devexforge-postgres -o jsonpath='{.items[0].status.phase}' 2>/dev/null || echo "")
if [ "$POD_PHASE" = "Running" ]; then
    pass "PostgreSQL pod running"
else
    fail "PostgreSQL pod status is '${POD_PHASE}'"
fi

# --- API Health ---
echo ""
echo "--- API Health ---"

HEALTH=$(curl -sk "${API_URL}/health" 2>/dev/null || echo "")
if echo "$HEALTH" | grep -q "healthy"; then
    pass "API health endpoint"
else
    fail "API health endpoint (got: ${HEALTH})"
fi

READY=$(curl -sk "${API_URL}/ready" 2>/dev/null || echo "")
if echo "$READY" | grep -q "ready"; then
    pass "API readiness (database connected)"
else
    fail "API readiness (got: ${READY})"
fi

# --- Portal ---
echo ""
echo "--- Portal ---"

PORTAL_STATUS=$(curl -sko /dev/null -w "%{http_code}" "${PORTAL_URL}/" 2>/dev/null || echo "000")
if [ "$PORTAL_STATUS" = "200" ]; then
    pass "Portal reachable (HTTP ${PORTAL_STATUS})"
else
    fail "Portal returned HTTP ${PORTAL_STATUS}"
fi

# --- API Auth Flow ---
echo ""
echo "--- API Auth Flow ---"

TOKEN=$(curl -sk -X POST "${KEYCLOAK_URL}/realms/teams/protocol/openid-connect/token" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "grant_type=password&client_id=devexforge-portal&username=admin&password=admin123" \
    2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null || echo "")

if [ -n "$TOKEN" ] && [ "$TOKEN" != "" ]; then
    pass "Keycloak token acquired"
else
    fail "Keycloak token acquisition"
    # Can't continue API tests without a token
    echo ""
    echo "=== Results ==="
    echo ""
    for t in "${TESTS[@]}"; do echo "  $t"; done
    echo ""
    echo "Passed: ${PASSED}  Failed: ${FAILED}  Total: $((PASSED + FAILED))"
    exit 1
fi

# List teams
TEAMS_RESP=$(curl -sk -H "Authorization: Bearer $TOKEN" "${API_URL}/api/v1/teams" 2>/dev/null || echo "")
if echo "$TEAMS_RESP" | grep -q "teams"; then
    pass "API list teams"
else
    fail "API list teams (got: ${TEAMS_RESP})"
fi

# --- Operator Reconciliation ---
echo ""
echo "--- Operator Reconciliation ---"

# Clean up previous test
kubectl --context "$PROD_CTX" delete team "$TEST_TEAM" --ignore-not-found &>/dev/null
kubectl --context "$PROD_CTX" delete environment "$NAMESPACE" --ignore-not-found &>/dev/null
kubectl --context "$PROD_CTX" delete namespace "$NAMESPACE" --ignore-not-found --wait=false &>/dev/null
sleep 3

# Create Team CRD
kubectl --context "$PROD_CTX" apply -f - <<EOF
apiVersion: ${CRD_GROUP}/v1alpha1
kind: Team
metadata:
  name: ${TEST_TEAM}
spec:
  displayName: Prod Smoke Test
  owner:
    email: smoketest@company.com
  members:
    - email: smoketest@company.com
      role: admin
EOF

if kubectl --context "$PROD_CTX" get team "$TEST_TEAM" &>/dev/null; then
    pass "Team CRD created"
else
    fail "Team CRD created"
fi

sleep 10

TEAM_PHASE=$(kubectl --context "$PROD_CTX" get team "$TEST_TEAM" -o jsonpath='{.status.phase}' 2>/dev/null || echo "")
if [ "$TEAM_PHASE" = "Active" ]; then
    pass "Team status Active"
else
    fail "Team status is '${TEAM_PHASE}'"
fi

# Create Environment CRD
kubectl --context "$PROD_CTX" apply -f - <<EOF
apiVersion: ${CRD_GROUP}/v1alpha1
kind: Environment
metadata:
  name: ${NAMESPACE}
spec:
  teamRef: ${TEST_TEAM}
  tier: ${TEST_TIER}
  cluster: beck-prod
  resourceQuota:
    cpuRequest: "1"
    cpuLimit: "2"
    memoryRequest: "1Gi"
    memoryLimit: "2Gi"
    pods: 5
  policies:
    requireNonRoot: true
    requireReadOnlyRoot: true
    maxCriticalCVEs: 0
    maxHighCVEs: 0
    requireResourceLimits: true
  argoCD:
    enabled: false
EOF

if kubectl --context "$PROD_CTX" get environment "$NAMESPACE" &>/dev/null; then
    pass "Environment CRD created"
else
    fail "Environment CRD created"
fi

echo "  Waiting for reconciliation (30s)..."
sleep 30

ENV_PHASE=$(kubectl --context "$PROD_CTX" get environment "$NAMESPACE" -o jsonpath='{.status.phase}' 2>/dev/null || echo "")
if [ "$ENV_PHASE" = "Active" ]; then
    pass "Environment status Active"
else
    fail "Environment status is '${ENV_PHASE}'"
fi

if kubectl --context "$PROD_CTX" get namespace "$NAMESPACE" &>/dev/null; then
    pass "Namespace created"
else
    fail "Namespace created"
fi

if kubectl --context "$PROD_CTX" -n "$NAMESPACE" get resourcequota default &>/dev/null; then
    pass "ResourceQuota created"
else
    fail "ResourceQuota created"
fi

# --- Cleanup ---
echo ""
echo "--- Cleanup ---"
kubectl --context "$PROD_CTX" delete environment "$NAMESPACE" --ignore-not-found
kubectl --context "$PROD_CTX" delete team "$TEST_TEAM" --ignore-not-found
echo "  Waiting for cleanup (15s)..."
sleep 15

if kubectl --context "$PROD_CTX" get namespace "$NAMESPACE" &>/dev/null; then
    fail "Namespace cleaned up"
else
    pass "Namespace cleaned up"
fi

# --- Results ---
echo ""
echo "=== Results ==="
echo ""
for t in "${TESTS[@]}"; do
    echo "  $t"
done
echo ""
echo "Passed: ${PASSED}  Failed: ${FAILED}  Total: $((PASSED + FAILED))"
echo ""

if [ "$FAILED" -gt 0 ]; then
    echo "SMOKE TESTS FAILED"
    exit 1
else
    echo "ALL SMOKE TESTS PASSED"
fi
