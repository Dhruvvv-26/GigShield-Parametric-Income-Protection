# ⚖️ KavachAI: Judge's Step-by-Step Evaluation Guide

Welcome Guidewire DEVTrails Judges! This guide is designed to take you from a fresh `git clone` to a fully functioning 12-container microservice ecosystem running completely locally. 

By following these instructions, you will verify the End-to-End (E2E) parametric trigger flow, the Hybrid ML Fraud Engine, and the Razorpay API simulation. 

> [!IMPORTANT]  
> **No Cloud Sprawl:** Our entire architecture is containerized locally. We use 100% free external APIs (OpenWeatherMap, CPCB), avoiding the need to provide you with temporary AWS/GCP IAM roles. Everything you run will execute locally on your machine.

---

## 🛠️ Step 1: System Prerequisites
Ensure your local environment meets the following specifications:
1. **Git** installed.
2. **Docker Desktop** (or Docker Engine + Docker Compose v2) installed and running.
   - *Note for Mac/Windows users:* Allocate at least **6GB RAM** and **4 CPU cores** in Docker Desktop settings to comfortably handle the 11 Machine Learning models and Kafka/Redpanda broker.
3. **Python 3.11+** installed locally (only needed if you wish to run the external simulation scripts).

---

## 📥 Step 2: Clone & Configure

**1. Clone the repository:**
```bash
git clone https://github.com/Dhruvvv-26/KavachAI.git
cd KavachAI
```

**2. Setup the Environment Variables:**
We have provided a comprehensive `.env.example` file. Standard API keys for free-tier weather data are either already included in the example or can be safely bypassed by the backend's "fail-closed" fallback mechanisms if they hit rate limits.

```bash
# Copy the example file to create your active .env
cp .env.example .env
```
*(Open `.env` to verify the DB passwords and Kafka broker URLs match default localhost expectations.)*

---

## 🚀 Step 3: Spinning Up the Matrix 

KavachAI uses a complex but fully orchestrated `docker-compose.yml` file. 

**1. Build and Boot the Services:**
This command will pull the base images (PostgreSQL with PostGIS, Redis, Redpanda) and compile the 6 custom FastAPI microservices.
```bash
docker compose up -d --build
```
> *Depending on your internet speed, the ML-Service image may take 2-4 minutes to build as it downloads PyTorch, XGBoost, and LightGBM binaries.*

**2. Verify System Health:**
Once the terminal returns to the prompt, the services will begin their internal boot sequences. Wait approximately **45 to 60 seconds**, then run this command to verify all services are active:
```bash
for port in 8001 8002 8003 8004 8005 8006; do curl -sf http://localhost:$port/health; echo ""; done
```
You are looking for every service to return `"status": "healthy"`. 
*(Particularly, check that `ml-service` on port `8006` reports `"models_loaded": 11`)*

---

## 🏗️ Step 4: Accessing the Observability GUIs

Before running transactions, you can visually inspect the infrastructure:
*   **Redpanda Console (Message Broker GUI):** `http://localhost:8080`
    *   *Verify the topics exist:* `raw.trigger.events`, `processed.trigger.events`, `claims.approved`
*   **Grafana (Metrics Dashboard):** `http://localhost:3001`
    *   *Login:* `admin` / `admin` (skip password reset)

---

## 🎭 Step 5: The Phase 2 Evaluation Flow (API Testing)

You don't need a UI to verify massive backend processing! You can execute these test sequences from your terminal to watch the microservices communicate asynchronously.

### Pre-Requisite: Seeding Test Data
Before simulating triggers, we must register a "test rider" and bind them to an active policy using our God Mode script.
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install requests psycopg2-binary
python3 scripts/god_mode_demo.py seed
```

### Scenario A: Rider Premium Generation (ML Engine)
Test our XGBoost/LightGBM active pricing engine. KavachAI prices risk dynamically using geographic and weather datasets.
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
**👀 What to notice:** Look at the `shap_breakdown` in the JSON response. The engine isn't hardcoding premiums; it's weighing variables mathematically.

### Scenario B: The "Happy Path" Payout (Zero-Touch Validation)
Let's simulate the `trigger-engine` detecting terrible Air Quality (AQI) in Delhi.
```bash
curl -s -X POST http://localhost:8003/api/v1/trigger/test \
  -H "Content-Type: application/json" \
  -d '{
    "zone_code":"delhi_rohini",
    "event_type":"aqi",
    "metric_value":450,
    "scenario":"clean"
  }' | python3 -m json.tool
```
**👀 What to notice:** 
1. This hits Redpanda. The `claims-service` consumes it, verifies the simulated GPS coordinates against PostGIS, approves it, and pushes it back to Redpanda. 
2. The `payment-service` consumes the approval, simulates a Razorpay transaction, and pushes a receipt to Redis. 
*Verify the final payout notification landed in Redis:*
```bash
docker exec redis redis-cli -a redis_secure_2026 --raw LRANGE notifications:all 0 1 2>/dev/null | python3 -m json.tool
```

### Scenario C: The "Hostile Path" (Geofence Fraud Defense)
Let's simulate a bad actor attempting to spoof their GPS to claim an AQI payout happening in Delhi, using a Mock Location app and zero physical movement.
```bash
curl -s -X POST http://localhost:8003/api/v1/trigger/test \
  -H "Content-Type: application/json" \
  -d '{
    "zone_code":"delhi_rohini",
    "event_type":"aqi",
    "metric_value":500,
    "scenario":"spoofed"
  }' | python3 -m json.tool
```
**👀 What to notice:** 
Look at the local logs for the claims service:
```bash
docker logs claims-service | tail -n 20
```
You will see the Layer 5 Zero-Trust engine immediately hard-block the claim. The ML engine detects multiple contradictory data points like `fraud_flags: ["MOCK_LOCATION_DETECTED", "GPS_INSTANT_LOCK_228ms"]` because the defense engine exposes the fake telemetry.

### Scenario D: The Actuarial Financial Dashboard
Verify the loss-ratio logic processing the transactions you just generated:
```bash
curl -s http://localhost:8005/api/v1/payments/summary | python3 -m json.tool
```
**👀 What to notice:** We calculate live metrics tracking `$ total_premiums` against `$ total_payouts` ensuring the platform remains mathematically solvent over time.

---

## 🧹 Step 6: Teardown
When you are completely finished evaluating the project, you can cleanly wipe the entire environment from your system without leaving dangling volumes:
```bash
docker compose down -v
```

> **Thank you for evaluating KavachAI Phase 2!**
