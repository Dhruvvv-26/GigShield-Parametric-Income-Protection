"""
Trigger Engine — NDMA / IMD RSS Poller
Parses government alert feeds for flood, cyclone, and heatwave alerts.
RSS feeds are public, rate-unlimited, no API key required.

Sources:
  NDMA: https://ndma.gov.in/rss/
  IMD: https://mausam.imd.gov.in/responsive/rss.php
"""
import logging
import re
import time
from datetime import datetime, timezone
from xml.etree import ElementTree

import httpx

from shared.config import get_settings
from shared.database import get_db_context
from shared.messaging import GigShieldProducer
from shared.redis_client import cache_get, cache_set

from integrations.zone_resolver import ZoneResolver

logger = logging.getLogger(__name__)
settings = get_settings()

# Keywords that indicate a payout-triggering event in NDMA/IMD RSS items
ALERT_KEYWORDS: dict[str, dict] = {
    "flood": {
        "keywords": ["flood", "waterlog", "inundation", "flash flood"],
        "event_type": "flood_alert",
        "tier": "tier2",
        "payout": 380,
    },
    "cyclone": {
        "keywords": ["cyclone", "severe storm", "typhoon", "hurricane"],
        "event_type": "cyclone",
        "tier": "tier2",
        "payout": 450,
    },
    "red_alert_rain": {
        "keywords": ["red alert", "extremely heavy rain", "100mm"],
        "event_type": "heavy_rain",
        "tier": "tier3",
        "payout": 600,
    },
    "heatwave": {
        "keywords": ["severe heatwave", "heat wave", "46°c", "47°c", "48°c"],
        "event_type": "extreme_heat",
        "tier": "tier2",
        "payout": 250,
    },
    "grap4": {
        "keywords": ["grap stage iv", "grap 4", "grap-iv", "severe+ aqi"],
        "event_type": "aqi",
        "tier": "tier3",
        "payout": 500,
    },
}

# City name patterns to identify which city an alert applies to
CITY_NAME_PATTERNS: dict[str, list[str]] = {
    "delhi_ncr":  ["delhi", "ncr", "noida", "gurgaon", "gurugram", "faridabad", "rohini"],
    "mumbai":     ["mumbai", "bombay", "thane", "navi mumbai"],
    "bengaluru":  ["bengaluru", "bangalore"],
    "hyderabad":  ["hyderabad", "secunderabad"],
    "pune":       ["pune", "poona"],
    "kolkata":    ["kolkata", "calcutta"],
}

NDMA_RSS_URLS = [
    "https://ndma.gov.in/rss/",
    "https://mausam.imd.gov.in/responsive/rss.php",
]

# Mock RSS feed for demo mode
MOCK_RSS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>NDMA Alerts</title>
    <item>
      <title>Orange Alert: Heavy Rain Warning for Mumbai</title>
      <description>IMD has issued an Orange Alert for extremely heavy rainfall in Mumbai and surrounding areas. Residents advised to stay indoors.</description>
      <pubDate>Wed, 25 Mar 2026 10:00:00 +0530</pubDate>
      <guid>ndma-alert-001</guid>
    </item>
  </channel>
</rss>"""


class NDMAPoller:
    """
    Parses NDMA/IMD RSS feeds every 5 minutes.
    No rate limits — public government RSS.
    Uses keyword matching + city detection to identify payout-triggering alerts.

    Note: Curfew/bandh detection is mocked via /api/v1/trigger/test endpoint.
    Production approach: NLP classifier on NDTV/ToI RSS feeds (Phase 3).
    """

    def __init__(self, producer: GigShieldProducer):
        self.producer = producer
        self.zone_resolver = ZoneResolver()

    async def run(self) -> None:
        logger.debug("NDMA/IMD RSS poll cycle starting...")
        start = time.monotonic()

        for rss_url in NDMA_RSS_URLS:
            try:
                await self._poll_rss_feed(rss_url)
            except Exception as e:
                logger.warning(f"RSS poll failed for {rss_url}: {e}")

        elapsed = time.monotonic() - start
        logger.debug("NDMA RSS poll cycle complete", elapsed_seconds=round(elapsed, 2))

    async def _poll_rss_feed(self, url: str) -> None:
        """Fetch and parse one RSS feed."""
        if settings.owm_api_key == "demo_key_replace_me":
            xml_content = MOCK_RSS_XML
        else:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url, follow_redirects=True)
                resp.raise_for_status()
                xml_content = resp.text

        await self._parse_and_process(xml_content, source=url)

    async def _parse_and_process(self, xml_content: str, source: str) -> None:
        """Parse RSS XML and process each alert item."""
        try:
            root = ElementTree.fromstring(xml_content)
        except ElementTree.ParseError as e:
            logger.error(f"RSS XML parse error: {e}")
            return

        items = root.findall(".//item")
        for item in items:
            title = (item.findtext("title") or "").lower()
            description = (item.findtext("description") or "").lower()
            guid = item.findtext("guid") or f"rss-{hash(title)}"
            combined_text = f"{title} {description}"

            await self._classify_alert(combined_text, guid, source)

    async def _classify_alert(
        self,
        text: str,
        guid: str,
        source: str,
    ) -> None:
        """
        Classify an RSS alert item.
        Checks keyword match → city identification → emit trigger.
        """
        for alert_type, config in ALERT_KEYWORDS.items():
            if not any(kw in text for kw in config["keywords"]):
                continue

            # Identify which cities are affected
            affected_cities = [
                city
                for city, patterns in CITY_NAME_PATTERNS.items()
                if any(p in text for p in patterns)
            ]

            if not affected_cities:
                # If no specific city found, could be national alert — skip
                continue

            for city_key in affected_cities:
                dedup_key = f"rss_trigger:{guid}:{city_key}:{alert_type}"
                if await cache_get(dedup_key):
                    continue  # Already processed this alert

                await cache_set(dedup_key, "1", ttl=86400)  # 24 hour dedup

                async with get_db_context() as db:
                    zones = await self.zone_resolver.get_zones_for_city(db, city_key)
                    for zone in zones:
                        payload = {
                            "zone_id":       str(zone.id),
                            "zone_code":     zone.zone_code,
                            "city":          city_key,
                            "event_type":    config["event_type"],
                            "tier":          config["tier"],
                            "metric_value":  0.0,    # RSS alerts don't have numeric values
                            "metric_unit":   "alert",
                            "payout_amount": config["payout"],
                            "data_source":   "ndma_rss",
                            "detected_at":   datetime.now(timezone.utc).isoformat(),
                            "alert_guid":    guid,
                            "source_url":    source,
                        }
                        await self.producer.publish(
                            topic=settings.topic_processed_trigger_events,
                            event_type=f"trigger.{config['event_type']}.{config['tier']}",
                            payload=payload,
                            source_service="trigger-engine",
                            key=zone.zone_code,
                        )

                logger.info(
                    "NDMA alert trigger emitted",
                    alert_type=alert_type,
                    city=city_key,
                    guid=guid,
                )
