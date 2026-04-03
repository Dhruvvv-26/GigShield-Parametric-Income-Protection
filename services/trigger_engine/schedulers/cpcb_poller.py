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
from shared.messaging import GigShieldProducer
from shared.redis_client import cache_get, cache_set

from integrations.threshold_evaluator import ThresholdEvaluator
from integrations.zone_resolver import ZoneResolver

logger = logging.getLogger(__name__)
settings = get_settings()

# CPCB monitoring stations mapped to our cities
# In production: query all stations and group by city polygon
CPCB_STATION_CITY_MAP: dict[str, str] = {
    "DTH":    "delhi_ncr",     # Delhi - central
    "MUM":    "mumbai",
    "BLR":    "bengaluru",
    "HYD":    "hyderabad",
    "PUN":    "pune",
    "KOL":    "kolkata",
}

# Mock AQI values for demo (realistic for each city's risk profile)
MOCK_AQI_VALUES: dict[str, int] = {
    "delhi_ncr":  342,   # Tier 1 breach — AQI > 300
    "mumbai":     178,   # Clean
    "bengaluru":  95,    # Clean
    "hyderabad":  210,   # Elevated but below threshold
    "pune":       145,   # Clean
    "kolkata":    280,   # Near threshold
}


class CPCBPoller:
    """
    Polls WAQI AQI endpoint every 60 minutes.
    Government open-data portal — no rate limits, no API key required for basic access.

    AQI thresholds (PM2.5 standard):
      Tier 1: AQI > 300, sustained 4+ hours → ₹150 payout
      Tier 2: AQI > 400, sustained 3+ hours → ₹300 payout
      Tier 3: AQI > 500 OR GRAP Stage IV    → ₹500 payout
    """

    AQI_BREACH_DURATION_KEY = "aqi_breach_start:{city}:{tier}"
    # Tier 1 requires 4 hours sustained, Tier 2 requires 3 hours
    REQUIRED_DURATION_HOURS = {
        "tier1": 4,
        "tier2": 3,
        "tier3": 1,   # Tier 3 (AQI>500) — immediate trigger
    }

    def __init__(self, producer: GigShieldProducer):
        self.producer = producer
        self.evaluator = ThresholdEvaluator()
        self.zone_resolver = ZoneResolver()

    async def run(self) -> None:
        logger.info("CPCB AQI poll cycle starting...")
        start = time.monotonic()
        
        # Import OWM_CITIES to safely extract latitude and longitude for each covered city
        from schedulers.owm_poller import OWM_CITIES

        for city_key in settings.covered_cities:
            try:
                city_config = OWM_CITIES.get(city_key, {})
                lat = city_config.get("lat", 0.0)
                lng = city_config.get("lon", 0.0)
                # Pass city_key into city_name to maintain downstream compatibility
                await self._poll_city_aqi(city_key, lat, lng)
            except Exception as e:
                logger.error(f"CPCB poll failed for {city_key}", exc_info=e)

        elapsed = time.monotonic() - start
        logger.info(f"CPCB AQI poll cycle complete | elapsed_seconds={round(elapsed, 2)}")

    async def _poll_city_aqi(self, city_name: str, lat: float, lng: float) -> dict:
        import os
        from datetime import datetime, timezone
        
        city_key = city_name # Map for downstream identical code logic

        # Fetch AQI
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(
                    f"https://api.waqi.info/feed/geo:{lat};{lng}/?token={os.environ.get('WAQI_API_KEY', '')}"
                )
                resp.raise_for_status()
                data = resp.json()
                aqi_value = int(data["data"]["aqi"])
                raw_payload = data
            except (httpx.HTTPError, ValueError, KeyError) as e:
                logger.error(f"WAQI API error for {city_name}: {e}")
                return {}

        # Evaluate threshold
        result = self.evaluator.evaluate_aqi(aqi_value)
        if not result["triggered"]:
            # Clear any active breach tracking if AQI is back to normal
            for tier in ["tier1", "tier2", "tier3"]:
                from shared.redis_client import cache_delete
                await cache_delete(self.AQI_BREACH_DURATION_KEY.format(city=city_key, tier=tier))
            return {}

        tier = result["tier"]

        # ── Sustained Duration Check ──────────────────────────────────────────
        # AQI triggers require sustained threshold breach (not just one reading)
        breach_key = self.AQI_BREACH_DURATION_KEY.format(city=city_key, tier=tier)
        breach_start_str = await cache_get(breach_key)

        now = datetime.now(timezone.utc)

        if breach_start_str is None:
            # First breach reading — record start time, wait for next poll
            await cache_set(breach_key, now.isoformat(), ttl=86400)
            logger.info(f"AQI breach started | city={city_key} | tier={tier} | aqi={aqi_value}")
            return {}

        # Calculate how long threshold has been breached
        breach_start = datetime.fromisoformat(breach_start_str)
        duration_hours = (now - breach_start).total_seconds() / 3600
        required_hours = self.REQUIRED_DURATION_HOURS.get(tier, 4)

        if duration_hours < required_hours:
            logger.debug(f"AQI breach not yet sustained | city={city_key} | tier={tier} | duration_hours={round(duration_hours, 1)} | required_hours={required_hours}")
            return {}

        # ── Sustained — emit trigger ──────────────────────────────────────────
        dedup_key = f"aqi_trigger:{city_key}:{tier}"
        if await cache_get(dedup_key):
            return {} # Already emitted for this breach window

        async with get_db_context() as db:
            zones = await self.zone_resolver.get_zones_for_city(db, city_key)
            for zone in zones:
                payload = {
                    "zone_id":        str(zone.id),
                    "zone_code":      zone.zone_code,
                    "city":           city_key,
                    "event_type":     "aqi",
                    "tier":           tier,
                    "metric_value":   float(aqi_value),
                    "metric_unit":    "aqi",
                    "payout_amount":  result["payout"],
                    "data_source":    "waqi",
                    "detected_at":    now.isoformat(),
                    "sustained_since": breach_start.isoformat(),
                    "duration_hours": round(duration_hours, 1),
                    "raw_payload":    raw_payload,
                }
                await self.producer.publish(
                    topic=settings.topic_processed_trigger_events,
                    event_type=f"trigger.aqi.{tier}",
                    payload=payload,
                    source_service="trigger-engine",
                    key=zone.zone_code,
                )

        # Cache dedup for 6 hours — don't re-trigger same tier in same breach window
        await cache_set(dedup_key, "1", ttl=21600)

        logger.info(f"AQI trigger emitted | city={city_key} | tier={tier} | aqi={aqi_value} | sustained_hours={round(duration_hours, 1)} | zones_affected={len(zones)}")

        from main import TRIGGER_EVENTS_TOTAL
        TRIGGER_EVENTS_TOTAL.labels(
            event_type="aqi", tier=tier, city=city_key
        ).inc()
        
        return {
            "city": city_name,
            "aqi": aqi_value,
            "source": "waqi",
            "timestamp": datetime.now(timezone.utc)
        }
