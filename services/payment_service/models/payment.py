"""
Payment Service — ORM Models
Mirrors payments + payment_audit_log tables from 01_init.sql.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, DateTime, Enum, ForeignKey,
    Numeric, SmallInteger, String, Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from shared.database import Base


class Payment(Base):
    """Payment record — one per approved claim."""
    __tablename__ = "payments"
    __table_args__ = {"extend_existing": True}

    id                  = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    claim_id            = Column(UUID(as_uuid=True), ForeignKey("claims.id"), nullable=False)
    worker_id           = Column(UUID(as_uuid=True), ForeignKey("workers.id"), nullable=False)
    amount              = Column(Numeric(8, 2), nullable=False)
    status              = Column(Enum("pending", "processing", "completed", "failed", "refunded",
                                      name="payout_status", create_type=False),
                                 nullable=False, default="pending")
    razorpay_payout_id  = Column(String(100))
    upi_id_masked       = Column(String(50))
    initiated_at        = Column(DateTime(timezone=True), nullable=False,
                                 default=lambda: datetime.now(timezone.utc))
    completed_at        = Column(DateTime(timezone=True))
    failed_at           = Column(DateTime(timezone=True))
    failure_reason      = Column(Text)
    retry_count         = Column(SmallInteger, nullable=False, default=0)
    # Drip-feed payout mode support
    payout_mode         = Column(String(20), nullable=False, default="lump_sum")
    installments_disbursed = Column(SmallInteger, nullable=False, default=0)
    drip_installments   = Column(SmallInteger, nullable=False, default=1)
    disbursed_at        = Column(DateTime(timezone=True))

    audit_logs = relationship("PaymentAuditLog", back_populates="payment")


class PaymentAuditLog(Base):
    """Append-only audit log for payment status transitions."""
    __tablename__ = "payment_audit_log"
    __table_args__ = {"extend_existing": True}

    id          = Column(Numeric, primary_key=True, autoincrement=True)
    payment_id  = Column(UUID(as_uuid=True), ForeignKey("payments.id"), nullable=False)
    old_status  = Column(Enum("pending", "processing", "completed", "failed", "refunded", name="payout_status", create_type=False))
    new_status  = Column(Enum("pending", "processing", "completed", "failed", "refunded", name="payout_status", create_type=False), nullable=False)
    changed_at  = Column(DateTime(timezone=True), nullable=False,
                         default=lambda: datetime.now(timezone.utc))
    changed_by  = Column(String(50), nullable=False)
    note        = Column(Text)

    payment = relationship("Payment", back_populates="audit_logs")


class Claim(Base):
    """Read-only Claim model for payment context."""
    __tablename__ = "claims"
    __table_args__ = {"extend_existing": True}

    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    policy_id        = Column(UUID(as_uuid=True), nullable=False)
    worker_id        = Column(UUID(as_uuid=True), nullable=False)
    trigger_event_id = Column(UUID(as_uuid=True), nullable=False)
    status           = Column(Enum("pending", "auto_approved", "soft_hold", "blocked", "completed", "rejected",
                                   name="claim_status", create_type=False),
                              nullable=False, default="pending")
    payout_amount    = Column(Numeric(8, 2), nullable=False)
    fraud_score      = Column(Numeric(5, 4))
    created_at       = Column(DateTime(timezone=True), nullable=False,
                              default=lambda: datetime.now(timezone.utc))
    completed_at     = Column(DateTime(timezone=True))


class Worker(Base):
    """Read-only Worker model for UPI and name lookups."""
    __tablename__ = "workers"
    __table_args__ = {"extend_existing": True}

    id        = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    full_name = Column(String(100), nullable=False)
    upi_id    = Column(Text)
    zone_id   = Column(UUID(as_uuid=True))
    platform  = Column(String(20), nullable=False)


class Policy(Base):
    """Read-only Policy model for premium totals."""
    __tablename__ = "policies"
    __table_args__ = {"extend_existing": True}

    id             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    worker_id      = Column(UUID(as_uuid=True), nullable=False)
    zone_id        = Column(UUID(as_uuid=True), nullable=False)
    status         = Column(Enum("active", "expired", "cancelled", "pending_payment",
                                 name="policy_status", create_type=False), nullable=False)
    weekly_premium = Column(Numeric(8, 2), nullable=False)
