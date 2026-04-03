"""
Worker Service — ORM Models
Mirrors the tables defined in migrations/01_init.sql.
"""
import uuid
from datetime import datetime, timezone

from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean, CheckConstraint, Column, DateTime, Enum,
    ForeignKey, Integer, Numeric, String, Text,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from shared.database import Base


class Zone(Base):
    __tablename__ = "zones"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    zone_code       = Column(String(50), unique=True, nullable=False, index=True)
    zone_name       = Column(String(100), nullable=False)
    city            = Column(String(50), nullable=False, index=True)
    geohash         = Column(String(12), index=True)
    boundary        = Column(Geometry("POLYGON", srid=4326), nullable=False)
    risk_multiplier = Column(Numeric(4, 2), nullable=False, default=1.0)
    is_active       = Column(Boolean, nullable=False, default=True)
    created_at      = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    workers  = relationship("Worker", back_populates="zone")


class Worker(Base):
    __tablename__ = "workers"

    id                    = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    phone_hash            = Column(String(128), unique=True, nullable=False, index=True)
    phone_last4           = Column(String(4))
    platform              = Column(Enum("blinkit", "zepto", "dunzo", "swiggy_instamart",
                                        name="platform_type"), nullable=False)
    platform_partner_id   = Column(String(100))
    full_name             = Column(String(100), nullable=False)
    vehicle_type          = Column(Enum("bicycle", "e_bike", "motorcycle", "scooter",
                                        name="vehicle_type"), nullable=False)
    work_hours_profile    = Column(Enum("full_day", "peak_only", "morning_only", "evening_only",
                                        name="work_hours_profile"), nullable=False, default="full_day")
    declared_daily_trips  = Column(Integer, nullable=False)
    declared_daily_income = Column(Numeric(8, 2), nullable=False)
    home_pincode          = Column(String(10))
    kyc_status            = Column(Enum("pending", "verified", "rejected",
                                        name="kyc_status"), nullable=False, default="pending")
    device_fingerprint    = Column(String(128))
    upi_id                = Column(Text)  # Fernet encrypted
    work_location         = Column(Geometry("POINT", srid=4326))
    zone_id               = Column(UUID(as_uuid=True), ForeignKey("zones.id"))
    primary_zone_id       = Column(UUID(as_uuid=True), ForeignKey("zones.id"))
    is_active             = Column(Boolean, nullable=False, default=True)
    created_at            = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at            = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        CheckConstraint(
            "declared_daily_trips BETWEEN 1 AND 60",
            name="chk_trips_range",
        ),
    )

    # Relationships
    zone     = relationship("Zone", back_populates="workers")


class GpsPing(Base):
    __tablename__ = "gps_pings"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    worker_id   = Column(UUID(as_uuid=True), ForeignKey("workers.id", ondelete="CASCADE"), nullable=False)
    location    = Column(Geometry("POINT", srid=4326), nullable=False)
    accuracy_m  = Column(Numeric(8, 2))
    speed_kmh   = Column(Numeric(6, 2))
    altitude_m  = Column(Numeric(8, 2))
    recorded_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
