"""
Policy Service — Premium Calculation Engine
Phase 2: Rule-based formula (deterministic, auditable).
Phase 3: Replace with XGBoost + LightGBM ensemble + SHAP waterfall.

Formula:
    Weekly Premium = Base Rate × Zone Risk × Seasonality × Disruption History × Coverage Tier

All factors are logged to premium_calculations table for actuarial audit.
"""
import math
import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.policy import PremiumCalculation
from models.schemas import PremiumBreakdown, PremiumCalculateResponse

logger = logging.getLogger(__name__)


# ── Constants ─────────────────────────────────────────────────────────────────

BASE_RATE: float = 25.0  # ₹25/week minimum

# City risk multipliers — based on NDMA/IMD 2024 historical disruption data
CITY_RISK_MULTIPLIERS: dict[str, float] = {
    "delhi_ncr":  2.6,   # 41 AQI>300 days/yr + 28 heatwave days
    "mumbai":     2.4,   # 23 heavy-rain days + 2 cyclone alerts
    "kolkata":    2.1,   # 18 cyclone-proximity days + 19 flooding events
    "hyderabad":  1.9,   # 31 heatwave days
    "pune":       1.7,   # 21 heavy-rain days
    "bengaluru":  1.4,   # 14 waterlogging events
}

# Zone-to-city mapping (loaded from zone_code)
ZONE_CITY_MAP: dict[str, str] = {
    "delhi_rohini":          "delhi_ncr",
    "delhi_dwarka":          "delhi_ncr",
    "delhi_lajpat_nagar":    "delhi_ncr",
    "delhi_karol_bagh":      "delhi_ncr",
    "delhi_saket":           "delhi_ncr",
    "gurgaon_cyber_city":    "delhi_ncr",
    "mumbai_kurla":          "mumbai",
    "mumbai_andheri_west":   "mumbai",
    "mumbai_bandra":         "mumbai",
    "mumbai_malad":          "mumbai",
    "mumbai_thane":          "mumbai",
    "bengaluru_koramangala": "bengaluru",
    "bengaluru_hsr_layout":  "bengaluru",
    "bengaluru_whitefield":  "bengaluru",
    "bengaluru_jp_nagar":    "bengaluru",
    "hyderabad_hitech_city": "hyderabad",
    "hyderabad_banjara_hills": "hyderabad",
    "pune_kothrud":          "pune",
    "pune_viman_nagar":      "pune",
    "kolkata_salt_lake":     "kolkata",
    "kolkata_park_street":   "kolkata",
}

# Seasonal factors — sin/cos encoded month → factor
# Peaks: Nov-Dec (Delhi AQI), Jul-Sep (Mumbai/Kolkata monsoon)
MONTHLY_SEASON_FACTORS: dict[int, float] = {
    1:  1.1,   # January  — Delhi fog
    2:  1.0,   # February — mild
    3:  1.0,   # March    — mild
    4:  1.2,   # April    — pre-summer heat building
    5:  1.3,   # May      — peak heatwave
    6:  1.4,   # June     — monsoon onset
    7:  1.6,   # July     — peak monsoon
    8:  1.6,   # August   — peak monsoon
    9:  1.5,   # September — late monsoon
    10: 1.2,   # October  — post-monsoon
    11: 1.7,   # November — Delhi AQI crisis peak + lingering monsoon
    12: 1.3,   # December — Delhi fog
}

# Coverage tier factors + max payout config
TIER_CONFIG: dict[str, dict] = {
    "basic": {
        "factor": 1.0,
        "max_payout_per_event": 200.0,   # ₹
        "max_payout_per_week":  400.0,
    },
    "standard": {
        "factor": 1.4,
        "max_payout_per_event": 400.0,
        "max_payout_per_week":  800.0,
    },
    "premium": {
        "factor": 1.9,
        "max_payout_per_event": 700.0,
        "max_payout_per_week": 1400.0,
    },
}

# Disruption history factor — based on zone risk (proxy until ML model trained)
# Phase 3: replaced by XGBoost feature 'historical_disruption_count_12m'
ZONE_HISTORY_FACTORS: dict[str, float] = {
    "delhi_ncr":  1.4,
    "mumbai":     1.3,
    "kolkata":    1.3,
    "hyderabad":  1.2,
    "pune":       1.1,
    "bengaluru":  1.0,
}


class PremiumCalculationEngine:
    """
    Rule-based premium calculator.
    Deterministic — same inputs always produce same output.
    Every calculation logged to premium_calculations table for actuarial audit.
    """

    def calculate(
        self,
        zone_code: str,
        coverage_tier: str,
        vehicle_type: str,
        declared_daily_trips: int,
        declared_daily_income: float,
        work_hours_profile: str,
        calculation_date: datetime | None = None,
    ) -> dict:
        """
        Core premium calculation.
        Returns a dict with all factors and the final premium.

        Factors:
        - Zone risk:    City-level historical disruption frequency
        - Seasonality:  Monthly sin/cos factor (monsoon/AQI peaks)
        - History:      Zone-level disruption history proxy
        - Tier:         Coverage tier multiplier
        - Vehicle adj:  Bicycle riders have higher AQI/heat exposure
        """
        if calculation_date is None:
            calculation_date = datetime.now(timezone.utc)

        month = calculation_date.month
        city = ZONE_CITY_MAP.get(zone_code, "bengaluru")

        # ── Factors ───────────────────────────────────────────────────────────
        zone_multiplier = CITY_RISK_MULTIPLIERS.get(city, 1.0)
        season_factor   = MONTHLY_SEASON_FACTORS.get(month, 1.0)
        history_factor  = ZONE_HISTORY_FACTORS.get(city, 1.0)
        tier_cfg        = TIER_CONFIG.get(coverage_tier, TIER_CONFIG["standard"])
        tier_factor     = tier_cfg["factor"]

        # Vehicle adjustment: bicycles are most exposed to AQI/heat
        vehicle_adjustments = {
            "bicycle":    1.0,    # Baseline — highest exposure
            "e_bike":     0.97,
            "motorcycle": 0.93,
            "scooter":    0.95,
        }
        vehicle_adj = vehicle_adjustments.get(vehicle_type, 1.0)

        # ── Final calculation ─────────────────────────────────────────────────
        raw_premium = (
            BASE_RATE
            * zone_multiplier
            * season_factor
            * history_factor
            * tier_factor
            * vehicle_adj
        )

        # Floor at base rate, round to nearest ₹1
        final_premium = max(BASE_RATE, round(raw_premium))

        # ── SHAP-style breakdown (Phase 2: rule-based attribution) ─────────────
        breakdown = {
            "base_rate":           BASE_RATE,
            "zone_multiplier":     zone_multiplier,
            "zone_contribution":   round(BASE_RATE * zone_multiplier - BASE_RATE, 2),
            "season_factor":       season_factor,
            "season_contribution": round(BASE_RATE * zone_multiplier * season_factor - BASE_RATE * zone_multiplier, 2),
            "history_factor":      history_factor,
            "history_contribution": round(BASE_RATE * zone_multiplier * season_factor * history_factor - BASE_RATE * zone_multiplier * season_factor, 2),
            "tier_factor":         tier_factor,
            "tier_contribution":   round(final_premium - BASE_RATE * zone_multiplier * season_factor * history_factor, 2),
            "final_premium":       float(final_premium),
            "calculation_method":  "rule_based",
            # Phase 3 additions:
            # "shap_values": {...},
            # "model_version": "xgboost_v1.2",
        }

        return {
            "city":                city,
            "zone_code":           zone_code,
            "coverage_tier":       coverage_tier,
            "final_premium":       float(final_premium),
            "max_payout_per_event": tier_cfg["max_payout_per_event"],
            "max_payout_per_week": tier_cfg["max_payout_per_week"],
            "breakdown":           breakdown,
        }

    async def calculate_and_log(
        self,
        db: AsyncSession,
        worker_id: UUID,
        zone_id: UUID,
        zone_code: str,
        coverage_tier: str,
        vehicle_type: str,
        declared_daily_trips: int,
        declared_daily_income: float,
        work_hours_profile: str,
    ) -> dict:
        """
        Calculate premium and persist the calculation to premium_calculations table.
        Returns the full result dict.
        """
        result = self.calculate(
            zone_code=zone_code,
            coverage_tier=coverage_tier,
            vehicle_type=vehicle_type,
            declared_daily_trips=declared_daily_trips,
            declared_daily_income=declared_daily_income,
            work_hours_profile=work_hours_profile,
        )
        bd = result["breakdown"]

        log_entry = PremiumCalculation(
            worker_id=worker_id,
            zone_id=zone_id,
            coverage_tier=coverage_tier,
            base_rate=bd["base_rate"],
            zone_multiplier=bd["zone_multiplier"],
            season_factor=bd["season_factor"],
            history_factor=bd["history_factor"],
            tier_factor=bd["tier_factor"],
            final_premium=result["final_premium"],
            calculation_method="rule_based",
            shap_values=None,   # Phase 3: SHAP waterfall JSON
        )
        db.add(log_entry)
        await db.flush()

        result["calculation_id"] = log_entry.id
        logger.info(
            "Premium calculated",
            extra={
                "worker_id": str(worker_id),
                "zone": zone_code,
                "tier": coverage_tier,
                "premium": result["final_premium"],
            },
        )
        return result
