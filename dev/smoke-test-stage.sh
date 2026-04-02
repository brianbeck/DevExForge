#!/usr/bin/env bash
set -uo pipefail

STAGE_CTX="${STAGE_CTX:-beck-stage-admin@beck-stage}"
TEST_TEAM="smoke-test"
TEST_TIER="dev"
NAMESPACE="${TEST_TEAM}-${TEST_TIER}"
CRD_GROUP="devexforge.brianbeck.net"
CRD_VERSION="v1alpha1"

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

check() {
    local desc="$1"
    shift
    if "$@" &>/dev/null; then
        pass "$desc"
    else
        fail "$desc"
    fi
}

echo "=== DevExForge Stage Smoke Tests ==="
echo ""
echo "Cluster: ${STAGE_CTX}"
echo ""

# --- Preflight ---
echo "--- Preflight ---"
check "Cluster reachable" kubectl --context "$STAGE_CTX" cluster-info
check "CRDs installed" kubectl --context "$STAGE_CTX" get crd teams.${CRD_GROUP}
check "Environment CRD installed" kubectl --context "$STAGE_CTX" get crd environments.${CRD_GROUP}
check "Operator namespace exists" kubectl --context "$STAGE_CTX" get namespace engineering-platform
POD_PHASE=$(kubectl --context "$STAGE_CTX" -n engineering-platform get pods -l app.kubernetes.io/name=devexforge-operator -o jsonpath='{.items[0].status.phase}' 2>/dev/null || echo "")
if [ "$POD_PHASE" = "Running" ]; then
    pass "Operator pod running"
else
    fail "Operator pod status is '${POD_PHASE}' (expected Running)"
fi

echo ""
echo "--- Create Test Team CRD ---"
# Clean up any previous test resources
kubectl --context "$STAGE_CTX" delete team "$TEST_TEAM" --ignore-not-found &>/dev/null
kubectl --context "$STAGE_CTX" delete environment "${NAMESPACE}" --ignore-not-found &>/dev/null
kubectl --context "$STAGE_CTX" delete namespace "$NAMESPACE" --ignore-not-found --wait=false &>/dev/null
sleep 3

# Create Team CRD
kubectl --context "$STAGE_CTX" apply -f - <<EOF
apiVersion: ${CRD_GROUP}/${CRD_VERSION}
kind: Team
metadata:
  name: ${TEST_TEAM}
spec:
  displayName: Smoke Test Team
  description: Automated smoke test
  owner:
    email: smoketest@company.com
  members:
    - email: smoketest@company.com
      role: admin
    - email: developer@company.com
      role: developer
  costCenter: TEST-001
  tags:
    purpose: smoke-test
EOF

check "Team CRD created" kubectl --context "$STAGE_CTX" get team "$TEST_TEAM"

echo ""
echo "--- Wait for Team reconciliation (10s) ---"
sleep 10

# Check Team status
TEAM_PHASE=$(kubectl --context "$STAGE_CTX" get team "$TEST_TEAM" -o jsonpath='{.status.phase}' 2>/dev/null || echo "")
if [ "$TEAM_PHASE" = "Active" ]; then
    pass "Team status is Active"
else
    fail "Team status is '${TEAM_PHASE}' (expected Active)"
fi

echo ""
echo "--- Create Test Environment CRD ---"
kubectl --context "$STAGE_CTX" apply -f - <<EOF
apiVersion: ${CRD_GROUP}/${CRD_VERSION}
kind: Environment
metadata:
  name: ${NAMESPACE}
spec:
  teamRef: ${TEST_TEAM}
  tier: ${TEST_TIER}
  cluster: beck-stage
  resourceQuota:
    cpuRequest: "1"
    cpuLimit: "2"
    memoryRequest: "1Gi"
    memoryLimit: "2Gi"
    pods: 10
    services: 5
    persistentVolumeClaims: 2
  limitRange:
    defaultCpuRequest: "100m"
    defaultCpuLimit: "500m"
    defaultMemoryRequest: "128Mi"
    defaultMemoryLimit: "512Mi"
  networkPolicy:
    allowInterNamespace: false
    egressAllowInternet: true
  policies:
    requireNonRoot: false
    requireReadOnlyRoot: false
    maxCriticalCVEs: 5
    maxHighCVEs: 20
    requireResourceLimits: false
  argoCD:
    enabled: false
EOF

check "Environment CRD created" kubectl --context "$STAGE_CTX" get environment "$NAMESPACE"

echo ""
echo "--- Wait for Environment reconciliation (30s) ---"
sleep 30

# Check Environment status
ENV_PHASE=$(kubectl --context "$STAGE_CTX" get environment "$NAMESPACE" -o jsonpath='{.status.phase}' 2>/dev/null || echo "")
if [ "$ENV_PHASE" = "Active" ]; then
    pass "Environment status is Active"
else
    fail "Environment status is '${ENV_PHASE}' (expected Active)"
fi

echo ""
echo "--- Verify reconciled resources ---"
check "Namespace created" kubectl --context "$STAGE_CTX" get namespace "$NAMESPACE"

# Check namespace labels
TEAM_LABEL=$(kubectl --context "$STAGE_CTX" get namespace "$NAMESPACE" -o jsonpath="{.metadata.labels['devexforge\.brianbeck\.net/team']}" 2>/dev/null || echo "")
if [ "$TEAM_LABEL" = "$TEST_TEAM" ]; then
    pass "Namespace has team label"
else
    fail "Namespace team label is '${TEAM_LABEL}' (expected ${TEST_TEAM})"
fi

check "ResourceQuota created" kubectl --context "$STAGE_CTX" -n "$NAMESPACE" get resourcequota default
check "LimitRange created" kubectl --context "$STAGE_CTX" -n "$NAMESPACE" get limitrange default
check "NetworkPolicy created" kubectl --context "$STAGE_CTX" -n "$NAMESPACE" get networkpolicy default
check "RoleBindings created" kubectl --context "$STAGE_CTX" -n "$NAMESPACE" get rolebindings -l devexforge.brianbeck.net/managed-by=devexforge-operator -o name | grep -q rolebinding

# Verify quota values
QUOTA_PODS=$(kubectl --context "$STAGE_CTX" -n "$NAMESPACE" get resourcequota default -o jsonpath='{.spec.hard.pods}' 2>/dev/null || echo "")
if [ "$QUOTA_PODS" = "10" ]; then
    pass "ResourceQuota pods limit is correct (10)"
else
    fail "ResourceQuota pods limit is '${QUOTA_PODS}' (expected 10)"
fi

echo ""
echo "--- Cleanup ---"
kubectl --context "$STAGE_CTX" delete environment "$NAMESPACE" --ignore-not-found
kubectl --context "$STAGE_CTX" delete team "$TEST_TEAM" --ignore-not-found
echo "Waiting for cleanup (15s)..."
sleep 15

# Verify cleanup
if kubectl --context "$STAGE_CTX" get namespace "$NAMESPACE" &>/dev/null; then
    fail "Namespace still exists after cleanup"
else
    pass "Namespace cleaned up"
fi

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
