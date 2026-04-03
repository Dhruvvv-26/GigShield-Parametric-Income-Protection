"""
Trigger Engine — Test Trigger Endpoint
POST /api/v1/trigger/test

THE DEMO CENTREPIECE.
Bypasses API polling, fires a trigger event directly into Redpanda.
Used for live judge demos and smoke testing.

Usage:
  # Clean rider (auto-approved):
  curl -X POST http://localhost:8003/api/v1/trigger/test \\
    -H "Content-Type: application/json" \\
    -d '{"zone_code":"delhi_rohini","event_type":"aqi","metric_value":450,"scenario":"clean"}'

  # Suspicious rider (soft-hold):
  curl -X POST ... -d '{"...","scenario":"suspicious"}'

  # Spoofed rider (blocked):
  curl -X POST ... -d '{"...","scenario":"spoofed"}'

Expected end-to-end time: < 10 seconds from this call to FCM push.
"""
import logging
import random
import time
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from integrations.threshold_evaluator import ThresholdEvaluator
from integrations.zone_resolver import ZoneResolver
from shared.config import get_settings
from shared.database import get_db
from shared.logging_config import get_logger
from shared.messaging import KavachAIProducer

logger = get_logger(__name__)
router = APIRouter()
settings = get_settings()
evaluator = ThresholdEvaluator()
zone_resolver = ZoneResolver()


# ── Sensor Payload Presets ───────────────────────────────────────────────────

def _build_sensor_payload(scenario: str) -> dict:
    """
    Build realistic sensor payloads for three demo scenarios.
    Each produces a fraud score in a predictable range.
    """
    base_ts = int(time.time() * 1000)

    if scenario == "suspicious":
        # fraud_score target: 0.45–0.65 → SOFT_HOLD
        return {
            "gps_pings": [
                {
                    "lat": 28.7041 + random.gauss(0, 0.000008),
                    "lng": 77.1025 + random.gauss(0, 0.000008),
                    "accuracy_m": random.uniform(1, 3),
                    "timestamp": datetime.fromtimestamp(
                        (base_ts + i * 5000) / 1000, tz=timezone.utc
                    ).isoformat(),
                }
                for i in range(5)
            ],
            "gps_cold_start_ms": random.randint(800, 2000),
            "accelerometer_rms": random.uniform(0.15, 0.35),
            "gyroscope_yaw_rate": random.uniform(0.02, 0.06),
            "is_mock_location": False,
            "is_developer_mode": False,
            "ip_geo_lat": 28.7041 + random.uniform(0.025, 0.04),
            "ip_geo_lng": 77.1025 + random.uniform(0.025, 0.04),
            "tower_handoffs_30min": random.randint(0, 1),
            "zone_resident_t_minus_30": False,
            "claims_in_window_same_zone": random.randint(15, 40),
        }

    elif scenario == "spoofed":
        # fraud_score target: 0.85–1.00 → BLOCKED
        return {
            "gps_pings": [
                {
                    "lat": 28.7041 + random.gauss(0, 0.0000008),
                    "lng": 77.1025 + random.gauss(0, 0.0000008),
                    "accuracy_m": random.uniform(0.1, 0.5),
                    "timestamp": datetime.fromtimestamp(
                        (base_ts + i * 5000) / 1000, tz=timezone.utc
                    ).isoformat(),
                }
                for i in range(5)
            ],
            "gps_cold_start_ms": random.randint(50, 300),
            "accelerometer_rms": random.uniform(0.01, 0.08),
            "gyroscope_yaw_rate": random.uniform(0.001, 0.01),
            "is_mock_location": True,
            "is_developer_mode": True,
            "ip_geo_lat": 28.7041 + random.uniform(0.06, 0.14),
            "ip_geo_lng": 77.1025 + random.uniform(0.06, 0.14),
            "tower_handoffs_30min": 0,
            "zone_resident_t_minus_30": False,
            "claims_in_window_same_zone": random.randint(120, 180),
        }

    else:
        # "clean" — fraud_score target: 0.10–0.25 → APPROVED
        return {
            "gps_pings": [
                {
                    "lat": 28.7041 + random.gauss(0, 0.00004),
                    "lng": 77.1025 + random.gauss(0, 0.00004),
                    "accuracy_m": random.uniform(6, 18),
                    "timestamp": datetime.fromtimestamp(
                        (base_ts + i * 5000) / 1000, tz=timezone.utc
                    ).isoformat(),
                }
                for i in range(5)
            ],
            "gps_cold_start_ms": random.randint(18000, 42000),
            "accelerometer_rms": random.uniform(0.9, 2.2),
            "gyroscope_yaw_rate": random.uniform(0.12, 0.25),
            "is_mock_location": False,
            "is_developer_mode": False,
            "ip_geo_lat": 28.7041 + random.uniform(-0.015, 0.015),
            "ip_geo_lng": 77.1025 + random.uniform(-0.015, 0.015),
            "tower_handoffs_30min": random.randint(3, 6),
            "zone_resident_t_minus_30": True,
            "claims_in_window_same_zone": random.randint(1, 8),
        }


class TriggerTestRequest(BaseModel):
    """
    Manual trigger payload for demo and testing.
    Mirrors the shape of a real processed.trigger.events message.
    """
    zone_code: str = Field(
        ...,
        description="Zone code to trigger. e.g. 'delhi_rohini', 'mumbai_kurla'",
        examples=["delhi_rohini"],
    )
    event_type: str = Field(
        ...,
        description="Trigger type: aqi | heavy_rain | extreme_heat | cyclone | curfew | flood_alert",
        examples=["aqi"],
    )
    metric_value: float = Field(
        ...,
        description="Metric value: AQI reading | rainfall mm | temperature °C | wind km/h",
        examples=[450.0],
    )
    scenario: str = Field(
        "clean",
        description="Sensor preset: 'clean' (auto-approve), 'suspicious' (soft-hold), 'spoofed' (blocked)",
        examples=["clean"],
    )
    tier: str | None = Field(
        None,
        description="Override tier. If not set, auto-calculated from metric_value.",
    )
    payout_override: int | None = Field(
        None,
        description="Override payout amount in ₹. If not set, auto-calculated from tier.",
    )


class TriggerTestResponse(BaseModel):
    triggered: bool
    zone_code: str
    zone_id: str
    city: str
    event_type: str
    tier: str
    metric_value: float
    payout_amount: int
    scenario: str
    sensor_data: dict
    message_id: str
    redpanda_topic: str
    timestamp: str


@router.post(
    "/test",
    response_model=TriggerTestResponse,
    summary="🔥 Fire a test trigger event (DEMO)",
    description="""
    **THE DEMO ENDPOINT.**

    Bypasses all API polling and fires a trigger event directly into Redpanda.
    Use this to show judges the full pipeline (3 scenarios):

    ```bash
    # Clean rider → auto-approve
    curl -X POST http://localhost:8003/api/v1/trigger/test \\
      -H "Content-Type: application/json" \\
      -d '{"zone_code":"delhi_rohini","event_type":"aqi","metric_value":450,"scenario":"clean"}'

    # Suspicious rider → soft-hold
    curl ... -d '{"...","scenario":"suspicious"}'

    # GPS spoofed → blocked
    curl ... -d '{"...","scenario":"spoofed"}'
    ```
    """,
)
async def fire_test_trigger(
    payload: TriggerTestRequest,
    db: AsyncSession = Depends(get_db),
) -> TriggerTestResponse:

    # ── Resolve zone ──────────────────────────────────────────────────────────
    zone = await zone_resolver.get_zone_by_code(db, payload.zone_code)
    if not zone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Zone '{payload.zone_code}' not found. "
                f"Valid zones: delhi_rohini, mumbai_kurla, bengaluru_koramangala, ..."
            ),
        )

    # ── Auto-evaluate tier and payout ─────────────────────────────────────────
    if payload.tier and payload.payout_override:
        tier = payload.tier
        payout = payload.payout_override
    else:
        evaluation_map = {
            "aqi":          evaluator.evaluate_aqi(int(payload.metric_value)),
            "heavy_rain":   evaluator.evaluate_rain(payload.metric_value),
            "extreme_heat": evaluator.evaluate_heat(payload.metric_value),
            "cyclone":      evaluator.evaluate_wind(payload.metric_value),
            "flood_alert":  {"triggered": True, "tier": "tier2", "payout": 380},
            "curfew":       {"triggered": True, "tier": "tier2", "payout": 400},
        }

        eval_result = evaluation_map.get(
            payload.event_type,
            {"triggered": True, "tier": "tier1", "payout": 200},
        )
        tier   = payload.tier or eval_result.get("tier", "tier1")
        payout = payload.payout_override or eval_result.get("payout", 200)

    # ── Build sensor payload from scenario preset ─────────────────────────────
    sensor_data = _build_sensor_payload(payload.scenario)

    # ── Build and emit message ────────────────────────────────────────────────
    now = datetime.now(timezone.utc)

    event_payload = {
        "zone_id":       str(zone.id),
        "zone_code":     zone.zone_code,
        "city":          zone.city,
        "event_type":    payload.event_type,
        "tier":          tier,
        "metric_value":  payload.metric_value,
        "metric_unit":   _metric_unit_for(payload.event_type),
        "payout_amount": payout,
        "data_source":   "test_endpoint",
        "detected_at":   now.isoformat(),
        "is_test":       True,
        "scenario":      payload.scenario,
        "sensor_data":   sensor_data,  # Pre-seeded realistic sensor payload
    }

    # Get producer from app state
    from main import producer as global_producer
    await global_producer.publish(
        topic=settings.topic_processed_trigger_events,
        event_type=f"trigger.{payload.event_type}.{tier}",
        payload=event_payload,
        source_service="trigger-engine-test",
        key=zone.zone_code,
    )

    logger.info(
        "Test trigger fired",
        zone=zone.zone_code,
        event_type=payload.event_type,
        tier=tier,
        payout=payout,
        metric_value=payload.metric_value,
        scenario=payload.scenario,
    )

    # Build response
    import uuid
    return TriggerTestResponse(
        triggered=True,
        zone_code=zone.zone_code,
        zone_id=str(zone.id),
        city=zone.city,
        event_type=payload.event_type,
        tier=tier,
        metric_value=payload.metric_value,
        payout_amount=payout,
        scenario=payload.scenario,
        sensor_data=sensor_data,
        message_id=str(uuid.uuid4()),
        redpanda_topic=settings.topic_processed_trigger_events,
        timestamp=now.isoformat(),
    )


def _metric_unit_for(event_type: str) -> str:
    units = {
        "aqi":          "aqi",
        "heavy_rain":   "mm",
        "extreme_heat": "celsius",
        "cyclone":      "kmh",
        "flood_alert":  "alert",
        "curfew":       "alert",
    }
    return units.get(event_type, "unit")
