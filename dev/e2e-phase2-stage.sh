#!/usr/bin/env bash
set -uo pipefail

STAGE_CTX="${STAGE_CTX:-beck-stage-admin@beck-stage}"
API_URL="${API_URL:-https://devexforge-api-stage.brianbeck.net}"
KEYCLOAK_URL="${KEYCLOAK_URL:-https://keycloak-stage.brianbeck.net}"

TEST_TEAM="e2e-phase2"
TEST_APP="sample-api"
TEST_IMAGE_TAG="blue"

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

json_get() {
    # json_get <field> <json>
    python3 -c "import sys,json
try:
    d=json.loads(sys.argv[2])
    v=d
    for k in sys.argv[1].split('.'):
        if isinstance(v, list):
            v=v[int(k)]
        else:
            v=v.get(k) if v is not None else None
    if v is None:
        print('')
    else:
        print(v)
except Exception:
    print('')
" "$1" "$2" 2>/dev/null || echo ""
}

curl_api() {
    # curl_api METHOD PATH [BODY]
    local method="$1"
    local path="$2"
    local body="${3:-}"
    if [ -n "$body" ]; then
        curl -sk -X "$method" \
            -H "Authorization: Bearer $TOKEN" \
            -H "Content-Type: application/json" \
            -d "$body" \
            "${API_URL}${path}" 2>/dev/null
    else
        curl -sk -X "$method" \
            -H "Authorization: Bearer $TOKEN" \
            -H "Content-Type: application/json" \
            "${API_URL}${path}" 2>/dev/null
    fi
}

curl_api_status() {
    # curl_api_status METHOD PATH [BODY]  -> prints HTTP status
    local method="$1"
    local path="$2"
    local body="${3:-}"
    if [ -n "$body" ]; then
        curl -sko /dev/null -w "%{http_code}" -X "$method" \
            -H "Authorization: Bearer $TOKEN" \
            -H "Content-Type: application/json" \
            -d "$body" \
            "${API_URL}${path}" 2>/dev/null
    else
        curl -sko /dev/null -w "%{http_code}" -X "$method" \
            -H "Authorization: Bearer $TOKEN" \
            -H "Content-Type: application/json" \
            "${API_URL}${path}" 2>/dev/null
    fi
}

echo "=== DevExForge Phase 2 E2E Tests (Stage) ==="
echo ""
echo "Cluster: ${STAGE_CTX}"
echo "API:     ${API_URL}"
echo "Team:    ${TEST_TEAM}"
echo "App:     ${TEST_APP}"
echo ""

# --- 1. Get auth token ---
echo "--- 1. Auth ---"
TOKEN=$(curl -sk -X POST "${KEYCLOAK_URL}/realms/teams/protocol/openid-connect/token" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "grant_type=password&client_id=devexforge-portal&username=admin&password=admin123" \
    2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null || echo "")

if [ -n "$TOKEN" ]; then
    pass "Keycloak token acquired"
else
    fail "Keycloak token acquisition"
    echo ""
    echo "Cannot continue without token."
    exit 1
fi

# --- 2. Cleanup prior run ---
echo ""
echo "--- 2. Cleanup prior run ---"
PRIOR_STATUS=$(curl_api_status DELETE "/api/v1/teams/${TEST_TEAM}")
echo "  Prior cleanup DELETE status: ${PRIOR_STATUS}"
echo "  Waiting 15s for cascade..."
sleep 15
pass "Prior run cleanup attempted"

# --- 3. Create team ---
echo ""
echo "--- 3. Create team ---"
CREATE_TEAM_BODY=$(cat <<EOF
{
  "slug": "${TEST_TEAM}",
  "displayName": "E2E Phase2 Test Team",
  "description": "End-to-end test team for Phase 2",
  "owner": {"email": "e2e@example.com"},
  "members": [
    {"email": "admin@company.com", "role": "admin"},
    {"email": "e2e@example.com", "role": "admin"}
  ],
  "costCenter": "E2E-001",
  "tags": {"purpose": "e2e-phase2"}
}
EOF
)
TEAM_STATUS=$(curl_api_status POST "/api/v1/teams" "$CREATE_TEAM_BODY")
if [ "$TEAM_STATUS" = "201" ] || [ "$TEAM_STATUS" = "200" ]; then
    pass "Team created (HTTP ${TEAM_STATUS})"
else
    fail "Team create returned HTTP ${TEAM_STATUS}"
    # Dump the response body for debugging
    curl_api POST "/api/v1/teams" "$CREATE_TEAM_BODY" | head -c 500
    echo ""
fi

# --- 4. Create dev environment ---
echo ""
echo "--- 4. Create dev environment ---"
DEV_ENV_BODY=$(cat <<'EOF'
{
  "tier": "dev",
  "resourceQuota": {
    "cpuRequest": "1",
    "cpuLimit": "2",
    "memoryRequest": "1Gi",
    "memoryLimit": "2Gi",
    "pods": 10,
    "services": 5,
    "persistentVolumeClaims": 2
  },
  "limitRange": {
    "defaultCpuRequest": "100m",
    "defaultCpuLimit": "500m",
    "defaultMemoryRequest": "128Mi",
    "defaultMemoryLimit": "512Mi"
  },
  "networkPolicy": {
    "allowInterNamespace": false,
    "egressAllowInternet": true
  },
  "argoCD": {"enabled": true}
}
EOF
)
DEV_STATUS=$(curl_api_status POST "/api/v1/teams/${TEST_TEAM}/environments" "$DEV_ENV_BODY")
if [ "$DEV_STATUS" = "201" ] || [ "$DEV_STATUS" = "200" ]; then
    pass "Dev environment created (HTTP ${DEV_STATUS})"
else
    fail "Dev env create returned HTTP ${DEV_STATUS}"
fi

# --- 5. Create staging environment ---
echo ""
echo "--- 5. Create staging environment ---"
STAGING_ENV_BODY=$(cat <<'EOF'
{
  "tier": "staging",
  "resourceQuota": {
    "cpuRequest": "1",
    "cpuLimit": "2",
    "memoryRequest": "1Gi",
    "memoryLimit": "2Gi",
    "pods": 10,
    "services": 5,
    "persistentVolumeClaims": 2
  },
  "limitRange": {
    "defaultCpuRequest": "100m",
    "defaultCpuLimit": "500m",
    "defaultMemoryRequest": "128Mi",
    "defaultMemoryLimit": "512Mi"
  },
  "networkPolicy": {
    "allowInterNamespace": false,
    "egressAllowInternet": true
  },
  "argoCD": {"enabled": true}
}
EOF
)
STG_STATUS=$(curl_api_status POST "/api/v1/teams/${TEST_TEAM}/environments" "$STAGING_ENV_BODY")
if [ "$STG_STATUS" = "201" ] || [ "$STG_STATUS" = "200" ]; then
    pass "Staging environment created (HTTP ${STG_STATUS})"
else
    fail "Staging env create returned HTTP ${STG_STATUS}"
fi

echo "  Waiting 20s for operator to reconcile namespaces..."
sleep 20

# --- 6. Register application ---
echo ""
echo "--- 6. Register application ---"
APP_BODY=$(cat <<EOF
{
  "name": "${TEST_APP}",
  "displayName": "Sample API",
  "description": "End-to-end test application",
  "repoUrl": "https://github.com/argoproj/rollouts-demo",
  "chartPath": "examples/blue-green",
  "imageRepo": "argoproj/rollouts-demo",
  "ownerEmail": "e2e@example.com",
  "defaultStrategy": "rolling"
}
EOF
)
APP_RESP=$(curl_api POST "/api/v1/teams/${TEST_TEAM}/applications" "$APP_BODY")
APP_SLUG=$(json_get name "$APP_RESP")
if [ -n "$APP_SLUG" ]; then
    pass "Application registered (slug='${APP_SLUG}')"
else
    fail "Application register (no slug in response): $(echo "$APP_RESP" | head -c 300)"
fi

# --- 7. List team applications ---
echo ""
echo "--- 7. List applications ---"
LIST_RESP=$(curl_api GET "/api/v1/teams/${TEST_TEAM}/applications")
if echo "$LIST_RESP" | python3 -c "
import sys,json
d=json.load(sys.stdin)
if isinstance(d, dict):
    d=d.get('applications') or d.get('items') or []
names=[a.get('name') for a in d]
sys.exit(0 if '${TEST_APP}' in names else 1)
" 2>/dev/null; then
    pass "Application appears in team list"
else
    fail "Application not found in team list: $(echo "$LIST_RESP" | head -c 300)"
fi

# --- 8. Get team inventory ---
echo ""
echo "--- 8. Team inventory ---"
INV_RESP=$(curl_api GET "/api/v1/teams/${TEST_TEAM}/applications/inventory")
if echo "$INV_RESP" | python3 -c "
import sys,json
d=json.load(sys.stdin)
rows=d.get('rows') if isinstance(d, dict) else d
names=[r.get('name') for r in (rows or [])]
sys.exit(0 if '${TEST_APP}' in names else 1)
" 2>/dev/null; then
    pass "Inventory has app row"
else
    fail "Inventory missing app row: $(echo "$INV_RESP" | head -c 300)"
fi

# --- 9. Deploy to dev ---
echo ""
echo "--- 9. Deploy to dev ---"
DEPLOY_BODY=$(cat <<EOF
{"tier": "dev", "imageTag": "${TEST_IMAGE_TAG}"}
EOF
)
DEPLOY_STATUS=$(curl_api_status POST "/api/v1/teams/${TEST_TEAM}/applications/${TEST_APP}/deploy" "$DEPLOY_BODY")
if [ "$DEPLOY_STATUS" = "200" ] || [ "$DEPLOY_STATUS" = "201" ]; then
    pass "Deploy to dev triggered (HTTP ${DEPLOY_STATUS})"
else
    fail "Deploy returned HTTP ${DEPLOY_STATUS}"
    curl_api POST "/api/v1/teams/${TEST_TEAM}/applications/${TEST_APP}/deploy" "$DEPLOY_BODY" | head -c 300
    echo ""
fi

# --- 10. List applicable gates ---
echo ""
echo "--- 10. List applicable gates ---"
GATES_RESP=$(curl_api GET "/api/v1/teams/${TEST_TEAM}/applications/${TEST_APP}/gates")
GATE_COUNT=$(echo "$GATES_RESP" | python3 -c "
import sys,json
d=json.load(sys.stdin)
items=d.get('items') if isinstance(d, dict) else d
print(len(items or []))
" 2>/dev/null || echo "0")
if [ "${GATE_COUNT:-0}" -ge 2 ]; then
    pass "App gates listed (count=${GATE_COUNT})"
else
    fail "Expected at least 2 gates, got ${GATE_COUNT}"
fi

# --- 11. Create promotion request dev -> staging ---
echo ""
echo "--- 11. Create promotion request ---"
PROMO_BODY=$(cat <<EOF
{"targetTier": "staging", "imageTag": "${TEST_IMAGE_TAG}"}
EOF
)
PROMO_RESP=$(curl_api POST "/api/v1/teams/${TEST_TEAM}/applications/${TEST_APP}/promotion-requests" "$PROMO_BODY")
PROMO_ID=$(json_get id "$PROMO_RESP")
PROMO_STATUS_FIELD=$(json_get status "$PROMO_RESP")
if [ -n "$PROMO_ID" ]; then
    pass "Promotion request created (id=${PROMO_ID}, status=${PROMO_STATUS_FIELD})"
else
    fail "Promotion request create: $(echo "$PROMO_RESP" | head -c 300)"
fi

# --- 12. Get promotion request detail ---
echo ""
echo "--- 12. Get promotion request detail ---"
if [ -n "$PROMO_ID" ]; then
    DETAIL_RESP=$(curl_api GET "/api/v1/promotion-requests/${PROMO_ID}")
    if echo "$DETAIL_RESP" | python3 -c "
import sys,json
d=json.load(sys.stdin)
sys.exit(0 if 'gateResults' in d else 1)
" 2>/dev/null; then
        pass "Promotion request detail has gateResults"
    else
        fail "Promotion request detail missing gateResults: $(echo "$DETAIL_RESP" | head -c 300)"
    fi
else
    fail "Skipped (no promotion id)"
fi

# --- 13. List team promotion requests ---
echo ""
echo "--- 13. List team promotion requests ---"
LIST_PROMO=$(curl_api GET "/api/v1/teams/${TEST_TEAM}/applications/${TEST_APP}/promotion-requests")
PROMO_COUNT=$(echo "$LIST_PROMO" | python3 -c "
import sys,json
d=json.load(sys.stdin)
if isinstance(d, dict):
    items=d.get('items') or []
    print(len(items))
else:
    print(len(d))
" 2>/dev/null || echo "0")
if [ "${PROMO_COUNT:-0}" -ge 1 ]; then
    pass "Team promotion list count=${PROMO_COUNT}"
else
    fail "Expected at least 1 promotion, got ${PROMO_COUNT}"
fi

# --- 14. Cancel the promotion ---
echo ""
echo "--- 14. Cancel promotion (if not terminal) ---"
TERMINAL_STATES="completed failed rejected cancelled rolled_back"
IS_TERMINAL=0
for s in $TERMINAL_STATES; do
    if [ "$PROMO_STATUS_FIELD" = "$s" ]; then
        IS_TERMINAL=1
        break
    fi
done
if [ "$IS_TERMINAL" = "1" ]; then
    echo "  Skipped: promotion already terminal (${PROMO_STATUS_FIELD})"
    pass "Cancel skipped (already terminal: ${PROMO_STATUS_FIELD})"
elif [ -n "$PROMO_ID" ]; then
    CANCEL_STATUS=$(curl_api_status POST "/api/v1/promotion-requests/${PROMO_ID}/cancel" "{}")
    if [ "$CANCEL_STATUS" = "200" ] || [ "$CANCEL_STATUS" = "409" ]; then
        pass "Cancel returned HTTP ${CANCEL_STATUS}"
    else
        fail "Cancel returned HTTP ${CANCEL_STATUS}"
    fi
else
    fail "Skipped (no promotion id)"
fi

# --- 15. List platform gates (admin) ---
echo ""
echo "--- 15. Admin list platform gates ---"
ADMIN_GATES=$(curl_api GET "/api/v1/admin/promotion-gates")
ADMIN_GATE_COUNT=$(echo "$ADMIN_GATES" | python3 -c "
import sys,json
d=json.load(sys.stdin)
items=d.get('items') if isinstance(d, dict) else d
print(len(items or []))
" 2>/dev/null || echo "0")
if [ "${ADMIN_GATE_COUNT:-0}" -ge 6 ]; then
    pass "Platform gates count=${ADMIN_GATE_COUNT} (>=6)"
else
    fail "Expected at least 6 platform gates, got ${ADMIN_GATE_COUNT}"
fi

# --- 16. Verify Argo CD Application exists ---
echo ""
echo "--- 16. Verify Argo CD Application ---"
ARGO_APPS=$(kubectl --context "$STAGE_CTX" -n argocd get application -o name 2>/dev/null || echo "")
if echo "$ARGO_APPS" | grep -q "${TEST_TEAM}"; then
    pass "Argo CD Application found for team"
else
    fail "No Argo CD Application matching team '${TEST_TEAM}' found"
fi

# --- 17. Verify ApplicationDeployment row sync ---
echo ""
echo "--- 17. Verify deployment row sync (waiting 35s) ---"
sleep 35
APP_DETAIL=$(curl_api GET "/api/v1/teams/${TEST_TEAM}/applications/${TEST_APP}")
if echo "$APP_DETAIL" | python3 -c "
import sys,json
d=json.load(sys.stdin)
deps=d.get('deployments') or []
for x in deps:
    if x.get('environmentTier')=='dev' and x.get('healthStatus'):
        sys.exit(0)
sys.exit(1)
" 2>/dev/null; then
    pass "Deployment row has healthStatus populated"
else
    fail "Dev deployment missing or healthStatus empty: $(echo "$APP_DETAIL" | head -c 400)"
fi

# --- 18. Cleanup ---
echo ""
echo "--- 18. Cleanup ---"
CLEAN_STATUS=$(curl_api_status DELETE "/api/v1/teams/${TEST_TEAM}")
echo "  DELETE team status: ${CLEAN_STATUS}"
echo "  Waiting 25s for cascade..."
sleep 25

NS_DEV="${TEST_TEAM}-dev"
NS_STG="${TEST_TEAM}-staging"
if kubectl --context "$STAGE_CTX" get namespace "$NS_DEV" &>/dev/null; then
    fail "Dev namespace '${NS_DEV}' still exists"
else
    pass "Dev namespace cleaned up"
fi
if kubectl --context "$STAGE_CTX" get namespace "$NS_STG" &>/dev/null; then
    fail "Staging namespace '${NS_STG}' still exists"
else
    pass "Staging namespace cleaned up"
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
    echo "E2E TESTS FAILED"
    exit 1
else
    echo "ALL E2E TESTS PASSED"
fi
