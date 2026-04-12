"""
Trigger Engine — CPCB AQI Poller
Polls India's Central Pollution Control Board for real-time AQI data.
CPCB portal: https://api.data.gov.in — government API, no rate limits.
Evaluates: AQI Tier 1 (>300), Tier 2 (>400), Tier 3 (>500)
"""
import logging
import time
from datetime import datetime, timezone

import httpx

from shared.config import get_settings
from shared.database import get_db_context
from shared.messaging import KavachAIProducer
from shared.redis_client import cache_get, cache_set

from integrations.threshold_evaluator import ThresholdEvaluator
from integrations.zone_resolver import ZoneResolver

logger = logging.getLogger(__name__)
settings = get_settings()

CPCB_STATION_CITY_MAP: dict[str, str] = {
    "DTH": "delhi_ncr",
    "MUM": "mumbai",
    "BLR": "bengaluru",
    "HYD": "hyderabad",
    "PUN": "pune",
    "KOL": "kolkata",
}

MOCK_AQI_VALUES: dict[str, int] = {
    "delhi_ncr": 342,
    "mumbai":    178,
    "bengaluru":  95,
    "hyderabad": 210,
    "pune":      145,
    "kolkata":   280,
}


class CPCBPoller:
    """
    Polls WAQI AQI endpoint every 60 minutes.
    AQI thresholds (PM2.5 standard):
      Tier 1: AQI > 300, sustained 4+ hours → ₹150 payout
      Tier 2: AQI > 400, sustained 3+ hours → ₹300 payout
      Tier 3: AQI > 500 OR GRAP Stage IV    → ₹500 payout
    """

    AQI_BREACH_DURATION_KEY = "aqi_breach_start:{city}:{tier}"
    REQUIRED_DURATION_HOURS = {
        "tier1": 4,
        "tier2": 3,
        "tier3": 1,
    }

    def __init__(self, producer: KavachAIProducer):
        self.producer = producer
        self.evaluator = ThresholdEvaluator()
        self.zone_resolver = ZoneResolver()

    async def run(self) -> None:
        logger.info("CPCB AQI poll cycle starting...")
        start = time.monotonic()

        from schedulers.owm_poller import OWM_CITIES

        for city_key in settings.covered_cities:
            try:
                city_config = OWM_CITIES.get(city_key, {})
                lat = city_config.get("lat", 0.0)
                lng = city_config.get("lon", 0.0)
                await self._poll_city_aqi(city_key, lat, lng)
            except Exception as e:
                logger.error(f"CPCB poll failed for {city_key}", exc_info=e)

        elapsed = time.monotonic() - start
        logger.info(f"CPCB AQI poll cycle complete | elapsed_seconds={round(elapsed, 2)}")

    async def _poll_city_aqi(self, city_name: str, lat: float, lng: float) -> dict:
        import os
        from datetime import datetime, timezone

        waqi_key = os.environ.get("WAQI_API_KEY", "").strip()
        if not waqi_key:
            logger.warning(
                f"WAQI_API_KEY not set — skipping live AQI poll for {city_name}. "
                f"Set WAQI_API_KEY in .env to enable real AQI data. "
                f"Demo triggers via god_mode_demo.py --scenario clean are unaffected."
            )
            return {}

        city_key = city_name

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(
                    f"https://api.waqi.info/feed/geo:{lat};{lng}/?token={waqi_key}"
                )
                resp.raise_for_status()
                data = resp.json()
                # WAQI returns {"status":"error","data":"Unknown station"} on bad geo coords
                # and {"data":{"aqi":"-"}} when a station has no current reading.
                if data.get("status") != "ok" or not isinstance(data.get("data"), dict):
                    logger.warning(
                        f"WAQI non-ok response for {city_name}: "
                        f"status={data.get('status')} data={data.get('data')}"
                    )
                    return {}
                aqi_raw = data["data"].get("aqi", -1)
                if aqi_raw == "-" or aqi_raw == -1:
                    logger.debug(f"WAQI no AQI reading available for {city_name} — skipping")
                    return {}
                aqi_value = int(aqi_raw)
                raw_payload = data
            except (httpx.HTTPError, ValueError, KeyError, TypeError) as e:
                logger.error(f"WAQI API error for {city_name}: {e}")
                return {}

        result = self.evaluator.evaluate_aqi(aqi_value)
        if not result["triggered"]:
            for tier in ["tier1", "tier2", "tier3"]:
                from shared.redis_client import cache_delete
                await cache_delete(self.AQI_BREACH_DURATION_KEY.format(city=city_key, tier=tier))
            return {}

        tier = result["tier"]

        breach_key = self.AQI_BREACH_DURATION_KEY.format(city=city_key, tier=tier)
        breach_start_str = await cache_get(breach_key)
        now = datetime.now(timezone.utc)

        if breach_start_str is None:
            await cache_set(breach_key, now.isoformat(), ttl=86400)
            logger.info(f"AQI breach started | city={city_key} | tier={tier} | aqi={aqi_value}")
            return {}

        breach_start = datetime.fromisoformat(breach_start_str)
        duration_hours = (now - breach_start).total_seconds() / 3600
        required_hours = self.REQUIRED_DURATION_HOURS.get(tier, 4)

        if duration_hours < required_hours:
            logger.debug(
                f"AQI breach not yet sustained | city={city_key} | tier={tier} | "
                f"duration_hours={round(duration_hours, 1)} | required_hours={required_hours}"
            )
            return {}

        dedup_key = f"aqi_trigger:{city_key}:{tier}"
        if await cache_get(dedup_key):
            return {}

        async with get_db_context() as db:
            zones = await self.zone_resolver.get_zones_for_city(db, city_key)
            for zone in zones:
                payload = {
                    "zone_id":         str(zone.id),
                    "zone_code":       zone.zone_code,
                    "city":            city_key,
                    "event_type":      "aqi",
                    "tier":            tier,
                    "metric_value":    float(aqi_value),
                    "metric_unit":     "aqi",
                    "payout_amount":   result["payout"],
                    "data_source":     "waqi",
                    "detected_at":     now.isoformat(),
                    "sustained_since": breach_start.isoformat(),
                    "duration_hours":  round(duration_hours, 1),
                    "raw_payload":     raw_payload,
                }
                await self.producer.publish(
                    topic=settings.topic_processed_trigger_events,
                    event_type=f"trigger.aqi.{tier}",
                    payload=payload,
                    source_service="trigger-engine",
                    key=zone.zone_code,
                )

        await cache_set(dedup_key, "1", ttl=21600)

        logger.info(
            f"AQI trigger emitted | city={city_key} | tier={tier} | aqi={aqi_value} | "
            f"sustained_hours={round(duration_hours, 1)} | zones_affected={len(zones)}"
        )

        from main import TRIGGER_EVENTS_TOTAL
        TRIGGER_EVENTS_TOTAL.labels(
            event_type="aqi", tier=tier, city=city_key
        ).inc()

        return {
            "city":      city_name,
            "aqi":       aqi_value,
            "source":    "waqi",
            "timestamp": datetime.now(timezone.utc),
        }
