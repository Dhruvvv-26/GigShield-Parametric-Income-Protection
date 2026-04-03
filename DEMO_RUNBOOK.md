# GigShield — Judge Demo Runbook

## Prerequisites
- Docker Desktop running (8GB RAM allocated)
- `.env` file present at repo root (copy from `.env.example`)

## Step 1: Start the Stack (60–90 seconds)
```bash
docker compose -f docker-compose.demo.yml up -d
```
Wait for: `worker_service | Application startup complete`

Verify all containers are up:
```bash
docker compose -f docker-compose.demo.yml ps
```

## Step 2: Seed Demo Data (10 seconds)
```bash
docker exec gigshield-worker-service python scripts/seed_demo.py
```
Seeds 10 riders across 3 zones with active policies.

## Step 3: Run the 60-Second Demo
```bash
python scripts/demo_script.py
```
Expected output:
```
✅ CHECK 1 PASSED — Clean claim auto-approved in 4.2s
✅ CHECK 2 PASSED — Suspicious claim soft-held, partial payout in 5.1s
✅ CHECK 3 PASSED — GPS spoofing detected and blocked in 3.8s
🎯 GigShield 5-Star Demo: All checks passed in 13.1s
```

## What Each Check Demonstrates

| Check | Scenario | Fraud Score | Outcome | What It Shows |
|---|---|---|---|---|
| 1 | Clean rider, genuine GPS | 0.10–0.25 | Auto-approved | Parametric trigger → instant payout for legitimate rider |
| 2 | Suspicious signals | 0.45–0.65 | 50% now, 50% held | Graduated response — honest worker never fully blocked |
| 3 | GPS spoofed, stationary | 0.85–1.00 | Blocked | 4-layer adversarial defense catches coordinated fraud |

## Narration Guide (for video or live demo)

**Before running Check 1:**
> "Arjun is a Blinkit cyclist in Rohini, Delhi. Delhi AQI just crossed 450. Watch what happens — he does nothing."

**After Check 1 passes:**
> "₹350 credited to Arjun's UPI in under 5 seconds. No claim filed. No document uploaded. No phone call. The system detected the threshold breach, verified his signals were clean, and paid him automatically."

**Before running Check 2:**
> "Now — a suspicious rider. GPS is in the zone, but the signal variance is too low and he only appeared after the trigger alert went out."

**After Check 2 passes:**
> "The system doesn't block him — it can't be certain. So it pays him 50% immediately and holds 50% for 2-hour verification. Legitimate riders are never fully blocked. Fraud rings can't drain the pool."

**Before running Check 3:**
> "Now — the Market Crash scenario. A rider using a mock GPS app, sitting at home, accelerometer shows zero vibration, IP address is 12km from the claimed location."

**After Check 3 passes:**
> "Blocked instantly. Four independent signal layers all contradict each other. This is what defeated the 500-rider Telegram syndicate. A single GPS coordinate check couldn't catch this. We built four."

## Troubleshooting

| Issue | Fix |
|---|---|
| Container won't start | `docker compose -f docker-compose.demo.yml logs {service_name}` |
| Claims not routing | Check Redis is healthy: `docker exec gigshield-redis redis-cli -a redis_secure_2026 ping` |
| FCM not sending | Set `FCM_DISPATCH_ENABLED=false` in `.env` — payout still works |
| Fraud score always 0 | Verify sensor payload is reaching Claims Service: check `claims_service` logs |
| Redpanda topics missing | Check `redpanda-init` ran: `docker logs gigshield-redpanda-init` |
| Port conflict | Ensure no local services on 5432, 6379, 8001–8005 |

## Emergency Fallback

If `demo_script.py` fails, run the pipeline manually:

```bash
# Fire a clean trigger directly
curl -X POST http://localhost:8003/api/v1/trigger/test \
  -H "Content-Type: application/json" \
  -d '{"zone_code":"delhi_rohini","event_type":"aqi","metric_value":450,"scenario":"clean"}'

# Check claims
curl http://localhost:8004/api/v1/claims/recent?limit=5

# Check payments
curl http://localhost:8005/api/v1/payments/recent?limit=5
```
