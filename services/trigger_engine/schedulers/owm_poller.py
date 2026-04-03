"""
Trigger Engine — OpenWeatherMap Poller
Polls current weather for all 6 Phase-1 cities.
Evaluates: Heavy Rain (Tier 1/2/3) + Extreme Heat (Tier 1/2/3).
Emits events to Redpanda: raw.external.events
"""
import logging
import time
from datetime import datetime, timezone

import httpx

from shared.config import get_settings
from shared.database import get_db_context
from shared.messaging import GigShieldProducer
from shared.redis_client import cache_get, cache_set

from integrations.threshold_evaluator import ThresholdEvaluator
from integrations.zone_resolver import ZoneResolver

logger = logging.getLogger(__name__)
settings = get_settings()


# OWM city coordinates for Phase-1 cities (centroid used for API call)
# Zone-level matching done in PostGIS after event emission
OWM_CITIES: dict[str, dict] = {
    "delhi_ncr": {
        "lat": 28.6139, "lon": 77.2090, "name": "Delhi",
        "owm_city_id": "1273294",
    },
    "mumbai": {
        "lat": 19.0760, "lon": 72.8777, "name": "Mumbai",
        "owm_city_id": "1275339",
    },
    "bengaluru": {
        "lat": 12.9716, "lon": 77.5946, "name": "Bengaluru",
        "owm_city_id": "1277333",
    },
    "hyderabad": {
        "lat": 17.3850, "lon": 78.4867, "name": "Hyderabad",
        "owm_city_id": "1269843",
    },
    "pune": {
        "lat": 18.5204, "lon": 73.8567, "name": "Pune",
        "owm_city_id": "1259229",
    },
    "kolkata": {
        "lat": 22.5726, "lon": 88.3639, "name": "Kolkata",
        "owm_city_id": "1275004",
    },
}


class OpenWeatherMapPoller:
    """
    Polls OWM /weather endpoint for each Phase-1 city.
    Rate: 15-minute intervals = 96 calls/day across 6 cities.
    Free limit: 1,000 calls/day. Headroom: 10×.

    On threshold breach:
      - Emits event to Redpanda: processed.trigger.events
      - Stores breach start time in Redis for sustained-duration check
    """

    def __init__(self, producer: GigShieldProducer):
        self.producer = producer
        self.evaluator = ThresholdEvaluator()
        self.zone_resolver = ZoneResolver()

    async def run(self) -> None:
        """
        Main poll cycle — called by APScheduler every 15 minutes.
        Polls all 6 cities in sequence (async HTTP).
        """
        logger.info("OWM poll cycle starting...")
        start = time.monotonic()

        async with httpx.AsyncClient(timeout=10.0) as client:
            for city_key, city_config in OWM_CITIES.items():
                try:
                    await self._poll_city(client, city_key, city_config)
                except Exception as e:
                    logger.error(
                        f"OWM poll failed for {city_key}",
                        exc_info=e,
                    )

        elapsed = time.monotonic() - start
        logger.info(f"OWM poll cycle complete | elapsed_seconds={round(elapsed, 2)}")

    async def _poll_city(
        self,
        client: httpx.AsyncClient,
        city_key: str,
        city_config: dict,
    ) -> None:
        """Fetch current weather for one city, evaluate thresholds, emit events."""

        # ── Fetch from OWM ────────────────────────────────────────────────────
        if settings.owm_api_key == "demo_key_replace_me":
            # Demo mode: return mock data so engine works without real API key
            weather_data = _mock_owm_response(city_key)
        else:
            resp = await client.get(
                f"{settings.owm_base_url}/weather",
                params={
                    "lat": city_config["lat"],
                    "lon": city_config["lon"],
                    "appid": settings.owm_api_key,
                    "units": "metric",
                },
            )
            resp.raise_for_status()
            weather_data = resp.json()

        # ── Extract metrics ───────────────────────────────────────────────────
        temp_celsius  = weather_data.get("main", {}).get("temp", 25.0)
        rain_1h_mm    = weather_data.get("rain", {}).get("1h", 0.0)
        rain_3h_mm    = weather_data.get("rain", {}).get("3h", 0.0)
        # OWM gives 1h and 3h rain. Extrapolate to 24h for threshold comparison:
        # Use 3h value × 8 as daily proxy — conservative estimate
        rain_24h_est  = max(rain_1h_mm * 24, rain_3h_mm * 8)
        wind_speed_ms = weather_data.get("wind", {}).get("speed", 0.0)
        wind_kmh      = wind_speed_ms * 3.6

        now = datetime.now(timezone.utc)

        # ── Evaluate: Heavy Rain ──────────────────────────────────────────────
        rain_result = self.evaluator.evaluate_rain(rain_24h_est)
        if rain_result["triggered"]:
            await self._handle_trigger(
                city_key=city_key,
                event_type="heavy_rain",
                tier=rain_result["tier"],
                metric_value=rain_24h_est,
                metric_unit="mm",
                payout_amount=rain_result["payout"],
                raw_payload=weather_data,
                source="openweathermap",
            )

        # ── Evaluate: Extreme Heat ────────────────────────────────────────────
        heat_result = self.evaluator.evaluate_heat(temp_celsius)
        if heat_result["triggered"]:
            # Heat triggers only count 10AM–5PM (peak outdoor work hours)
            if 10 <= now.hour <= 17:
                await self._handle_trigger(
                    city_key=city_key,
                    event_type="extreme_heat",
                    tier=heat_result["tier"],
                    metric_value=temp_celsius,
                    metric_unit="celsius",
                    payout_amount=heat_result["payout"],
                    raw_payload=weather_data,
                    source="openweathermap",
                )

        # ── Evaluate: Cyclone / Wind ──────────────────────────────────────────
        wind_result = self.evaluator.evaluate_wind(wind_kmh)
        if wind_result["triggered"]:
            await self._handle_trigger(
                city_key=city_key,
                event_type="cyclone",
                tier=wind_result["tier"],
                metric_value=wind_kmh,
                metric_unit="kmh",
                payout_amount=wind_result["payout"],
                raw_payload=weather_data,
                source="openweathermap",
            )

        # Update last-poll timestamp metric
        from main import LAST_POLL_TIMESTAMP
        LAST_POLL_TIMESTAMP.labels(source="openweathermap").set(now.timestamp())

    async def _handle_trigger(
        self,
        city_key: str,
        event_type: str,
        tier: str,
        metric_value: float,
        metric_unit: str,
        payout_amount: int,     
        raw_payload: dict,
        source: str,
    ) -> None:
        """
        Deduplication → Zone resolution → Persist to DB → Emit to Redpanda.
        """
        dedup_key = f"trigger:{city_key}:{event_type}:{tier}"
        if await cache_get(dedup_key):
            logger.debug(f"Trigger {dedup_key} already active — skipping emit")
            return

        # Resolve all zones in this city affected by the trigger
        async with get_db_context() as db:
            zones = await self.zone_resolver.get_zones_for_city(db, city_key)
            for zone in zones:
                await self._emit_trigger_event(
                    zone_id=str(zone.id),
                    zone_code=zone.zone_code,
                    city=city_key,
                    event_type=event_type,
                    tier=tier,
                    metric_value=metric_value,
                    metric_unit=metric_unit,
                    payout_amount=payout_amount,
                    raw_payload=raw_payload,
                    source=source,
                )

        # Cache to prevent duplicate emissions for 30 minutes
        # (sustained-duration check happens in ThresholdEvaluator)
        await cache_set(dedup_key, "1", ttl=1800)

        logger.info(f"Trigger event fired | city={city_key} | event_type={event_type} | tier={tier} | metric_value={metric_value}")

        from main import TRIGGER_EVENTS_TOTAL
        TRIGGER_EVENTS_TOTAL.labels(
            event_type=event_type, tier=tier, city=city_key
        ).inc()

    async def _emit_trigger_event(
        self,
        zone_id: str,
        zone_code: str,
        city: str,
        event_type: str,
        tier: str,
        metric_value: float,
        metric_unit: str,
        payout_amount: int,
        raw_payload: dict,
        source: str,
    ) -> None:
        """Publish one trigger event per zone to Redpanda."""
        payload = {
            "zone_id":      zone_id,
            "zone_code":    zone_code,
            "city":         city,
            "event_type":   event_type,
            "tier":         tier,
            "metric_value": metric_value,
            "metric_unit":  metric_unit,
            "payout_amount": payout_amount,
            "data_source":  source,
            "detected_at":  datetime.now(timezone.utc).isoformat(),
        }

        await self.producer.publish(
            topic=settings.topic_processed_trigger_events,
            event_type=f"trigger.{event_type}.{tier}",
            payload=payload,
            source_service="trigger-engine",
            key=zone_code,   # Partition by zone for ordering
        )


def _mock_owm_response(city_key: str) -> dict:
    """
    Mock OWM response for demo/development (no API key required).
    Returns realistic data for each city.
    """
    mock_data = {
        "delhi_ncr":  {"main": {"temp": 44.0}, "rain": {"1h": 0.0, "3h": 0.0}, "wind": {"speed": 8.0}},
        "mumbai":     {"main": {"temp": 32.0}, "rain": {"1h": 5.5, "3h": 15.0}, "wind": {"speed": 12.0}},
        "bengaluru":  {"main": {"temp": 28.0}, "rain": {"1h": 2.0, "3h": 5.0},  "wind": {"speed": 6.0}},
        "hyderabad":  {"main": {"temp": 41.0}, "rain": {"1h": 0.0, "3h": 0.0},  "wind": {"speed": 9.0}},
        "pune":       {"main": {"temp": 35.0}, "rain": {"1h": 3.0, "3h": 8.0},  "wind": {"speed": 7.0}},
        "kolkata":    {"main": {"temp": 36.0}, "rain": {"1h": 1.0, "3h": 3.0},  "wind": {"speed": 10.0}},
    }
    return mock_data.get(city_key, {"main": {"temp": 30.0}, "rain": {}, "wind": {"speed": 5.0}})
