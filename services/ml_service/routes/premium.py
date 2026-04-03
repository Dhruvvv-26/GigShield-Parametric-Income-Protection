"""
Premium Pricing Endpoint — POST /api/v1/premium/calculate
Returns ML-powered premium quote with SHAP breakdown.
"""
import math
import logging

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger("ml_service")
router = APIRouter()


class PremiumRequest(BaseModel):
    city: str = Field(..., example="delhi_ncr")
    vehicle_type: str = Field(..., example="bicycle")
    coverage_tier: str = Field(..., example="standard")
    month: int = Field(ge=1, le=12, example=7)
    historical_aqi_events_12m: int = Field(ge=0, example=45)
    historical_rain_events_12m: int = Field(ge=0, example=28)
    disruption_history_90d: int = Field(ge=0, example=15)
    declared_daily_trips: int = Field(ge=10, le=50, example=30)
    avg_daily_earnings: float = Field(ge=200, example=1100.0)
    monthly_work_days: int = Field(ge=10, le=31, example=22)
    work_hours_profile: str = Field(default="full_day", example="full_day")
    zone_idx: int = Field(default=0, ge=0, le=20, example=5)


class PremiumResponse(BaseModel):
    weekly_premium: float
    model_version: str
    shap_breakdown: dict


def _month_to_season(month: int) -> str:
    if month in [3, 4, 5]:
        return "summer"
    elif month in [6, 7, 8, 9]:
        return "monsoon"
    elif month in [10, 11]:
        return "post_monsoon"
    else:
        return "winter"


@router.post("/calculate", response_model=PremiumResponse)
async def calculate_premium(req: PremiumRequest):
    from main import models

    xgb_model = models.get("premium_xgb")
    lgb_model = models.get("premium_lgb")
    meta = models.get("premium_meta")
    shap_explainer = models.get("shap_explainer")

    if xgb_model is None or lgb_model is None or meta is None:
        # Fallback to rule-based
        return _rule_based_premium(req)

    # Build feature row matching training pipeline
    month_sin = math.sin(2 * math.pi * req.month / 12)
    month_cos = math.cos(2 * math.pi * req.month / 12)
    season = _month_to_season(req.month)

    row = {
        "month_sin": month_sin,
        "month_cos": month_cos,
        "historical_aqi_events_12m": req.historical_aqi_events_12m,
        "historical_rain_events_12m": req.historical_rain_events_12m,
        "disruption_history_90d": req.disruption_history_90d,
        "declared_daily_trips": req.declared_daily_trips,
        "avg_daily_earnings": req.avg_daily_earnings,
        "monthly_work_days": req.monthly_work_days,
        "zone_idx": req.zone_idx,
    }

    # One-hot encode categoricals
    feature_columns = meta["feature_columns"]
    for col in feature_columns:
        if col not in row:
            row[col] = 0

    # Set one-hot flags
    row[f"city_{req.city}"] = 1
    row[f"vehicle_type_{req.vehicle_type}"] = 1
    row[f"coverage_tier_{req.coverage_tier}"] = 1
    row[f"work_hours_profile_{req.work_hours_profile}"] = 1
    row[f"season_{season}"] = 1

    X = pd.DataFrame([row])[feature_columns].fillna(0).astype(float)

    xgb_pred = float(xgb_model.predict(X)[0])
    lgb_pred = float(lgb_model.predict(X)[0])
    premium = round(0.60 * xgb_pred + 0.40 * lgb_pred, 2)

    # SHAP breakdown
    shap_breakdown = {"base_rate": 25.0}
    if shap_explainer is not None:
        try:
            shap_values = shap_explainer.shap_values(X)
            sv = shap_values[0]

            # Group SHAP into interpretable categories
            city_cols = [i for i, c in enumerate(feature_columns) if c.startswith("city_")]
            season_cols = [i for i, c in enumerate(feature_columns) if c.startswith("season_")]
            aqi_idx = feature_columns.index("historical_aqi_events_12m") if "historical_aqi_events_12m" in feature_columns else None
            rain_idx = feature_columns.index("historical_rain_events_12m") if "historical_rain_events_12m" in feature_columns else None
            tier_cols = [i for i, c in enumerate(feature_columns) if c.startswith("coverage_tier_")]

            shap_breakdown["city_aqi_risk"] = round(float(sum(sv[i] for i in city_cols)), 2)
            shap_breakdown["seasonality"] = round(float(sum(sv[i] for i in season_cols)), 2)
            if aqi_idx is not None:
                shap_breakdown["disruption_history_aqi"] = round(float(sv[aqi_idx]), 2)
            if rain_idx is not None:
                shap_breakdown["disruption_history_rain"] = round(float(sv[rain_idx]), 2)
            shap_breakdown["coverage_tier"] = round(float(sum(sv[i] for i in tier_cols)), 2)
        except Exception as e:
            logger.warning(f"SHAP computation failed: {e}")

    return PremiumResponse(
        weekly_premium=max(20, premium),
        model_version="xgb_lgb_v1",
        shap_breakdown=shap_breakdown,
    )


def _rule_based_premium(req: PremiumRequest) -> PremiumResponse:
    """Fallback when ML models aren't loaded."""
    CITY_RISK = {"delhi_ncr": 2.6, "mumbai": 2.4, "kolkata": 2.1, "hyderabad": 1.9, "pune": 1.7, "bengaluru": 1.4}
    VEHICLE_RISK = {"bicycle": 1.3, "ebike": 1.1, "motorcycle": 0.9}
    TIER_MULT = {"basic": 1.0, "standard": 1.4, "premium": 1.8}

    base = 25.0
    premium = base * CITY_RISK.get(req.city, 1.5) * VEHICLE_RISK.get(req.vehicle_type, 1.0) * TIER_MULT.get(req.coverage_tier, 1.0)
    premium = round(max(20, min(500, premium)), 2)

    return PremiumResponse(
        weekly_premium=premium,
        model_version="rule_based_fallback",
        shap_breakdown={"base_rate": base, "note": "ML models not loaded — using rule-based fallback"},
    )
