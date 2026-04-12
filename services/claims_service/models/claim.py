"""
Claims Service — ORM Models
Mirrors claims + trigger_events tables from 01_init.sql.
"""
import uuid
from datetime import datetime, timezone

from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean, Column, DateTime, Enum, ForeignKey,
    Numeric, String, Text,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from shared.database import Base


class Zone(Base):
    """Read-only Zone model for PostGIS zone lookups."""
    __tablename__ = "zones"
    __table_args__ = {"extend_existing": True}

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    zone_code       = Column(String(50), unique=True, nullable=False, index=True)
    zone_name       = Column(String(100), nullable=False)
    city            = Column(String(50), nullable=False, index=True)
    geohash         = Column(String(12), index=True)
    boundary        = Column(Geometry("POLYGON", srid=4326), nullable=False)
    risk_multiplier = Column(Numeric(4, 2), nullable=False, default=1.0)
    is_active       = Column(Boolean, nullable=False, default=True)
    created_at      = Column(DateTime(timezone=True), nullable=False,
                             default=lambda: datetime.now(timezone.utc))


class TriggerEvent(Base):
    """Trigger Events table — referenced by Claims as FK."""
    __tablename__ = "trigger_events"
    __table_args__ = {"extend_existing": True}

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    zone_id         = Column(UUID(as_uuid=True), ForeignKey("zones.id"), nullable=False)
    event_type      = Column(Enum("aqi", "heavy_rain", "extreme_heat", "cyclone",
                                  "curfew", "flood_alert", name="trigger_event_type",
                                  create_type=False), nullable=False)
    tier            = Column(Enum("tier1", "tier2", "tier3", name="trigger_tier",
                                  create_type=False), nullable=False)
    metric_value    = Column(Numeric(10, 2), nullable=False)
    metric_unit     = Column(String(20), nullable=False)
    data_source     = Column(String(50), nullable=False)
    raw_payload     = Column(JSONB)
    is_sustained    = Column(Boolean, nullable=False, default=False)
    detected_at     = Column(DateTime(timezone=True), nullable=False,
                             default=lambda: datetime.now(timezone.utc))
    sustained_since = Column(DateTime(timezone=True))
    resolved_at     = Column(DateTime(timezone=True))

    claims = relationship("Claim", back_populates="trigger_event")


class Policy(Base):
    """Read-only Policy model for zone lookups."""
    __tablename__ = "policies"
    __table_args__ = {"extend_existing": True}

    id                   = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    worker_id            = Column(UUID(as_uuid=True), ForeignKey("workers.id"), nullable=False)
    zone_id              = Column(UUID(as_uuid=True), ForeignKey("zones.id"), nullable=False)
    coverage_tier        = Column(Enum("basic", "standard", "premium", name="coverage_tier",
                                       create_type=False), nullable=False, default="standard")
    status               = Column(Enum("active", "expired", "cancelled", "pending_payment",
                                       name="policy_status", create_type=False),
                                  nullable=False, default="pending_payment")
    weekly_premium       = Column(Numeric(8, 2), nullable=False)
    max_payout_per_event = Column(Numeric(8, 2), nullable=False)
    max_payout_per_week  = Column(Numeric(8, 2), nullable=False)
    coverage_start       = Column(DateTime(timezone=True))
    coverage_end         = Column(DateTime(timezone=True))
    razorpay_payment_id  = Column(String(100))
    created_at           = Column(DateTime(timezone=True), nullable=False,
                                  default=lambda: datetime.now(timezone.utc))
    updated_at           = Column(DateTime(timezone=True), nullable=False,
                                  default=lambda: datetime.now(timezone.utc))


class Worker(Base):
    """Worker model with primary zone for home zone lock enforcement."""
    __tablename__ = "workers"
    __table_args__ = {"extend_existing": True}

    id                    = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    phone_hash            = Column(String(128), unique=True, nullable=False)
    phone_last4           = Column(String(4))
    platform              = Column(String(20), nullable=False)
    full_name             = Column(String(100), nullable=False)
    vehicle_type          = Column(String(20), nullable=False)
    upi_id                = Column(Text)
    work_location         = Column(Geometry("POINT", srid=4326))
    zone_id               = Column(UUID(as_uuid=True), ForeignKey("zones.id"))
    # Phase 3.5: Primary zone for home zone lock — riders can only claim
    # payouts for weather events in their registered zone
    primary_zone_id       = Column(UUID(as_uuid=True), ForeignKey("zones.id"), nullable=True)
    is_active             = Column(Boolean, nullable=False, default=True)
    created_at            = Column(DateTime(timezone=True), nullable=False,
                                   default=lambda: datetime.now(timezone.utc))


class Claim(Base):
    """Full Claims model — the core of this service."""
    __tablename__ = "claims"
    __table_args__ = {"extend_existing": True}

    id                  = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    policy_id           = Column(UUID(as_uuid=True), ForeignKey("policies.id"), nullable=False)
    worker_id           = Column(UUID(as_uuid=True), ForeignKey("workers.id"), nullable=False)
    trigger_event_id    = Column(UUID(as_uuid=True), ForeignKey("trigger_events.id"), nullable=False)
    status              = Column(Enum("pending", "auto_approved", "soft_hold", "blocked",
                                      "completed", "rejected", name="claim_status",
                                      create_type=False),
                                 nullable=False, default="pending")
    payout_amount       = Column(Numeric(8, 2), nullable=False)
    fraud_score         = Column(Numeric(5, 4))
    fraud_flags         = Column(JSONB, default=[])
    # Per-layer fraud score breakdown (Phase 3)
    gps_score           = Column(Numeric(5, 4))
    sensor_score        = Column(Numeric(5, 4))
    network_score       = Column(Numeric(5, 4))
    behavioral_score    = Column(Numeric(5, 4))
    # Dual-selfie check
    selfie_url          = Column(Text)
    # Admin audit trail
    reviewer_note       = Column(Text)
    worker_gps_at_claim = Column(Geometry("POINT", srid=4326))
    sensor_data         = Column(JSONB)
    created_at          = Column(DateTime(timezone=True), nullable=False,
                                 default=lambda: datetime.now(timezone.utc))
    reviewed_at         = Column(DateTime(timezone=True))
    completed_at        = Column(DateTime(timezone=True))

    trigger_event = relationship("TriggerEvent", back_populates="claims")


class GpsPing(Base):
    """Read-only GPS ping model for fraud scoring."""
    __tablename__ = "gps_pings"
    __table_args__ = {"extend_existing": True}

    id          = Column(Numeric, primary_key=True, autoincrement=True)
    worker_id   = Column(UUID(as_uuid=True), ForeignKey("workers.id"), nullable=False)
    location    = Column(Geometry("POINT", srid=4326), nullable=False)
    accuracy_m  = Column(Numeric(8, 2))
    speed_kmh   = Column(Numeric(6, 2))
    altitude_m  = Column(Numeric(8, 2))
    recorded_at = Column(DateTime(timezone=True), nullable=False,
                         default=lambda: datetime.now(timezone.utc))
