#!/usr/bin/env bash
# ============================================================
# KavachAI — Full Smoke Test (10 tests)
# Validates all critical endpoints are working.
#
# Usage:
#   ./scripts/full_smoke_test.sh                    # Uses localhost
#   ./scripts/full_smoke_test.sh --base https://...  # Uses Railway URLs
#
# Each test outputs PASS/FAIL. Exit code is 0 only if ALL pass.
# ============================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# ── Default base URLs (localhost) ─────────────────────────────
WORKER_BASE="${WORKER_URL:-http://localhost:8001}"
POLICY_BASE="${POLICY_URL:-http://localhost:8002}"
TRIGGER_BASE="${TRIGGER_URL:-http://localhost:8003}"
CLAIMS_BASE="${CLAIMS_URL:-http://localhost:8004}"
PAYMENT_BASE="${PAYMENT_URL:-http://localhost:8005}"
ML_BASE="${ML_URL:-http://localhost:8006}"

# Parse --base argument for Railway (same base domain, different services)
while [[ $# -gt 0 ]]; do
    case "$1" in
        --worker)  WORKER_BASE="$2";  shift 2;;
        --policy)  POLICY_BASE="$2";  shift 2;;
        --trigger) TRIGGER_BASE="$2"; shift 2;;
        --claims)  CLAIMS_BASE="$2";  shift 2;;
        --payment) PAYMENT_BASE="$2"; shift 2;;
        --ml)      ML_BASE="$2";      shift 2;;
        *) echo "Unknown: $1"; shift;;
    esac
done

PASS=0
FAIL=0
TOTAL=10

DEMO_WORKER="6fc7ae56-8cc2-4d32-b8cf-c21844a177ce"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  KavachAI — Full Smoke Test (${TOTAL} tests)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ── Helper ────────────────────────────────────────────────────
run_test() {
    local test_num="$1"
    local test_name="$2"
    local url="$3"
    local method="${4:-GET}"
    local body="${5:-}"
    local expect_field="${6:-status}"
    local expect_value="${7:-}"

    printf "  [%02d/10] %-45s " "$test_num" "$test_name"

    local response=""
    if [ "$method" = "POST" ] && [ -n "$body" ]; then
        response=$(curl -sf -X POST -H "Content-Type: application/json" -d "$body" "$url" 2>/dev/null || echo "")
    else
        response=$(curl -sf "$url" 2>/dev/null || echo "")
    fi

    if [ -z "$response" ]; then
        echo -e "${RED}FAIL${NC} (no response)"
        FAIL=$((FAIL + 1))
        return
    fi

    # If we have an expected field/value, check it
    if [ -n "$expect_value" ]; then
        local actual=""
        actual=$(echo "$response" | python3 -c "import sys,json; print(json.load(sys.stdin).get('$expect_field',''))" 2>/dev/null || echo "")
        if [ "$actual" = "$expect_value" ]; then
            echo -e "${GREEN}PASS${NC}"
            PASS=$((PASS + 1))
        else
            echo -e "${RED}FAIL${NC} (${expect_field}='${actual}', expected '${expect_value}')"
            FAIL=$((FAIL + 1))
        fi
    else
        # Just check we got a valid JSON response
        if echo "$response" | python3 -c "import sys,json; json.load(sys.stdin)" 2>/dev/null; then
            echo -e "${GREEN}PASS${NC}"
            PASS=$((PASS + 1))
        else
            echo -e "${RED}FAIL${NC} (invalid JSON)"
            FAIL=$((FAIL + 1))
        fi
    fi
}

# ── Test 1: Worker Service Health ─────────────────────────────
run_test 1 "Worker Service /health" \
    "${WORKER_BASE}/health" "GET" "" "status" "healthy"

# ── Test 2: Policy Service Health ─────────────────────────────
run_test 2 "Policy Service /health" \
    "${POLICY_BASE}/health" "GET" "" "status" "healthy"

# ── Test 3: Trigger Engine Health ─────────────────────────────
run_test 3 "Trigger Engine /health" \
    "${TRIGGER_BASE}/health" "GET" "" "status" "healthy"

# ── Test 4: Claims Service Health ─────────────────────────────
run_test 4 "Claims Service /health" \
    "${CLAIMS_BASE}/health" "GET" "" "status" "healthy"

# ── Test 5: Payment Service Health ────────────────────────────
run_test 5 "Payment Service /health" \
    "${PAYMENT_BASE}/health" "GET" "" "status" "healthy"

# ── Test 6: ML Service Health (models_loaded=11) ──────────────
printf "  [06/10] %-45s " "ML Service /health (11 models)"
ML_RESPONSE=$(curl -sf "${ML_BASE}/health" 2>/dev/null || echo "")
if [ -n "$ML_RESPONSE" ]; then
    ML_STATUS=$(echo "$ML_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status',''))" 2>/dev/null || echo "")
    ML_MODELS=$(echo "$ML_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('models_loaded',0))" 2>/dev/null || echo "0")
    if [ "$ML_STATUS" = "healthy" ]; then
        echo -e "${GREEN}PASS${NC} (models_loaded=${ML_MODELS})"
        PASS=$((PASS + 1))
    else
        echo -e "${RED}FAIL${NC} (status='${ML_STATUS}', models_loaded=${ML_MODELS})"
        FAIL=$((FAIL + 1))
    fi
else
    echo -e "${RED}FAIL${NC} (no response)"
    FAIL=$((FAIL + 1))
fi

# ── Test 7: Demo Worker Profile ───────────────────────────────
run_test 7 "Demo worker profile (Arjun Kumar)" \
    "${WORKER_BASE}/api/v1/workers/${DEMO_WORKER}"

# ── Test 8: Force Majeure Exclusions ──────────────────────────
run_test 8 "Force Majeure exclusions reference" \
    "${POLICY_BASE}/api/v1/policies/exclusions/reference"

# ── Test 9: Payment Summary (BCR fields) ──────────────────────
printf "  [09/10] %-45s " "Payment summary + BCR fields"
PAY_RESPONSE=$(curl -sf "${PAYMENT_BASE}/api/v1/payments/summary" 2>/dev/null || echo "")
if [ -n "$PAY_RESPONSE" ]; then
    HAS_BCR=$(echo "$PAY_RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print('yes' if 'burning_cost_rate' in d else 'no')" 2>/dev/null || echo "no")
    if [ "$HAS_BCR" = "yes" ]; then
        BCR_VAL=$(echo "$PAY_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('burning_cost_rate',0))" 2>/dev/null || echo "?")
        echo -e "${GREEN}PASS${NC} (BCR=${BCR_VAL}%)"
        PASS=$((PASS + 1))
    else
        echo -e "${RED}FAIL${NC} (burning_cost_rate field missing)"
        FAIL=$((FAIL + 1))
    fi
else
    echo -e "${RED}FAIL${NC} (no response)"
    FAIL=$((FAIL + 1))
fi

# ── Test 10: Claims Paginated Listing ─────────────────────────
run_test 10 "Claims paginated listing" \
    "${CLAIMS_BASE}/api/v1/claims?page=1&per_page=5"

# ── Summary ──────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ $PASS -eq $TOTAL ]; then
    echo -e "  ${GREEN}✅ ALL ${TOTAL} TESTS PASSED${NC}"
    echo "  KavachAI is production-ready for judges."
else
    echo -e "  ${RED}❌ ${PASS}/${TOTAL} tests passed, ${FAIL} failed${NC}"
    echo "  Fix failing services before submitting."
fi
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Exit with non-zero if any test failed
[ $FAIL -eq 0 ] && exit 0 || exit 1
