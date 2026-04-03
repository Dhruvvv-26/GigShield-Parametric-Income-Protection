# KavachAI — Phase 2 Local Setup

## Prerequisites
- Docker + Docker Compose installed
- OpenWeatherMap free API key (optional — system works without it using `/trigger/test`)

## Start the Full Stack

```bash
# 1. Clone / navigate to project root
cd kavachai/

# 2. Copy environment file and add your OWM key (optional)
cp .env.example .env
# Edit .env if you have an OWM API key

# 3. Start everything with one command
docker compose up -d

# 4. Wait ~30 seconds for all services to be healthy
docker compose ps
# All services should show "healthy" or "running"

# 5. Seed demo data (50 workers + policies)
python scripts/seed_demo_data.py
```

## Verify Everything Is Working

```bash
# API Gateway health check
curl http://localhost:8000/health

# List all zones
curl http://localhost:8000/api/v1/zones

# Get a premium quote
curl -X POST http://localhost:8000/api/v1/premium/calculate \
  -H "Content-Type: application/json" \
  -d '{"city":"Delhi","vehicle_type":"bicycle","coverage_tier":"standard","declared_daily_income":1200,"risk_multiplier":2.6}'

# Register a worker
curl -X POST http://localhost:8000/api/v1/riders/register \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "+919999999999",
    "name": "Test Rider",
    "platform": "blinkit",
    "vehicle_type": "bicycle",
    "zone_code": "delhi_rohini",
    "declared_daily_trips": 30,
    "declared_daily_income": 1200,
    "work_hours_profile": "full_day",
    "upi_id": "test.rider@upi"
  }'

# Create a policy (use worker_id from above response)
curl -X POST http://localhost:8000/api/v1/policies/create \
  -H "Content-Type: application/json" \
  -d '{"worker_id": "<WORKER_ID>", "coverage_tier": "standard"}'
```

## ★ The Magic Moment — Live Demo ★

```bash
# Fire a test trigger (bypasses API polling — instant demo)
curl -X POST http://localhost:8000/api/v1/trigger/test \
  -H "Content-Type: application/json" \
  -d '{"zone_code":"delhi_rohini","event_type":"aqi_hazardous","value":450}'

# Wait 5 seconds, then check claims
curl http://localhost:8000/api/v1/claims

# Check payments (Razorpay test mode)
curl http://localhost:8000/api/v1/payments

# Check notifications
curl http://localhost:8000/api/v1/notifications/all
```

## Service Ports

| Service | Port | URL |
|---|---|---|
| API Gateway | 8000 | http://localhost:8000 |
| Worker Service | 8001 | http://localhost:8001/docs |
| Policy Service | 8002 | http://localhost:8002/docs |
| Trigger Engine | 8003 | http://localhost:8003/docs |
| Claims Service | 8004 | http://localhost:8004/docs |
| Payment Service | 8005 | http://localhost:8005/docs |
| Notification Svc | 8006 | http://localhost:8006/docs |
| Redpanda Console | 8080 | http://localhost:8080 |
| MLflow | 5000 | http://localhost:5000 |

## Useful Commands

```bash
# View logs for a specific service
docker compose logs -f trigger-engine
docker compose logs -f claims-service
docker compose logs -f payment-service

# View Redpanda topics
docker exec kavachai-redpanda rpk topic list

# Stop everything
docker compose down

# Full reset (deletes all data)
docker compose down -v
```
