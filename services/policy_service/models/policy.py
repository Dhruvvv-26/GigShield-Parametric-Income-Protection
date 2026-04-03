"""
Policy Service — ORM Models
Mirrors policies + premium_calculations tables from 01_init.sql.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, DateTime, Enum, ForeignKey,
    Numeric, SmallInteger, String, Text,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from shared.database import Base


class Policy(Base):
    __tablename__ = "policies"

    id                   = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    worker_id            = Column(UUID(as_uuid=True), nullable=False, index=True)
    zone_id              = Column(UUID(as_uuid=True), nullable=False, index=True)
    coverage_tier        = Column(Enum("basic", "standard", "premium", name="coverage_tier"),
                                  nullable=False, default="standard")
    status               = Column(Enum("active", "expired", "cancelled", "pending_payment",
                                       name="policy_status"), nullable=False, default="pending_payment", index=True)
    weekly_premium       = Column(Numeric(8, 2), nullable=False)
    max_payout_per_event = Column(Numeric(8, 2), nullable=False)
    max_payout_per_week  = Column(Numeric(8, 2), nullable=False)
    coverage_start       = Column(DateTime(timezone=True))
    coverage_end         = Column(DateTime(timezone=True))
    razorpay_payment_id  = Column(String(100))
    created_at           = Column(DateTime(timezone=True), nullable=False,
                                  default=lambda: datetime.now(timezone.utc))
    updated_at           = Column(DateTime(timezone=True), nullable=False,
                                  default=lambda: datetime.now(timezone.utc),
                                  onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    claims = relationship("Claim", back_populates="policy")


class PremiumCalculation(Base):
    __tablename__ = "premium_calculations"

    id                 = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    worker_id          = Column(UUID(as_uuid=True), nullable=False, index=True)
    zone_id            = Column(UUID(as_uuid=True), nullable=False)
    coverage_tier      = Column(Enum("basic", "standard", "premium", name="coverage_tier"), nullable=False)
    base_rate          = Column(Numeric(8, 2), nullable=False)
    zone_multiplier    = Column(Numeric(5, 3), nullable=False)
    season_factor      = Column(Numeric(5, 3), nullable=False)
    history_factor     = Column(Numeric(5, 3), nullable=False)
    tier_factor        = Column(Numeric(5, 3), nullable=False)
    final_premium      = Column(Numeric(8, 2), nullable=False)
    calculation_method = Column(String(20), nullable=False, default="rule_based")
    shap_values        = Column(JSONB)
    calculated_at      = Column(DateTime(timezone=True), nullable=False,
                                default=lambda: datetime.now(timezone.utc))


class Claim(Base):
    """Minimal Claim model for foreign key resolution — full model lives in claims_service."""
    __tablename__ = "claims"

    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    policy_id        = Column(UUID(as_uuid=True), ForeignKey("policies.id"), nullable=False, index=True)
    worker_id        = Column(UUID(as_uuid=True), nullable=False)
    trigger_event_id = Column(UUID(as_uuid=True), nullable=False)
    status           = Column(String(20), nullable=False, default="pending")
    payout_amount    = Column(Numeric(8, 2), nullable=False)
    created_at       = Column(DateTime(timezone=True), nullable=False,
                              default=lambda: datetime.now(timezone.utc))

    policy = relationship("Policy", back_populates="claims")
