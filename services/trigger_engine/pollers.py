"""
GigShield Trigger Engine — Unified API Pollers
================================================
Three async httpx pollers that fetch live environmental data
for parametric trigger evaluation.

Pollers:
  1. OWM (OpenWeatherMap)  — Rain, Temp, Wind for 6 cities
  2. WAQI (Air Quality)    — Live AQI from CPCB sensors via WAQI REST
  3. WeatherAPI.com        — Severe weather alerts (IMD Red Alert for Tier 3)

Config driven by env vars:
  OWM_API_KEY, WAQI_API_KEY, WEATHERAPI_KEY

Each poller is an async class with a `run()` method invoked by
APScheduler or an asyncio.sleep loop in main.py.
"""
import asyncio
import logging
import os
import time
from datetime import datetime, timezone

import httpx

logger = logging.getLogger("trigger_engine.pollers")

# ── City coordinates for all 6 Phase-1 cities ─────────────────────────────────
CITIES: dict[str, dict] = {
    "delhi_ncr":  {"lat": 28.6139, "lon": 77.2090, "name": "Delhi"},
    "mumbai":     {"lat": 19.0760, "lon": 72.8777, "name": "Mumbai"},
    "bengaluru":  {"lat": 12.9716, "lon": 77.5946, "name": "Bengaluru"},
    "hyderabad":  {"lat": 17.3850, "lon": 78.4867, "name": "Hyderabad"},
    "pune":       {"lat": 18.5204, "lon": 73.8567, "name": "Pune"},
    "kolkata":    {"lat": 22.5726, "lon": 88.3639, "name": "Kolkata"},
}


# ═══════════════════════════════════════════════════════════════════════════════
#  POLLER 1: OpenWeatherMap — Rain, Temperature, Wind
# ═══════════════════════════════════════════════════════════════════════════════

class OWMPoller:
    """
    Polls OWM /data/2.5/weather endpoint for each Phase-1 city.
    Rate budget: 15-min intervals × 6 cities = 96 calls/day (free limit: 1,000/day).

    Extracts:
      - rain_1h_mm, rain_3h_mm → extrapolated rain_24h_est
      - temp_celsius
      - wind_speed_kmh

    Returns list of city snapshots for downstream threshold evaluation.
    """

    BASE_URL = "https://api.openweathermap.org/data/2.5"

    def __init__(self):
        self.api_key = os.environ.get("OWM_API_KEY", "")

    async def run(self) -> list[dict]:
        """Poll all 6 cities and return weather snapshots."""
        logger.info("OWM poll cycle starting...")
        start = time.monotonic()
        results = []

        if not self.api_key:
            logger.warning("OWM_API_KEY not set — returning mock data")
            return self._mock_all()

        async with httpx.AsyncClient(timeout=10.0) as client:
            for city_key, cfg in CITIES.items():
                try:
                    snapshot = await self._poll_city(client, city_key, cfg)
                    results.append(snapshot)
                except Exception as e:
                    logger.error(f"OWM poll failed | city={city_key} | error={e}")

        elapsed = time.monotonic() - start
        logger.info(f"OWM poll cycle complete | cities={len(results)} | elapsed={round(elapsed, 2)}s")
        return results

    async def _poll_city(self, client: httpx.AsyncClient, city_key: str, cfg: dict) -> dict:
        """Fetch current weather for one city from OWM API."""
        resp = await client.get(
            f"{self.BASE_URL}/weather",
            params={
                "lat": cfg["lat"],
                "lon": cfg["lon"],
                "appid": self.api_key,
                "units": "metric",
            },
        )
        resp.raise_for_status()
        data = resp.json()

        # Extract metrics
        temp_celsius = data.get("main", {}).get("temp", 25.0)
        rain_1h_mm = data.get("rain", {}).get("1h", 0.0)
        rain_3h_mm = data.get("rain", {}).get("3h", 0.0)
        # Conservative 24h extrapolation
        rain_24h_est = max(rain_1h_mm * 24, rain_3h_mm * 8)
        wind_speed_ms = data.get("wind", {}).get("speed", 0.0)
        wind_kmh = wind_speed_ms * 3.6
        humidity = data.get("main", {}).get("humidity", 50)
        weather_main = data.get("weather", [{}])[0].get("main", "Clear")

        snapshot = {
            "city": city_key,
            "source": "openweathermap",
            "temp_celsius": round(temp_celsius, 1),
            "rain_1h_mm": round(rain_1h_mm, 1),
            "rain_3h_mm": round(rain_3h_mm, 1),
            "rain_24h_est_mm": round(rain_24h_est, 1),
            "wind_speed_kmh": round(wind_kmh, 1),
            "humidity_pct": humidity,
            "weather_main": weather_main,
            "polled_at": datetime.now(timezone.utc).isoformat(),
            "raw_response": data,
        }

        logger.debug(
            f"OWM data | city={city_key} | temp={temp_celsius}°C "
            f"| rain_24h_est={rain_24h_est}mm | wind={wind_kmh}km/h"
        )
        return snapshot

    @staticmethod
    def _mock_all() -> list[dict]:
        """Return mock weather data for demo mode."""
        mock = {
            "delhi_ncr":  {"temp": 44.0, "rain_24h": 0.0, "wind_kmh": 28.8},
            "mumbai":     {"temp": 32.0, "rain_24h": 120.0, "wind_kmh": 43.2},
            "bengaluru":  {"temp": 28.0, "rain_24h": 48.0, "wind_kmh": 21.6},
            "hyderabad":  {"temp": 41.0, "rain_24h": 0.0, "wind_kmh": 32.4},
            "pune":       {"temp": 35.0, "rain_24h": 72.0, "wind_kmh": 25.2},
            "kolkata":    {"temp": 36.0, "rain_24h": 24.0, "wind_kmh": 36.0},
        }
        return [
            {
                "city": city, "source": "openweathermap_mock",
                "temp_celsius": v["temp"], "rain_24h_est_mm": v["rain_24h"],
                "wind_speed_kmh": v["wind_kmh"],
                "polled_at": datetime.now(timezone.utc).isoformat(),
            }
            for city, v in mock.items()
        ]


# ═══════════════════════════════════════════════════════════════════════════════
#  POLLER 2: WAQI (World Air Quality Index) — Live AQI from CPCB sensors
# ═══════════════════════════════════════════════════════════════════════════════

class WAQIPoller:
    """
    Polls WAQI REST API for live AQI at city centroid coordinates.
    Endpoint: https://api.waqi.info/feed/geo:{lat};{lng}/?token={token}

    WAQI aggregates data from India's CPCB monitoring network and provides
    a stable, documented REST endpoint — unlike the CPCB portal which has
    no official public API and requires manual scraping.

    Rate budget: 60-min intervals × 6 cities = 144 calls/day
    Free limit: 1,000 calls/day. Headroom: 7×.

    Returns list of AQI snapshots with dominant pollutant info.
    """

    BASE_URL = "https://api.waqi.info/feed/geo"

    def __init__(self):
        self.api_token = os.environ.get("WAQI_API_KEY", "")

    async def run(self) -> list[dict]:
        """Poll AQI for all 6 cities."""
        logger.info("WAQI AQI poll cycle starting...")
        start = time.monotonic()
        results = []

        if not self.api_token:
            logger.warning("WAQI_API_KEY not set — returning mock AQI data")
            return self._mock_all()

        async with httpx.AsyncClient(timeout=10.0) as client:
            for city_key, cfg in CITIES.items():
                try:
                    snapshot = await self._poll_city(client, city_key, cfg)
                    if snapshot:
                        results.append(snapshot)
                except Exception as e:
                    logger.error(f"WAQI poll failed | city={city_key} | error={e}")

        elapsed = time.monotonic() - start
        logger.info(f"WAQI poll cycle complete | cities={len(results)} | elapsed={round(elapsed, 2)}s")
        return results

    async def _poll_city(self, client: httpx.AsyncClient, city_key: str, cfg: dict) -> dict | None:
        """Fetch current AQI for one city from WAQI geo-query endpoint."""
        lat = cfg["lat"]
        lng = cfg["lon"]
        url = f"{self.BASE_URL}:{lat};{lng}/?token={self.api_token}"

        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()

        if data.get("status") != "ok":
            logger.warning(f"WAQI returned non-ok status for {city_key}: {data.get('status')}")
            return None

        aqi_data = data.get("data", {})
        aqi_value = int(aqi_data.get("aqi", 0))
        dominant_pol = aqi_data.get("dominentpol", "pm25")
        station_name = aqi_data.get("city", {}).get("name", "unknown")

        # Extract individual pollutant values (iaqi = individual AQI)
        iaqi = aqi_data.get("iaqi", {})
        pm25 = iaqi.get("pm25", {}).get("v")
        pm10 = iaqi.get("pm10", {}).get("v")
        no2 = iaqi.get("no2", {}).get("v")
        o3 = iaqi.get("o3", {}).get("v")

        snapshot = {
            "city": city_key,
            "source": "waqi",
            "aqi": aqi_value,
            "dominant_pollutant": dominant_pol,
            "station": station_name,
            "pm25": pm25,
            "pm10": pm10,
            "no2": no2,
            "o3": o3,
            "polled_at": datetime.now(timezone.utc).isoformat(),
            "raw_response": data,
        }

        logger.debug(
            f"WAQI data | city={city_key} | aqi={aqi_value} "
            f"| dominant={dominant_pol} | station={station_name}"
        )
        return snapshot

    @staticmethod
    def _mock_all() -> list[dict]:
        """Return mock AQI data matching realistic city profiles."""
        mock_aqi = {
            "delhi_ncr": 342, "mumbai": 178, "bengaluru": 95,
            "hyderabad": 210, "pune": 145, "kolkata": 280,
        }
        return [
            {
                "city": city, "source": "waqi_mock", "aqi": aqi,
                "dominant_pollutant": "pm25", "station": f"mock_{city}",
                "polled_at": datetime.now(timezone.utc).isoformat(),
            }
            for city, aqi in mock_aqi.items()
        ]


# ═══════════════════════════════════════════════════════════════════════════════
#  POLLER 3: WeatherAPI.com — Severe Weather Alerts (IMD Red Alerts → Tier 3)
# ═══════════════════════════════════════════════════════════════════════════════

class WeatherAPIAlertsPoller:
    """
    Polls WeatherAPI.com Forecast + Alerts endpoint for severe weather.
    Endpoint: https://api.weatherapi.com/v1/forecast.json?q={lat},{lng}&alerts=yes

    Purpose: Detect IMD Red Alert / extreme weather events that trigger Tier 3
    payouts (cyclone, flood alert, GRAP Stage IV, etc.)

    These events are NOT caught by OWM or WAQI alone because they require
    government meteorological advisory context.

    Rate budget: 30-min intervals × 6 cities = 288 calls/day
    Free limit: 1,000,000 calls/month (~33,000/day). Headroom: 100×.

    Alert severity mapping:
      - "Moderate" → Tier 1 (if not already covered by OWM thresholds)
      - "Severe"   → Tier 2
      - "Extreme"  → Tier 3 (IMD Red Alert equivalent)
    """

    BASE_URL = "https://api.weatherapi.com/v1/forecast.json"

    SEVERITY_TO_TIER = {
        "Moderate": "tier1",
        "Severe":   "tier2",
        "Extreme":  "tier3",
    }

    # Keywords in alert headlines/descriptions that indicate Tier 3 events
    TIER3_KEYWORDS = [
        "red alert", "very severe cyclonic", "extremely heavy rain",
        "grap stage iv", "grap stage 4", "flood warning",
        "hurricane", "super cyclone", "landslide warning",
    ]

    def __init__(self):
        self.api_key = os.environ.get("WEATHERAPI_KEY", "")

    async def run(self) -> list[dict]:
        """Poll severe weather alerts for all 6 cities."""
        logger.info("WeatherAPI alerts poll cycle starting...")
        start = time.monotonic()
        results = []

        if not self.api_key:
            logger.warning("WEATHERAPI_KEY not set — returning empty alerts")
            return []

        async with httpx.AsyncClient(timeout=10.0) as client:
            for city_key, cfg in CITIES.items():
                try:
                    alerts = await self._poll_city_alerts(client, city_key, cfg)
                    results.extend(alerts)
                except Exception as e:
                    logger.error(f"WeatherAPI alerts poll failed | city={city_key} | error={e}")

        elapsed = time.monotonic() - start
        logger.info(
            f"WeatherAPI alerts poll complete | alerts_found={len(results)} | elapsed={round(elapsed, 2)}s"
        )
        return results

    async def _poll_city_alerts(
        self, client: httpx.AsyncClient, city_key: str, cfg: dict
    ) -> list[dict]:
        """Fetch severe weather alerts for one city from WeatherAPI.com."""
        resp = await client.get(
            self.BASE_URL,
            params={
                "key": self.api_key,
                "q": f"{cfg['lat']},{cfg['lon']}",
                "days": 1,
                "alerts": "yes",
                "aqi": "no",
            },
        )
        resp.raise_for_status()
        data = resp.json()

        alerts_raw = data.get("alerts", {}).get("alert", [])
        if not alerts_raw:
            return []

        parsed = []
        for alert in alerts_raw:
            headline = alert.get("headline", "")
            desc = alert.get("desc", "")
            severity = alert.get("severity", "")
            event = alert.get("event", "")
            effective = alert.get("effective", "")
            expires = alert.get("expires", "")

            # Determine tier from severity + keyword analysis
            tier = self.SEVERITY_TO_TIER.get(severity, None)

            # Keyword override: if description contains Tier 3 keywords, upgrade
            desc_lower = (headline + " " + desc + " " + event).lower()
            for kw in self.TIER3_KEYWORDS:
                if kw in desc_lower:
                    tier = "tier3"
                    break

            if tier is None:
                # Not severe enough to trigger — skip
                continue

            # Determine event type from alert metadata
            event_type = self._classify_alert_event(desc_lower)

            parsed.append({
                "city": city_key,
                "source": "weatherapi_alerts",
                "headline": headline,
                "description": desc[:500],  # Truncate for storage
                "severity": severity,
                "tier": tier,
                "event_type": event_type,
                "event_name": event,
                "effective": effective,
                "expires": expires,
                "polled_at": datetime.now(timezone.utc).isoformat(),
            })

            logger.warning(
                f"SEVERE ALERT | city={city_key} | tier={tier} | severity={severity} "
                f"| event={event} | headline={headline[:80]}"
            )

        return parsed

    @staticmethod
    def _classify_alert_event(desc_lower: str) -> str:
        """Classify alert into GigShield event types."""
        if any(kw in desc_lower for kw in ["cyclone", "cyclonic", "hurricane", "typhoon"]):
            return "cyclone"
        elif any(kw in desc_lower for kw in ["flood", "flash flood", "deluge"]):
            return "flood_alert"
        elif any(kw in desc_lower for kw in ["heat wave", "heatwave", "extreme heat", "hot day"]):
            return "extreme_heat"
        elif any(kw in desc_lower for kw in ["heavy rain", "extremely heavy", "torrential"]):
            return "heavy_rain"
        elif any(kw in desc_lower for kw in ["air quality", "grap", "smog", "pollution"]):
            return "aqi"
        elif any(kw in desc_lower for kw in ["curfew", "lockdown", "section 144"]):
            return "curfew"
        else:
            return "severe_weather"


# ═══════════════════════════════════════════════════════════════════════════════
#  Unified Poller Runner (for asyncio.sleep-based scheduling)
# ═══════════════════════════════════════════════════════════════════════════════

async def run_all_pollers(
    on_weather: callable = None,
    on_aqi: callable = None,
    on_alert: callable = None,
    owm_interval_s: int = 900,    # 15 minutes
    aqi_interval_s: int = 3600,   # 60 minutes
    alert_interval_s: int = 1800, # 30 minutes
):
    """
    Run all three pollers in parallel with different intervals.
    Callbacks receive the list of snapshots/alerts for downstream processing.

    Usage:
        await run_all_pollers(
            on_weather=my_weather_handler,
            on_aqi=my_aqi_handler,
            on_alert=my_alert_handler,
        )
    """
    owm = OWMPoller()
    waqi = WAQIPoller()
    weather_alerts = WeatherAPIAlertsPoller()

    async def _owm_loop():
        while True:
            try:
                snapshots = await owm.run()
                if on_weather and snapshots:
                    await on_weather(snapshots)
            except Exception as e:
                logger.error(f"OWM poller loop error: {e}")
            await asyncio.sleep(owm_interval_s)

    async def _aqi_loop():
        while True:
            try:
                snapshots = await waqi.run()
                if on_aqi and snapshots:
                    await on_aqi(snapshots)
            except Exception as e:
                logger.error(f"WAQI poller loop error: {e}")
            await asyncio.sleep(aqi_interval_s)

    async def _alert_loop():
        while True:
            try:
                alerts = await weather_alerts.run()
                if on_alert and alerts:
                    await on_alert(alerts)
            except Exception as e:
                logger.error(f"WeatherAPI alerts loop error: {e}")
            await asyncio.sleep(alert_interval_s)

    logger.info(
        f"Starting unified pollers | OWM={owm_interval_s}s | WAQI={aqi_interval_s}s | Alerts={alert_interval_s}s"
    )

    await asyncio.gather(
        _owm_loop(),
        _aqi_loop(),
        _alert_loop(),
    )
