#!/usr/bin/env bash
# ============================================================
# KavachAI — Set Railway Environment Variables
#
# ⚠️  WARNING: NEVER commit this script with values filled in.
#     This script reads from a local .env file and sets each
#     variable on each Railway service.
#
# Usage: ./scripts/set_railway_env.sh [--env-file .env]
#
# Prerequisites:
#   - Railway CLI installed and logged in
#   - Project linked: railway link
#   - .env file with all required secrets
# ============================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()  { echo -e "${BLUE}[INFO]${NC}  $1"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
fail()  { echo -e "${RED}[FAIL]${NC}  $1"; exit 1; }

# Parse arguments
ENV_FILE=".env"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --env-file) ENV_FILE="$2"; shift 2;;
        *) fail "Unknown argument: $1";;
    esac
done

if [ ! -f "$ENV_FILE" ]; then
    fail "Environment file not found: $ENV_FILE"
fi

info "Reading environment variables from: $ENV_FILE"

# ── Services to configure ────────────────────────────────────
SERVICES=(
    "kavachai-worker-service"
    "kavachai-policy-service"
    "kavachai-trigger-engine"
    "kavachai-claims-service"
    "kavachai-payment-service"
    "kavachai-ml-service"
)

# ── Variables to set on ALL services ──────────────────────────
# These are read from .env and applied to every service
COMMON_VARS=(
    "DATABASE_URL"
    "REDIS_URL"
    "OPENWEATHERMAP_API_KEY"
    "CPCB_API_KEY"
    "SECRET_KEY"
    "REDPANDA_BROKERS"
)

# ── Service-specific variables ────────────────────────────────
# These are only set on specific services
declare -A SERVICE_SPECIFIC_VARS
SERVICE_SPECIFIC_VARS["kavachai-payment-service"]="RAZORPAY_KEY_ID RAZORPAY_KEY_SECRET FIREBASE_CREDENTIALS_JSON FCM_DISPATCH_ENABLED TWILIO_ACCOUNT_SID TWILIO_AUTH_TOKEN TWILIO_WHATSAPP_FROM"
SERVICE_SPECIFIC_VARS["kavachai-trigger-engine"]="OPENWEATHERMAP_API_KEY CPCB_API_KEY TRIGGER_POLL_INTERVAL_MINUTES"
SERVICE_SPECIFIC_VARS["kavachai-claims-service"]="FIREBASE_CREDENTIALS_JSON"

# ── Helper to read value from .env ────────────────────────────
get_env_value() {
    local key="$1"
    local value=""
    # Read from .env file, handling quotes and exports
    value=$(grep -E "^(export )?${key}=" "$ENV_FILE" 2>/dev/null | head -1 | sed -E "s/^(export )?${key}=//" | sed -E 's/^"(.*)"$/\1/' | sed -E "s/^'(.*)'$/\1/")
    echo "$value"
}

# ── Set common variables on all services ──────────────────────
info "Setting common environment variables on all services..."

for var_name in "${COMMON_VARS[@]}"; do
    var_value=$(get_env_value "$var_name")
    if [ -z "$var_value" ]; then
        warn "Variable $var_name not found in $ENV_FILE — skipping"
        continue
    fi

    for service in "${SERVICES[@]}"; do
        railway variables set "${var_name}=${var_value}" --service "$service" 2>/dev/null || {
            warn "Failed to set $var_name on $service"
        }
    done
    ok "Set $var_name on all services"
done

# ── Set service-specific variables ────────────────────────────
info "Setting service-specific environment variables..."

for service in "${!SERVICE_SPECIFIC_VARS[@]}"; do
    IFS=' ' read -ra vars <<< "${SERVICE_SPECIFIC_VARS[$service]}"
    for var_name in "${vars[@]}"; do
        var_value=$(get_env_value "$var_name")
        if [ -z "$var_value" ]; then
            warn "Variable $var_name not found in $ENV_FILE — skipping for $service"
            continue
        fi

        railway variables set "${var_name}=${var_value}" --service "$service" 2>/dev/null || {
            warn "Failed to set $var_name on $service"
        }
        ok "Set $var_name on $service"
    done
done

# ── Set inter-service URLs ────────────────────────────────────
# These point services to each other via Railway's internal networking
info "Setting inter-service URL variables..."

# Get public URLs  for cross-service communication
WORKER_URL=$(railway domain --service "kavachai-worker-service" 2>/dev/null || echo "")
POLICY_URL=$(railway domain --service "kavachai-policy-service" 2>/dev/null || echo "")
CLAIMS_URL=$(railway domain --service "kavachai-claims-service" 2>/dev/null || echo "")
PAYMENT_URL=$(railway domain --service "kavachai-payment-service" 2>/dev/null || echo "")
ML_URL=$(railway domain --service "kavachai-ml-service" 2>/dev/null || echo "")

# Ensure https:// prefix
[ -n "$WORKER_URL" ] && [[ "$WORKER_URL" != https://* ]] && WORKER_URL="https://${WORKER_URL}"
[ -n "$POLICY_URL" ] && [[ "$POLICY_URL" != https://* ]] && POLICY_URL="https://${POLICY_URL}"
[ -n "$CLAIMS_URL" ] && [[ "$CLAIMS_URL" != https://* ]] && CLAIMS_URL="https://${CLAIMS_URL}"
[ -n "$PAYMENT_URL" ] && [[ "$PAYMENT_URL" != https://* ]] && PAYMENT_URL="https://${PAYMENT_URL}"
[ -n "$ML_URL" ] && [[ "$ML_URL" != https://* ]] && ML_URL="https://${ML_URL}"

# Set WORKER_SERVICE_URL on policy_service (it calls worker_service for profile lookups)
if [ -n "$WORKER_URL" ]; then
    for service in "${SERVICES[@]}"; do
        railway variables set "WORKER_SERVICE_URL=${WORKER_URL}" --service "$service" 2>/dev/null || true
    done
    ok "Set WORKER_SERVICE_URL on all services"
fi

if [ -n "$POLICY_URL" ]; then
    railway variables set "POLICY_SERVICE_URL=${POLICY_URL}" --service "kavachai-trigger-engine" 2>/dev/null || true
    ok "Set POLICY_SERVICE_URL on trigger-engine"
fi

if [ -n "$CLAIMS_URL" ]; then
    railway variables set "CLAIMS_SERVICE_URL=${CLAIMS_URL}" --service "kavachai-payment-service" 2>/dev/null || true
    ok "Set CLAIMS_SERVICE_URL on payment-service"
fi

if [ -n "$PAYMENT_URL" ]; then
    railway variables set "PAYMENT_SERVICE_URL=${PAYMENT_URL}" --service "kavachai-claims-service" 2>/dev/null || true
    ok "Set PAYMENT_SERVICE_URL on claims-service"
fi

if [ -n "$ML_URL" ]; then
    railway variables set "ML_SERVICE_URL=${ML_URL}" --service "kavachai-claims-service" 2>/dev/null || true
    ok "Set ML_SERVICE_URL on claims-service"
fi

echo ""
ok "Environment variables configured for all Railway services"
info "Verify with: railway variables --service <service-name>"
