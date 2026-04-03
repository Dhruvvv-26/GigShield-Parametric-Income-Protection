"""
Disruption Prediction Endpoint — GET /api/v1/predict/disruption
Returns LSTM-powered disruption probability for a given zone.
"""
import math
import logging
from datetime import datetime, timezone, timedelta

import numpy as np
from fastapi import APIRouter, Query

logger = logging.getLogger("ml_service")
router = APIRouter()

# Zone-to-city mapping (matches PostGIS zone configuration)
ZONE_CITY_MAP = {
    "delhi_rohini": "delhi_ncr", "delhi_dwarka": "delhi_ncr", "delhi_saket": "delhi_ncr",
    "delhi_laxmi_nagar": "delhi_ncr",
    "mumbai_andheri": "mumbai", "mumbai_bandra": "mumbai", "mumbai_powai": "mumbai",
    "mumbai_dadar": "mumbai",
    "bengaluru_koramangala": "bengaluru", "bengaluru_whitefield": "bengaluru",
    "bengaluru_indiranagar": "bengaluru",
    "hyderabad_gachibowli": "hyderabad", "hyderabad_hitech_city": "hyderabad",
    "hyderabad_secunderabad": "hyderabad",
    "pune_kothrud": "pune", "pune_hinjewadi": "pune", "pune_viman_nagar": "pune",
    "kolkata_salt_lake": "kolkata", "kolkata_newtown": "kolkata",
    "kolkata_park_street": "kolkata", "kolkata_howrah": "kolkata",
}


@router.get("/disruption")
async def predict_disruption(
    zone_code: str = Query(..., example="delhi_rohini"),
    days_ahead: int = Query(default=7, ge=1, le=30, example=7),
):
    from main import models

    lstm_model = models.get("lstm_model")
    lstm_scaler = models.get("lstm_scaler")
    lstm_meta = models.get("lstm_meta")

    city = ZONE_CITY_MAP.get(zone_code)
    if city is None:
        # Try extracting city from zone code prefix
        for prefix, city_name in [("delhi", "delhi_ncr"), ("mumbai", "mumbai"),
                                   ("bengaluru", "bengaluru"), ("hyderabad", "hyderabad"),
                                   ("pune", "pune"), ("kolkata", "kolkata")]:
            if zone_code.startswith(prefix):
                city = city_name
                break
        if city is None:
            city = "delhi_ncr"  # default

    if lstm_model is None or lstm_scaler is None or lstm_meta is None:
        return _rule_based_prediction(zone_code, city, days_ahead)

    try:
        import torch

        # Generate a synthetic 15-day sequence for the current conditions
        now = datetime.now(timezone.utc)
        seq_len = lstm_meta["sequence_length"]
        n_features = lstm_meta["input_size"]

        sequence = _generate_recent_sequence(city, now, seq_len)

        # Scale and predict
        seq_flat = sequence.reshape(-1, n_features)
        seq_scaled = lstm_scaler.transform(seq_flat).reshape(1, seq_len, n_features)

        with torch.no_grad():
            prob = float(lstm_model(torch.FloatTensor(seq_scaled)).item())

        # Determine confidence
        if prob > 0.75 or prob < 0.25:
            confidence = "high"
        elif prob > 0.60 or prob < 0.40:
            confidence = "medium"
        else:
            confidence = "low"

        # Determine primary risk
        primary_risk = _get_primary_risk(city, now.month)

        return {
            "zone_code": zone_code,
            "city": city,
            "prediction_horizon_days": days_ahead,
            "disruption_probability": round(prob, 4),
            "confidence": confidence,
            "primary_risk": primary_risk,
            "model_version": "lstm_v1",
        }

    except Exception as e:
        logger.error(f"LSTM prediction failed: {e}")
        return _rule_based_prediction(zone_code, city, days_ahead)


def _generate_recent_sequence(city: str, now: datetime, seq_len: int = 15) -> np.ndarray:
    """
    Generate a synthetic 15-day sequence representing recent conditions.
    In production, this would come from the last 15 days of actual API data.
    """
    from ml.train_lstm_model import CITY_PARAMS, generate_daily_data

    # Generate city data and take the last seq_len days matching current month
    try:
        city_df = generate_daily_data(city, n_days=365)
        month_data = city_df[city_df["month"] == now.month]
        if len(month_data) >= seq_len:
            sample = month_data.tail(seq_len)
        else:
            sample = city_df.tail(seq_len)
    except Exception:
        # Fallback: generate simple synthetic sequence
        features = []
        for i in range(seq_len):
            day = now - timedelta(days=seq_len - i)
            dow = day.weekday()
            month = day.month

            features.append([
                150.0,   # AQI
                30.0,    # temp
                5.0,     # rain
                12.0,    # wind
                0,       # trigger
                math.sin(2 * math.pi * dow / 7),
                math.cos(2 * math.pi * dow / 7),
                math.sin(2 * math.pi * month / 12),
                math.cos(2 * math.pi * month / 12),
            ])
        return np.array(features, dtype=np.float32)

    feature_cols = ["max_aqi", "max_temp_celsius", "rainfall_mm", "wind_speed_kmh",
                    "trigger_fired", "day_of_week_sin", "day_of_week_cos",
                    "month_sin", "month_cos"]
    return sample[feature_cols].values.astype(np.float32)


def _get_primary_risk(city: str, month: int) -> str:
    """Determine primary risk factor based on city and season."""
    if city == "delhi_ncr" and month in [10, 11, 12, 1]:
        return "AQI"
    elif city in ["mumbai", "kolkata", "pune", "bengaluru"] and month in [6, 7, 8, 9]:
        return "heavy_rain"
    elif city in ["delhi_ncr", "hyderabad"] and month in [4, 5, 6]:
        return "extreme_heat"
    elif city in ["mumbai", "kolkata"] and month in [5, 10, 11]:
        return "cyclone"
    else:
        return "mixed"


def _rule_based_prediction(zone_code: str, city: str, days_ahead: int) -> dict:
    """Fallback when LSTM model isn't loaded."""
    now = datetime.now(timezone.utc)
    month = now.month

    # Simple seasonal probability
    CITY_SEASON_RISK = {
        ("delhi_ncr", "winter"): 0.75,
        ("delhi_ncr", "summer"): 0.55,
        ("mumbai", "monsoon"): 0.80,
        ("kolkata", "monsoon"): 0.70,
        ("bengaluru", "monsoon"): 0.50,
    }

    if month in [6, 7, 8, 9]:
        season = "monsoon"
    elif month in [3, 4, 5]:
        season = "summer"
    elif month in [10, 11]:
        season = "post_monsoon"
    else:
        season = "winter"

    prob = CITY_SEASON_RISK.get((city, season), 0.30)
    primary_risk = _get_primary_risk(city, month)

    return {
        "zone_code": zone_code,
        "city": city,
        "prediction_horizon_days": days_ahead,
        "disruption_probability": round(prob, 4),
        "confidence": "medium",
        "primary_risk": primary_risk,
        "model_version": "rule_based_fallback",
    }
