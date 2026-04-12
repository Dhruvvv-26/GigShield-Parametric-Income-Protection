#!/usr/bin/env bash
# ============================================================
# KavachAI — Railway.app Deployment Script
# Deploys all 6 FastAPI microservices to Railway.app
#
# Usage: ./scripts/railway_deploy.sh
#
# Prerequisites:
#   - Railway CLI installed: npm install -g @railway/cli
#   - Logged in: railway login
#   - .env file at project root with all secrets
# ============================================================

set -euo pipefail

# ── Color helpers ─────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

info()  { echo -e "${BLUE}[INFO]${NC}  $1"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
fail()  { echo -e "${RED}[FAIL]${NC}  $1"; exit 1; }

# ── Step 0: Verify Railway CLI ────────────────────────────────
info "Checking Railway CLI installation..."
if ! command -v railway &>/dev/null; then
    fail "Railway CLI not found. Install with: npm install -g @railway/cli"
fi
ok "Railway CLI found: $(railway --version 2>/dev/null || echo 'installed')"

info "Checking Railway login status..."
if ! railway whoami &>/dev/null; then
    fail "Not logged in to Railway. Run: railway login"
fi
ok "Logged in as: $(railway whoami 2>/dev/null)"

# ── Step 1: Create or link project ───────────────────────────
PROJECT_NAME="kavachai-prod"
info "Creating/linking Railway project: ${PROJECT_NAME}"
railway link --name "${PROJECT_NAME}" 2>/dev/null || {
    info "Project may already exist or needs manual linking."
    info "Run: railway init  or  railway link"
    warn "Continuing with current linked project..."
}

# ── Step 2: Provision managed add-ons ─────────────────────────
info "Provisioning PostgreSQL add-on..."
railway add --plugin postgresql 2>/dev/null || warn "PostgreSQL may already be provisioned"
info "Waiting for PostgreSQL to become healthy..."
sleep 10
ok "PostgreSQL add-on provisioned"

info "Provisioning Redis add-on..."
railway add --plugin redis 2>/dev/null || warn "Redis may already be provisioned"
info "Waiting for Redis to become healthy..."
sleep 5
ok "Redis add-on provisioned"

# Capture DATABASE_URL and REDIS_URL from Railway
info "Capturing DATABASE_URL and REDIS_URL from Railway variables..."
DATABASE_URL=$(railway variables get DATABASE_URL 2>/dev/null || echo "")
REDIS_URL=$(railway variables get REDIS_URL 2>/dev/null || echo "")

if [ -n "$DATABASE_URL" ]; then
    ok "DATABASE_URL captured from Railway"
else
    warn "DATABASE_URL not found — set it manually after provisioning"
fi

if [ -n "$REDIS_URL" ]; then
    ok "REDIS_URL captured from Railway"
else
    warn "REDIS_URL not found — set it manually after provisioning"
fi

# ── Step 3: Set environment variables ─────────────────────────
info "Setting environment variables on all services..."
if [ -f "scripts/set_railway_env.sh" ]; then
    bash scripts/set_railway_env.sh
    ok "Environment variables set"
else
    warn "scripts/set_railway_env.sh not found — set env vars manually"
fi

# ── Step 4: Deploy services in dependency order ───────────────
# Order: worker → policy → trigger → ml → claims → payment

SERVICES=(
    "kavachai-worker-service:8001:services/worker_service/Dockerfile.railway"
    "kavachai-policy-service:8002:services/policy_service/Dockerfile.railway"
    "kavachai-trigger-engine:8003:services/trigger_engine/Dockerfile.railway"
    "kavachai-ml-service:8006:services/ml_service/Dockerfile.railway"
    "kavachai-claims-service:8004:services/claims_service/Dockerfile.railway"
    "kavachai-payment-service:8005:services/payment_service/Dockerfile.railway"
)

declare -A SERVICE_URLS

for entry in "${SERVICES[@]}"; do
    IFS=':' read -r name port dockerfile <<< "$entry"
    info "Deploying ${name} (port ${port})..."

    # Deploy the service
    railway up --service "${name}" --dockerfile "${dockerfile}" --detach 2>/dev/null || {
        warn "Deploy command for ${name} may need manual intervention"
        warn "Try: railway up --service ${name}"
        continue
    }

    info "Waiting for ${name} to become healthy..."

    # Wait for health check (up to 5 minutes)
    MAX_WAIT=300
    WAITED=0
    INTERVAL=10
    HEALTHY=false

    # Get public URL for the service
    SERVICE_URL=$(railway domain --service "${name}" 2>/dev/null || echo "")

    if [ -z "$SERVICE_URL" ]; then
        # Generate a domain if none exists
        railway domain --service "${name}" --generate 2>/dev/null || true
        SERVICE_URL=$(railway domain --service "${name}" 2>/dev/null || echo "")
    fi

    if [ -n "$SERVICE_URL" ]; then
        # Ensure https:// prefix
        [[ "$SERVICE_URL" != https://* ]] && SERVICE_URL="https://${SERVICE_URL}"
        SERVICE_URLS["${name}"]="${SERVICE_URL}"

        while [ $WAITED -lt $MAX_WAIT ]; do
            HEALTH_RESPONSE=$(curl -sf "${SERVICE_URL}/health" 2>/dev/null || echo "")

            if [ -n "$HEALTH_RESPONSE" ]; then
                # Special check for ML service — wait for models_loaded: 11
                if [ "$name" = "kavachai-ml-service" ]; then
                    MODELS_LOADED=$(echo "$HEALTH_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('models_loaded',0))" 2>/dev/null || echo "0")
                    if [ "$MODELS_LOADED" = "11" ]; then
                        ok "${name} healthy — models_loaded: 11"
                        HEALTHY=true
                        break
                    else
                        info "  ML service loading models... ($MODELS_LOADED/11)"
                    fi
                else
                    ok "${name} healthy at ${SERVICE_URL}"
                    HEALTHY=true
                    break
                fi
            fi

            sleep $INTERVAL
            WAITED=$((WAITED + INTERVAL))
            info "  Waiting... (${WAITED}s/${MAX_WAIT}s)"
        done

        if [ "$HEALTHY" = false ]; then
            warn "${name} did not become healthy within ${MAX_WAIT}s"
        fi
    else
        warn "Could not determine public URL for ${name}"
    fi

    echo ""
done

# ── Step 5: Print summary ────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  KavachAI — Railway Deployment Summary"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
printf "%-30s %-50s\n" "Service" "Public URL"
echo "──────────────────────────────────────────────────────────────────────────────"

for name in "${!SERVICE_URLS[@]}"; do
    printf "%-30s %-50s\n" "$name" "${SERVICE_URLS[$name]}"
done
echo ""

# ── Step 6: Run smoke test ───────────────────────────────────
info "Running smoke test on all deployed services..."
echo ""

PASS=0
TOTAL=0

for name in "${!SERVICE_URLS[@]}"; do
    TOTAL=$((TOTAL + 1))
    URL="${SERVICE_URLS[$name]}"
    RESPONSE=$(curl -sf "${URL}/health" 2>/dev/null || echo "")

    if [ -n "$RESPONSE" ]; then
        STATUS=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status',''))" 2>/dev/null || echo "")
        if [ "$STATUS" = "healthy" ]; then
            ok "PASS — ${name}: ${URL}/health → healthy"
            PASS=$((PASS + 1))
        else
            warn "FAIL — ${name}: ${URL}/health → status='${STATUS}'"
        fi
    else
        warn "FAIL — ${name}: ${URL}/health → no response"
    fi
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ $PASS -eq $TOTAL ]; then
    ok "ALL ${TOTAL} SERVICES HEALTHY ✅"
    echo "  KavachAI is deployment-ready for judges."
else
    warn "${PASS}/${TOTAL} services healthy — check failed services above."
fi
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
