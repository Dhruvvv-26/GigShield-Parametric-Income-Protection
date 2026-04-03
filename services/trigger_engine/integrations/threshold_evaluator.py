"""
Trigger Engine — Threshold Evaluator
Single source of truth for all KavachAI parametric trigger rules.
Used by all pollers (OWM, CPCB, NDMA).
"""
from shared.config import get_settings

settings = get_settings()


class ThresholdEvaluator:
    """
    Evaluates raw metric values against KavachAI parametric trigger thresholds.
    Returns whether a threshold is breached, the tier, and the payout amount.

    All thresholds are configured in shared/config.py for easy adjustment.
    """

    # ── Rain Triggers ─────────────────────────────────────────────────────────

    def evaluate_rain(self, rainfall_mm_24h: float) -> dict:
        """
        Heavy Rainfall trigger evaluation.
        Source: OpenWeatherMap (rain.3h × 8 proxy for 24h)

        Tier 1: > 35mm/24hr, 2+ hrs sustained  → ₹200
        Tier 2: > 65mm/24hr OR NDMA waterlogging → ₹380
        Tier 3: > 100mm/24hr OR IMD Red Alert   → ₹600
        """
        if rainfall_mm_24h >= settings.rain_tier3_threshold_mm:
            return {"triggered": True, "tier": "tier3", "payout": settings.rain_tier3_payout}
        elif rainfall_mm_24h >= settings.rain_tier2_threshold_mm:
            return {"triggered": True, "tier": "tier2", "payout": settings.rain_tier2_payout}
        elif rainfall_mm_24h >= settings.rain_tier1_threshold_mm:
            return {"triggered": True, "tier": "tier1", "payout": settings.rain_tier1_payout}
        return {"triggered": False, "tier": None, "payout": 0}

    # ── AQI Triggers ──────────────────────────────────────────────────────────

    def evaluate_aqi(self, aqi_value: int) -> dict:
        """
        Hazardous AQI trigger evaluation.
        Source: CPCB government API (PM2.5 standard)

        Tier 1: AQI > 300, 4+ hrs sustained    → ₹150
        Tier 2: AQI > 400, 3+ hrs sustained    → ₹300
        Tier 3: AQI > 500 OR GRAP Stage IV     → ₹500
        """
        if aqi_value >= settings.aqi_tier3_threshold:
            return {"triggered": True, "tier": "tier3", "payout": settings.aqi_tier3_payout}
        elif aqi_value >= settings.aqi_tier2_threshold:
            return {"triggered": True, "tier": "tier2", "payout": settings.aqi_tier2_payout}
        elif aqi_value >= settings.aqi_tier1_threshold:
            return {"triggered": True, "tier": "tier1", "payout": settings.aqi_tier1_payout}
        return {"triggered": False, "tier": None, "payout": 0}

    # ── Heat Triggers ─────────────────────────────────────────────────────────

    def evaluate_heat(self, temp_celsius: float) -> dict:
        """
        Extreme Heatwave trigger evaluation.
        Source: OpenWeatherMap current weather
        Only active 10AM–5PM (caller enforces time window)

        Tier 1: > 43°C, 3+ hrs   → ₹150
        Tier 2: > 45°C, 2+ hrs   → ₹250
        Tier 3: > 47°C OR IMD Severe Heatwave Alert → ₹450
        """
        if temp_celsius >= settings.heat_tier3_threshold_celsius:
            return {"triggered": True, "tier": "tier3", "payout": settings.heat_tier3_payout}
        elif temp_celsius >= settings.heat_tier2_threshold_celsius:
            return {"triggered": True, "tier": "tier2", "payout": settings.heat_tier2_payout}
        elif temp_celsius >= settings.heat_tier1_threshold_celsius:
            return {"triggered": True, "tier": "tier1", "payout": settings.heat_tier1_payout}
        return {"triggered": False, "tier": None, "payout": 0}

    # ── Wind / Cyclone Triggers ───────────────────────────────────────────────

    def evaluate_wind(self, wind_speed_kmh: float) -> dict:
        """
        Cyclone / Severe Storm trigger evaluation.
        Source: OpenWeatherMap wind.speed (converted from m/s to km/h)

        Tier 1: > 55 km/h + IMD Yellow Alert  → ₹250
        Tier 2: > 80 km/h + IMD Orange Alert  → ₹450
        Tier 3: > 110 km/h + IMD Red Alert    → ₹750
        """
        if wind_speed_kmh >= 110:
            return {"triggered": True, "tier": "tier3", "payout": 750}
        elif wind_speed_kmh >= 80:
            return {"triggered": True, "tier": "tier2", "payout": 450}
        elif wind_speed_kmh >= 55:
            return {"triggered": True, "tier": "tier1", "payout": 250}
        return {"triggered": False, "tier": None, "payout": 0}
