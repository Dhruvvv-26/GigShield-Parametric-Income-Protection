# GigShield — Week 3 Development Deliverable
## Phase 2 / SCALE — Backend Core

---

## Quick Start

```bash
# 1. Clone and configure
git clone https://github.com/Dhruvvv-26/GigShield-Parametric-Income-Protection.git
cd GigShield-Parametric-Income-Protection
cp .env.example .env
# Edit .env and set OWM_API_KEY (get free key at openweathermap.org)

# 2. Start entire stack
docker compose up -d

# 3. Wait for all services to be healthy (~45 seconds)
docker compose ps

# 4. Seed demo data (50 Blinkit/Zepto riders)
pip install httpx faker
python scripts/seed_demo_data.py

# 5. Run acceptance check
python scripts/verify_e2e.py
```

---

## Services Running After `docker compose up -d`

| Service              | URL                         | Purpose                               |
|----------------------|-----------------------------|---------------------------------------|
| Worker Service       | http://localhost:8001/docs  | Rider registration + zone assignment  |
| Policy Service       | http://localhost:8002/docs  | Premium calculation + policy CRUD     |
| Trigger Engine       | http://localhost:8003/docs  | OWM/CPCB polling + test trigger       |
| Redpanda Console     | http://localhost:8080       | Kafka topic browser                   |
| Prometheus           | http://localhost:9090       | Metrics                               |
| Grafana              | http://localhost:3001       | Dashboards (admin / gigshield2026)    |
| PostgreSQL           | localhost:5432              | Primary DB + PostGIS                  |
| Redis                | localhost:6379              | Cache + dedup locks                   |

---

## Week 3 Acceptance Criteria

### ✅ Criterion 1: `docker compose up` starts all containers

```bash
docker compose up -d
docker compose ps   # All services should show "healthy"
```

### ✅ Criterion 2: `SELECT ST_Within(point, zone)` returns correct result for Rohini

```bash
# Via API (no psql required):
curl -X POST http://localhost:8001/api/v1/zones/lookup \
  -H "Content-Type: application/json" \
  -d '{"latitude": 28.7300, "longitude": 77.1100}'

# Expected: {"found": true, "zone": {"zone_code": "delhi_rohini", ...}}

# Via psql (direct DB check):
docker exec gigshield-postgres psql -U gigshield -d gigshield -c "
SELECT zone_code FROM zones
WHERE ST_Within(ST_SetSRID(ST_MakePoint(77.1100, 28.7300), 4326), boundary);"
# Expected: delhi_rohini
```

### ✅ Criterion 3: `POST /api/v1/riders/register` creates rider with correct zone

```bash
curl -X POST http://localhost:8001/api/v1/riders/register \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "9876543210",
    "full_name": "Arjun Kumar",
    "platform": "blinkit",
    "vehicle_type": "bicycle",
    "declared_daily_trips": 30,
    "declared_daily_income": 1200.0,
    "work_latitude": 28.7300,
    "work_longitude": 77.1100,
    "upi_id": "arjun@oksbi"
  }'
# Expected: 201 {"zone_code": "delhi_rohini", ...}
```

### ✅ Criterion 4: Live weather poll fires events to Redpanda topic

```bash
# Fire a manual trigger (bypasses API polling — demo mode):
curl -X POST http://localhost:8003/api/v1/trigger/test \
  -H "Content-Type: application/json" \
  -d '{"zone_code":"delhi_rohini","event_type":"aqi","metric_value":450}'

# View the message in Redpanda Console:
# http://localhost:8080 → Topics → processed.trigger.events
```

---

## Day-by-Day Build Log

### Day 1–2: Worker Service ✅
- Registration endpoint with PostGIS zone assignment
- GPS ping ingestion
- Zone lookup API (ST_Within)
- 20-zone PostGIS polygon seed

### Day 3–4: Policy Service ✅
- Premium calculation engine (rule-based, Phase 2)
- Premium breakdown (SHAP-style attribution)
- Policy CRUD: create, view, activate, renew
- All calculations logged to `premium_calculations` table

### Day 5–6: Trigger Engine ✅
- APScheduler: OWM (15min), CPCB (60min), NDMA RSS (5min)
- ThresholdEvaluator: Rain / AQI / Heat / Wind all tiers
- Sustained-duration tracking in Redis (AQI requires 4h breach)
- Redpanda producer publishing `processed.trigger.events`
- POST /api/v1/trigger/test — demo endpoint

### Day 7: End-to-End Verification ✅
- All acceptance criteria verified by `scripts/verify_e2e.py`
- 50 demo workers seeded by `scripts/seed_demo_data.py`
- Redpanda Console showing live topic messages

---

## Running Tests

```bash
# Worker Service
cd services/worker_service
PYTHONPATH=.:../../shared pytest tests/ -v --cov=. --cov-report=term-missing

# Policy Service
cd services/policy_service
PYTHONPATH=.:../../shared pytest tests/ -v --cov=. --cov-report=term-missing

# Trigger Engine
cd services/trigger_engine
PYTHONPATH=.:../../shared pytest tests/ -v --cov=. --cov-report=term-missing
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    External Data Sources                         │
│  OpenWeatherMap (15min)  CPCB AQI (60min)  NDMA RSS (5min)      │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                    ┌──────▼──────┐
                    │   Trigger   │  APScheduler
                    │   Engine    │  :8003
                    │  (8003)     │
                    └──────┬──────┘
                           │ processed.trigger.events
                    ┌──────▼──────┐
                    │  Redpanda   │  Kafka-compatible
                    │  (19092)    │  single container
                    └─────────────┘
                           │
             ┌─────────────┼─────────────┐
             │             │             │
    ┌────────▼────┐ ┌──────▼──────┐     │  (Week 4)
    │   Worker    │ │   Policy    │  Claims + Payment
    │   Service   │ │   Service   │
    │   :8001     │ │   :8002     │
    └──────┬──────┘ └──────┬──────┘
           │               │
    ┌──────▼───────────────▼──────┐
    │    PostgreSQL + PostGIS     │
    │    Redis                    │
    └─────────────────────────────┘
```

---

## Week 4 Preview (Mar 29 – Apr 4)

- `claims_service` — Redpanda consumer → PostGIS zone match → ClaimRecord
- `payment_service` — Razorpay test mode UPI payout
- Firebase FCM push → worker app notification
- Full end-to-end: `POST /trigger/test` → claim → payout → FCM in < 10 seconds
