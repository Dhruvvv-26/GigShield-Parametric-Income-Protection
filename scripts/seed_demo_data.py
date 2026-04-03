#!/usr/bin/env python3
"""
KavachAI — Demo Seed Script
Seeds 50 fake Blinkit/Zepto riders with active policies for the demo.

Usage:
    python scripts/seed_demo_data.py

Requires:
    pip install httpx faker

Services must be running:
    docker compose up -d worker-service policy-service
"""
import asyncio
import random
import httpx
from faker import Faker

fake = Faker("en_IN")

WORKER_SERVICE_URL = "http://localhost:8001"
POLICY_SERVICE_URL = "http://localhost:8002"

ZONES = [
    {"zone_code": "delhi_rohini",          "lat": 28.7300, "lon": 77.1100},
    {"zone_code": "delhi_dwarka",          "lat": 28.5750, "lon": 76.9950},
    {"zone_code": "delhi_lajpat_nagar",    "lat": 28.5730, "lon": 77.2500},
    {"zone_code": "delhi_karol_bagh",      "lat": 28.6500, "lon": 77.1950},
    {"zone_code": "delhi_saket",           "lat": 28.5300, "lon": 77.2150},
    {"zone_code": "gurgaon_cyber_city",    "lat": 28.5050, "lon": 77.0900},
    {"zone_code": "mumbai_kurla",          "lat": 19.0725, "lon": 72.8850},
    {"zone_code": "mumbai_andheri_west",   "lat": 19.1350, "lon": 72.8375},
    {"zone_code": "mumbai_bandra",         "lat": 19.0650, "lon": 72.8375},
    {"zone_code": "bengaluru_koramangala", "lat": 12.9325, "lon": 77.6350},
    {"zone_code": "bengaluru_hsr_layout",  "lat": 12.9100, "lon": 77.6575},
    {"zone_code": "hyderabad_hitech_city", "lat": 17.4550, "lon": 78.3850},
    {"zone_code": "pune_kothrud",          "lat": 18.5125, "lon": 73.8250},
    {"zone_code": "kolkata_salt_lake",     "lat": 22.5850, "lon": 88.4150},
]

PLATFORMS     = ["blinkit", "blinkit", "blinkit", "zepto", "zepto"]
VEHICLE_TYPES = ["bicycle", "bicycle", "bicycle", "e_bike", "motorcycle"]
WORK_HOURS    = ["full_day", "full_day", "peak_only", "morning_only"]
TIERS         = ["standard", "standard", "basic", "premium"]

ZONE_WORKER_COUNTS = {
    "delhi_rohini":          8,
    "mumbai_kurla":          7,
    "delhi_dwarka":          4,
    "mumbai_andheri_west":   4,
    "bengaluru_koramangala": 4,
    "delhi_karol_bagh":      3,
    "mumbai_bandra":         3,
    "bengaluru_hsr_layout":  3,
    "hyderabad_hitech_city": 3,
    "delhi_lajpat_nagar":    3,
    "delhi_saket":           2,
    "pune_kothrud":          2,
    "gurgaon_cyber_city":    2,
    "kolkata_salt_lake":     2,
}


def _random_phone() -> str:
    prefix = random.choice(["6", "7", "8", "9"])
    return prefix + "".join([str(random.randint(0, 9)) for _ in range(9)])


def _jitter(lat: float, lon: float, d: float = 0.008) -> tuple:
    return (lat + random.uniform(-d, d), lon + random.uniform(-d, d))


async def register_worker(client: httpx.AsyncClient, zone: dict, idx: int) -> dict | None:
    lat, lon = _jitter(zone["lat"], zone["lon"])
    payload = {
        "phone_number":         _random_phone(),
        "full_name":            fake.name(),
        "platform":             random.choice(PLATFORMS),
        "platform_partner_id":  f"GS-{zone['zone_code'][:3].upper()}-{idx:04d}",
        "vehicle_type":         random.choice(VEHICLE_TYPES),
        "work_hours_profile":   random.choice(WORK_HOURS),
        "declared_daily_trips": random.randint(20, 35),
        "declared_daily_income": round(random.uniform(900, 1400), 2),
        "home_pincode":         "110085",
        "work_latitude":        round(lat, 6),
        "work_longitude":       round(lon, 6),
        "upi_id":               f"rider{idx:04d}@oksbi",
    }
    try:
        r = await client.post(f"{WORKER_SERVICE_URL}/api/v1/riders/register",
                              json=payload, timeout=10.0)
        if r.status_code == 201:
            data = r.json()
            print(f"  ✓ [{idx:02d}] {payload['full_name']} → {data['zone_code']}")
            return data
        elif r.status_code == 409:
            print(f"  ↩ [{idx:02d}] Phone already registered (skip)")
        else:
            print(f"  ✗ [{idx:02d}] HTTP {r.status_code}: {r.text[:80]}")
    except httpx.ConnectError:
        print(f"  ✗ Cannot reach Worker Service. Is it running?")
    return None


async def create_policy(client: httpx.AsyncClient, worker_id: str, idx: int) -> bool:
    payload = {
        "worker_id":           worker_id,
        "coverage_tier":       random.choice(TIERS),
        "razorpay_payment_id": f"pay_demo_{worker_id[:8]}",
    }
    try:
        r = await client.post(f"{POLICY_SERVICE_URL}/api/v1/policies",
                              json=payload, timeout=10.0)
        if r.status_code in (201, 409):
            if r.status_code == 201:
                d = r.json()
                print(f"  ✓ Policy [{idx:02d}] ₹{d['weekly_premium']}/wk "
                      f"({d['coverage_tier']}) status={d['status']}")
            return True
        else:
            print(f"  ✗ Policy [{idx:02d}] HTTP {r.status_code}: {r.text[:80]}")
    except httpx.ConnectError:
        print(f"  ✗ Cannot reach Policy Service. Is it running?")
    return False


async def main():
    print("=" * 60)
    print("  KavachAI — Demo Data Seeder")
    print("=" * 60)

    async with httpx.AsyncClient() as client:
        for name, url in [("Worker Service", WORKER_SERVICE_URL),
                          ("Policy Service", POLICY_SERVICE_URL)]:
            try:
                r = await client.get(f"{url}/health", timeout=5.0)
                status = "✓ healthy" if r.status_code == 200 else f"✗ {r.status_code}"
            except httpx.ConnectError:
                status = "✗ not reachable"
                print(f"  {name}: {status}")
                print(f"  → Run: docker compose up -d")
                return
            print(f"  {name}: {status}")

    print()
    workers_ok = policies_ok = idx = 0

    async with httpx.AsyncClient() as client:
        for zone in ZONES:
            count = ZONE_WORKER_COUNTS.get(zone["zone_code"], 2)
            print(f"\n📍 {zone['zone_code']} ({count} riders)")
            for _ in range(count):
                idx += 1
                w = await register_worker(client, zone, idx)
                if w:
                    workers_ok += 1
                    if await create_policy(client, w["worker_id"], idx):
                        policies_ok += 1
                await asyncio.sleep(0.08)

    print()
    print("=" * 60)
    print(f"  Workers registered : {workers_ok}")
    print(f"  Policies created   : {policies_ok}")
    print()
    print("  🔥 Fire a test trigger:")
    print()
    print("  curl -X POST http://localhost:8003/api/v1/trigger/test \\")
    print("    -H 'Content-Type: application/json' \\")
    print("    -d '{\"zone_code\":\"delhi_rohini\",\"event_type\":\"aqi\","
          "\"metric_value\":450}'")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
