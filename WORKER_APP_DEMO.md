# 📱 KavachAI Worker App — Demo Recording Guide

> **✅ STATUS: COMPLETE — Phase 2 mobile ↔ backend integration verified**  
> Last updated: 2026-04-04

---

## 🔧 Pre-Demo Setup (Do This First!)

### Step 1: Find Your LAN IP

Every time you switch networks (WiFi ↔ iPhone Hotspot), your IP changes.

```bash
hostname -I | awk '{print $1}'
```

Example output: `172.20.10.2` (iPhone hotspot) or `192.168.1.x` (home WiFi)

### Step 2: Update the Worker App `.env`

Open `worker-app/.env` and replace **every** IP with your current one:

```env
EXPO_PUBLIC_API_HOST=<YOUR_IP>

EXPO_PUBLIC_WORKER_ID=6fc7ae56-8cc2-4d32-b8cf-c21844a177ce
EXPO_PUBLIC_POLICY_ID=21bc33f9-fa75-4a27-983b-df1a1b1fe4f1

EXPO_PUBLIC_WORKER_SERVICE=http://<YOUR_IP>:8001
EXPO_PUBLIC_POLICY_SERVICE=http://<YOUR_IP>:8002
EXPO_PUBLIC_TRIGGER_SERVICE=http://<YOUR_IP>:8003
EXPO_PUBLIC_CLAIMS_SERVICE=http://<YOUR_IP>:8004
EXPO_PUBLIC_PAYMENT_SERVICE=http://<YOUR_IP>:8005
EXPO_PUBLIC_ML_SERVICE=http://<YOUR_IP>:8006
```

> **CRITICAL**: The Worker ID and Policy ID above **must match** what `god_mode_demo.py` uses. These are already aligned.

### Step 3: Start Docker Services

```bash
docker compose -f docker-compose.demo.yml up -d
```

Verify all 12 containers are healthy:

```bash
docker ps --format "table {{.Names}}\t{{.Status}}"
```

### Step 4: Seed the Demo Database

```bash
python3 scripts/god_mode_demo.py seed
```

This creates:
- **Rider**: Arjun Kumar (Blinkit cyclist, Delhi Rohini zone)
- **Policy**: Standard tier, ₹127/week, active for 7 days
- **Zone**: Delhi Rohini with AQI/Heat/Rain triggers

### Step 5: Verify APIs Are Reachable (from laptop)

```bash
# Should return JSON with policy data (NOT "Not Found")
curl -s http://localhost:8002/api/v1/policies/worker/6fc7ae56-8cc2-4d32-b8cf-c21844a177ce | python3 -m json.tool | head -10

# Should return claims array
curl -s http://localhost:8004/api/v1/claims/worker/6fc7ae56-8cc2-4d32-b8cf-c21844a177ce | python3 -m json.tool | head -5

# Should return trigger status
curl -s http://localhost:8003/api/v1/trigger/status | python3 -m json.tool | head -5
```

### Step 6: Start Expo (with cache clear!)

```bash
cd worker-app
npx expo start -c
```

> **Always use `-c`** to ensure new env vars are picked up. Expo caches aggressively.

### Step 7: Scan QR Code on iPhone

Open the Camera app → scan the QR → it opens in Expo Go.

---

## 🐛 Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Network request failed` | Phone can't reach laptop | Check they're on the **same network** and IP in `.env` is correct |
| `HTTP 404` on policy | Worker ID mismatch or no policy seeded | Run `god_mode_demo.py seed` and verify `.env` uses `6fc7ae56...` |
| Coverage shows "Inactive" | Policy API returns null | Verify policy exists: `curl localhost:8002/api/v1/policies/worker/6fc7ae56...` |
| ₹0 everywhere | Claims/Payments empty for this worker | Run `god_mode_demo.py trigger --scenario clean` to generate claims |
| Errors after network switch | IP changed | Run `hostname -I`, update all IPs in `.env`, restart Expo with `-c` |
| `Port 8081 is running...` | Old Expo instance | Kill it: `kill $(lsof -t -i:8081)`, then restart |

---

## ⏱️ The 60-Second Demo Narration Sequence

### Setup Before Recording
1. **Split Screen**: Terminal on the **Left**, Phone mirror on the **Right**
2. **Clean State**: Run `python3 scripts/god_mode_demo.py seed` before starting
3. **Expo Go**: Open KavachAI app, verify policy shows "ACTIVE" with ₹127/week
4. **Quiet Mode**: Turn off Slack/WhatsApp notifications

### The Script

| Time | Action (Terminal/App) | Narration Script |
|:---|:---|:---|
| **T+00s** | **Terminal:** `python3 scripts/god_mode_demo.py trigger --scenario clean` | *"We're starting with a clean scenario. KavachAI just detected a severe AQI spike in Rohini, Delhi via our CPCB sensors."* |
| **T+02s** | **App:** Show Home Screen | *"On the rider app, Arjun sees 'Coverage Active'. The live AQI is dangerously high at 450, and the temperature is 38 degrees."* |
| **T+10s** | **App:** Tap 'My Policy' | *"Arjun is protected for just ₹127 a week. Our parametric engine watches for AQI, Rain, Heat, and even City Curfews."* |
| **T+18s** | **Terminal:** Watch 'Claim Created' logs | *"Back in the logs, you see the claim was auto-approved. A low fraud score of 0.08 means zero manual intervention was needed."* |
| **T+25s** | **App:** Tap 'Payouts' Tab | *"Instantly, Arjun sees a ₹300 credit in his history. No paperwork, no investigators, just instant relief."* |
| **T+28s** | **Phone:** Wait for FCM Push | *"And there's the Firebase push notification—Arjun knows his rent is safe before he even finishes his shift."* |
| **T+32s** | **Terminal:** `python3 scripts/god_mode_demo.py trigger --scenario spoofed` | *"Now, let's try to break it. A bad actor in Mumbai is spoofing their GPS to trick our Delhi sensors."* |
| **T+45s** | **Terminal:** Watch for `BLOCKED` | *"Our Layer 5 defense catches it immediately. Fraud score: 0.89. Hard-blocked. Zero payout."* |
| **T+50s** | **Terminal:** `curl -s -X POST http://localhost:8006/api/v1/premium/calculate -H "Content-Type: application/json" -d '{"city":"delhi_ncr","vehicle_type":"bicycle","coverage_tier":"standard","month":7,"historical_aqi_events_12m":45,"historical_rain_events_12m":28,"disruption_history_90d":15,"declared_daily_trips":30,"avg_daily_earnings":1100.0,"monthly_work_days":22}' \| python3 -m json.tool` | *"We don't hardcode prices. Here is our live ML engine weighing AQI risk and seasonality to price Arjun's specific zone."* |
| **T+58s** | **Terminal:** `curl -s http://localhost:8005/api/v1/payments/summary \| python3 -m json.tool` | *"Finally, our actuarial dashboard tracks real-time loss ratios, ensuring KavachAI stays solvent."* |
| **T+60s** | **STOP RECORDING** | *"ML pricing, parametric triggers, and fraud-proof infrastructure. That is KavachAI."* |

---

## 🚀 Rapid-Fire Commands (Copy/Paste)

### Happy Path (Delhi Clean)
```bash
python3 scripts/god_mode_demo.py trigger --scenario clean
```

### Hostile Path (Mumbai Spoof)
```bash
python3 scripts/god_mode_demo.py trigger --scenario spoofed
```

### ML Premium Breakdown (SHAP)
```bash
curl -s -X POST http://localhost:8006/api/v1/premium/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "city":"delhi_ncr",
    "vehicle_type":"bicycle",
    "coverage_tier":"standard",
    "month":7,
    "historical_aqi_events_12m":45,
    "historical_rain_events_12m":28,
    "disruption_history_90d":15,
    "declared_daily_trips":30,
    "avg_daily_earnings":1100.0,
    "monthly_work_days":22
  }' | python3 -m json.tool
```

### Actuarial Live Summary
```bash
curl -s http://localhost:8005/api/v1/payments/summary | python3 -m json.tool
```

### System Status Check
```bash
python3 scripts/god_mode_demo.py status
```

---


