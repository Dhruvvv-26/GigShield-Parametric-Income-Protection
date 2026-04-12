"""
Payment Service — Pydantic Schemas
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class PaymentResponse(BaseModel):
    payment_id: UUID
    claim_id: UUID
    worker_id: UUID
    amount: float
    status: str
    razorpay_payout_id: Optional[str] = None
    upi_id_masked: Optional[str] = None
    initiated_at: datetime
    completed_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    failure_reason: Optional[str] = None

    model_config = {"from_attributes": True}


class PaymentListResponse(BaseModel):
    payments: list[PaymentResponse]
    total: int
    worker_id: Optional[str] = None


class PaymentSummaryResponse(BaseModel):
    """Financial summary for admin dashboard — loss ratio is the key metric."""
    total_premiums_this_week: float
    total_payouts_this_week: float
    loss_ratio_percent: float
    active_policies: int
    claims_this_week: int
    payments_completed: int
    payments_pending: int
    payments_failed: int
    avg_payout_amount: float
    daily_payout_volume: float
    # BCR = Burning Cost Rate — standard actuarial metric for parametric insurance solvency
    burning_cost_rate: float = Field(0.0, description="(total_payouts / total_exposure_premium) × 100 over trailing 30 days")
    bcr_status: str = Field("SOLVENT", description="SOLVENT (<70) | WATCH (70-85) | CRITICAL (>85)")
    trailing_30d_premiums: float = Field(0.0, description="Sum of premiums collected in last 30 calendar days")
    trailing_30d_payouts: float = Field(0.0, description="Sum of payouts initiated in last 30 calendar days")
    reserve_ratio: float = Field(0.0, description="(total_premiums - total_payouts) / total_premiums × 100")


class RazorpayWebhookPayload(BaseModel):
    """Razorpay webhook event payload."""
    event: str = Field(..., description="Event type: payout.processed, payout.failed")
    payload: dict = Field(default_factory=dict)
    account_id: Optional[str] = None
    contains: Optional[list[str]] = None
