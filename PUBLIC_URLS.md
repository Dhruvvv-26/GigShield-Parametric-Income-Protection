# KavachAI — Public Service URLs

> Fill in after deploying to Railway.app. Use `./scripts/update_public_urls.sh` to auto-populate this file.

| Service | Public URL | Health |
|---------|-----------|--------|
| Worker Service | `https://kavachai-worker-service-production.up.railway.app` | `/health` |
| Policy Service | `https://kavachai-policy-service-production.up.railway.app` | `/health` |
| Trigger Engine | `https://kavachai-trigger-engine-production.up.railway.app` | `/health` |
| Claims Service | `https://kavachai-claims-service-production.up.railway.app` | `/health` |
| Payment Service | `https://kavachai-payment-service-production.up.railway.app` | `/health` |
| ML Service | `https://kavachai-ml-service-production.up.railway.app` | `/health` → models_loaded: 11 |
| Admin Dashboard | `https://kavachai-admin.vercel.app` | — |

## Demo Anchor Worker

| Field | Value |
|-------|-------|
| **worker_id** | `6fc7ae56-8cc2-4d32-b8cf-c21844a177ce` |
| **Name** | Arjun Kumar |
| **Zone** | delhi_rohini |
| **Platform** | Blinkit |
| **Vehicle** | e_bike |

## Quick Verification (for judges)

```bash
# 1. All 6 services healthy?
for svc in worker policy trigger claims payment ml; do
  url="https://kavachai-${svc}-service-production.up.railway.app"
  echo "${svc}: $(curl -sf ${url}/health | python3 -c 'import sys,json; print(json.load(sys.stdin).get(\"status\",\"unknown\"))' 2>/dev/null || echo '❌')"
done

# 2. ML models loaded?
curl -s https://kavachai-ml-service-production.up.railway.app/health | python3 -m json.tool

# 3. Run full smoke test
./scripts/full_smoke_test.sh
```

## Key Demo Endpoints

1. **Arjun's Worker Profile**: `GET /api/v1/workers/6fc7ae56-8cc2-4d32-b8cf-c21844a177ce`
2. **His Active Policy**: `GET /api/v1/policies/worker/6fc7ae56-8cc2-4d32-b8cf-c21844a177ce`
3. **Force Majeure Exclusions**: `GET /api/v1/policies/exclusions/reference`
4. **All Claims (paginated)**: `GET /api/v1/claims?page=1&per_page=10`
5. **Financial Summary + BCR**: `GET /api/v1/payments/summary`
6. **Trigger Status**: `GET /api/v1/trigger/status`
7. **SHAP Premium**: `POST /api/v1/premium/calculate`
