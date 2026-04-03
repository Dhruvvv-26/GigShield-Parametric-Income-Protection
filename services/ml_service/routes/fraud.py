"""
Fraud Scoring Endpoint — POST /api/v1/fraud/score
Returns ML-powered fraud score using IsolationForest + GradientBoosting ensemble.
"""
import logging

import numpy as np
from fastapi import APIRouter
from pydantic import BaseModel, Field

logger = logging.getLogger("ml_service")
router = APIRouter()


class FraudRequest(BaseModel):
    gps_variance_sigma: float = Field(default=0.0, example=3.5)
    gps_accuracy_m: float = Field(default=10.0, example=12.0)
    gps_cold_start_ms: int = Field(default=30000, example=25000)
    accel_rms: float = Field(default=1.5, example=1.8)
    gyro_yaw_mismatch_deg: float = Field(default=5.0, example=8.0)
    mock_location_enabled: int = Field(default=0, ge=0, le=1, example=0)
    ip_gps_delta_km: float = Field(default=1.0, example=0.8)
    tower_handoffs_30min: int = Field(default=4, example=5)
    zone_resident_t_minus_30: int = Field(default=1, ge=0, le=1, example=1)
    claims_in_window_same_zone: int = Field(default=5, example=6)
    month: int = Field(default=6, ge=1, le=12, example=7)
    is_monsoon: int = Field(default=0, ge=0, le=1, example=1)


class FraudResponse(BaseModel):
    combined_score: float
    iso_forest_score: float
    gb_score: float
    decision: str
    model_version: str
    flags: list[str]


@router.post("/score", response_model=FraudResponse)
async def score_fraud(req: FraudRequest):
    from main import models

    iso_forest = models.get("iso_forest")
    gb_clf = models.get("gb_fraud")
    scaler = models.get("fraud_scaler")
    meta = models.get("fraud_meta")

    if iso_forest is None or gb_clf is None or scaler is None or meta is None:
        return _rule_based_fraud(req)

    feature_cols = meta["feature_columns"]
    feature_values = [getattr(req, col, 0) for col in feature_cols]
    X = np.array([feature_values], dtype=float)

    # Scale for Isolation Forest
    X_scaled = scaler.transform(X)

    # Isolation Forest: anomaly score (higher = more anomalous)
    iso_raw = float(-iso_forest.score_samples(X_scaled)[0])
    iso_min = meta.get("iso_score_min", 0)
    iso_max = meta.get("iso_score_max", 1)
    iso_score = (iso_raw - iso_min) / (iso_max - iso_min + 1e-8)
    iso_score = max(0.0, min(1.0, iso_score))

    # GradientBoosting: P(fraud)
    gb_score = float(gb_clf.predict_proba(X)[:, 1][0])

    # Combined: 40% IsoForest + 60% GB
    combined = round(0.40 * iso_score + 0.60 * gb_score, 4)

    # Decision routing
    if combined >= 0.85:
        decision = "blocked"
    elif combined >= 0.65:
        decision = "soft_hold"
    else:
        decision = "approved"

    # Generate flags
    flags = []
    if req.mock_location_enabled == 1:
        flags.append("MOCK_LOCATION_DETECTED")
    if req.gps_cold_start_ms < 500:
        flags.append(f"GPS_INSTANT_LOCK_{req.gps_cold_start_ms}ms")
    if req.gps_variance_sigma < 0.001:
        flags.append(f"GPS_ZERO_VARIANCE_{req.gps_variance_sigma:.6f}")
    if req.accel_rms < 0.1:
        flags.append(f"DEVICE_STATIONARY_ACCEL_{req.accel_rms:.3f}")
    if req.ip_gps_delta_km > 5.0:
        flags.append(f"IP_GPS_MISMATCH_{req.ip_gps_delta_km:.1f}km")
    if req.claims_in_window_same_zone > 50:
        flags.append(f"COORDINATED_BURST_{req.claims_in_window_same_zone}")
    if req.tower_handoffs_30min == 0:
        flags.append("ZERO_TOWER_HANDOFFS")

    return FraudResponse(
        combined_score=combined,
        iso_forest_score=round(iso_score, 4),
        gb_score=round(gb_score, 4),
        decision=decision,
        model_version="isoforest_gb_v1",
        flags=flags,
    )


def _rule_based_fraud(req: FraudRequest) -> FraudResponse:
    """Fallback rule-based scoring when ML models aren't loaded."""
    score = 0.0
    flags = []

    if req.mock_location_enabled == 1:
        score += 0.4
        flags.append("MOCK_LOCATION_DETECTED")
    if req.gps_variance_sigma < 0.001:
        score += 0.3
        flags.append("GPS_ZERO_VARIANCE")
    if req.gps_cold_start_ms < 500:
        score += 0.2
        flags.append("GPS_INSTANT_LOCK")
    if req.accel_rms < 0.1:
        score += 0.3
        flags.append("DEVICE_STATIONARY")
    if req.ip_gps_delta_km > 5.0:
        score += 0.2
        flags.append("IP_GPS_MISMATCH")

    score = min(1.0, score)

    if score >= 0.85:
        decision = "blocked"
    elif score >= 0.65:
        decision = "soft_hold"
    else:
        decision = "approved"

    return FraudResponse(
        combined_score=round(score, 4),
        iso_forest_score=0.0,
        gb_score=0.0,
        decision=decision,
        model_version="rule_based_fallback",
        flags=flags,
    )
