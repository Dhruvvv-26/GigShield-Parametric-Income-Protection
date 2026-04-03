"""
Policy Service — Pydantic v2 Schemas
"""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# ── Premium ───────────────────────────────────────────────────────────────────

class PremiumCalculateRequest(BaseModel):
    """
    POST /api/v1/premium/calculate
    All fields required for deterministic rule-based premium calculation.
    Phase 3: replaced by XGBoost model with SHAP output.
    """
    worker_id: UUID
    zone_code: str = Field(..., description="e.g. 'delhi_rohini'")
    coverage_tier: str = Field("standard", description="basic | standard | premium")
    vehicle_type: str = Field(..., description="bicycle | e_bike | motorcycle | scooter")
    declared_daily_trips: int = Field(..., ge=1, le=60)
    declared_daily_income: float = Field(..., ge=100)
    work_hours_profile: str = Field("full_day")


class PremiumBreakdown(BaseModel):
    """SHAP-style breakdown of premium components (rule-based in Phase 2)."""
    base_rate: float
    zone_multiplier: float
    zone_contribution: float      # base_rate × zone_multiplier − base_rate
    season_factor: float
    season_contribution: float
    history_factor: float
    history_contribution: float
    tier_factor: float
    tier_contribution: float
    final_premium: float
    calculation_method: str       # 'rule_based' | 'xgboost'


class PremiumCalculateResponse(BaseModel):
    worker_id: UUID
    zone_code: str
    city: str
    coverage_tier: str
    weekly_premium: float         # ₹ per week
    max_payout_per_event: float   # ₹ — based on tier
    max_payout_per_week: float    # ₹ — 2× per-event cap
    breakdown: PremiumBreakdown
    calculation_id: UUID          # Logged to premium_calculations table


# ── Policy ────────────────────────────────────────────────────────────────────

class PolicyCreateRequest(BaseModel):
    """POST /api/v1/policies — create a new weekly policy for a worker."""
    worker_id: UUID
    coverage_tier: str = Field("standard", description="basic | standard | premium")
    razorpay_payment_id: str | None = Field(
        None, description="Provided after Razorpay payment is confirmed (Week 4)"
    )


class PolicyResponse(BaseModel):
    policy_id: UUID
    worker_id: UUID
    zone_code: str
    zone_name: str
    city: str
    coverage_tier: str
    status: str
    weekly_premium: float
    max_payout_per_event: float
    max_payout_per_week: float
    coverage_start: datetime | None
    coverage_end: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class PolicyActivateRequest(BaseModel):
    """PATCH /api/v1/policies/{policy_id}/activate — called after payment confirmation."""
    razorpay_payment_id: str


class PolicyListResponse(BaseModel):
    policies: list[PolicyResponse]
    total: int
    active_count: int
