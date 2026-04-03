"""
Worker Service — Pydantic v2 Schemas
Request validation + response serialization for all endpoints.
"""
import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


# ── Enums (string literals for Pydantic) ─────────────────────────────────────

VehicleType   = str  # 'bicycle' | 'e_bike' | 'motorcycle' | 'scooter'
PlatformType  = str  # 'blinkit' | 'zepto' | 'dunzo' | 'swiggy_instamart'
WorkHours     = str  # 'full_day' | 'peak_only' | 'morning_only' | 'evening_only'
KycStatus     = str  # 'pending' | 'verified' | 'rejected'


# ── Registration ──────────────────────────────────────────────────────────────

class WorkerRegistrationRequest(BaseModel):
    """
    POST /api/v1/riders/register
    Onboards a new Q-Commerce rider.
    """
    phone_number: str = Field(
        ...,
        description="Indian mobile number (10 digits, starting with 6-9)",
        examples=["9876543210"],
    )
    full_name: str = Field(..., min_length=2, max_length=100)
    platform: PlatformType = Field(..., description="Delivery platform")
    platform_partner_id: str | None = Field(
        None, description="Blinkit fleet ID / Zepto driver ID"
    )
    vehicle_type: VehicleType
    work_hours_profile: WorkHours = "full_day"
    declared_daily_trips: int = Field(..., ge=1, le=60)
    declared_daily_income: float = Field(..., ge=100, le=5000, description="₹ per day")
    home_pincode: str | None = Field(None, pattern=r"^\d{6}$")
    work_latitude: float = Field(..., ge=8.0, le=37.0, description="India latitude range")
    work_longitude: float = Field(..., ge=68.0, le=97.0, description="India longitude range")
    device_fingerprint: str | None = Field(None, description="SHA-256 of device params")
    upi_id: str | None = Field(None, description="worker@upi format")

    @field_validator("phone_number")
    @classmethod
    def validate_indian_phone(cls, v: str) -> str:
        v = v.strip().replace(" ", "").replace("-", "")
        if v.startswith("+91"):
            v = v[3:]
        if v.startswith("91") and len(v) == 12:
            v = v[2:]
        if not re.match(r"^[6-9]\d{9}$", v):
            raise ValueError("Invalid Indian mobile number")
        return v

    @field_validator("platform")
    @classmethod
    def validate_platform(cls, v: str) -> str:
        allowed = {"blinkit", "zepto", "dunzo", "swiggy_instamart"}
        if v not in allowed:
            raise ValueError(f"Platform must be one of: {allowed}")
        return v

    @field_validator("vehicle_type")
    @classmethod
    def validate_vehicle(cls, v: str) -> str:
        allowed = {"bicycle", "e_bike", "motorcycle", "scooter"}
        if v not in allowed:
            raise ValueError(f"Vehicle type must be one of: {allowed}")
        return v

    @field_validator("upi_id")
    @classmethod
    def validate_upi(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not re.match(r"^[\w.\-]{3,}@[\w]{3,}$", v):
            raise ValueError("Invalid UPI ID format")
        return v


class WorkerRegistrationResponse(BaseModel):
    """Response for successful registration."""
    worker_id: UUID
    zone_code: str
    zone_name: str
    city: str
    message: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Worker Profile ────────────────────────────────────────────────────────────

class WorkerProfileResponse(BaseModel):
    worker_id: UUID
    full_name: str
    platform: str
    vehicle_type: str
    work_hours_profile: str
    declared_daily_trips: int
    declared_daily_income: float
    zone_code: str
    zone_name: str
    city: str
    kyc_status: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class WorkerUpdateRequest(BaseModel):
    """PATCH /api/v1/riders/{worker_id} — partial update."""
    declared_daily_trips: int | None = Field(None, ge=1, le=60)
    declared_daily_income: float | None = Field(None, ge=100, le=5000)
    work_hours_profile: WorkHours | None = None
    upi_id: str | None = None

    @field_validator("upi_id")
    @classmethod
    def validate_upi(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not re.match(r"^[\w.\-]{3,}@[\w]{3,}$", v):
            raise ValueError("Invalid UPI ID format")
        return v


# ── GPS Ping ──────────────────────────────────────────────────────────────────

class GpsPingRequest(BaseModel):
    """POST /api/v1/riders/{worker_id}/gps — ingest location ping."""
    latitude: float = Field(..., ge=8.0, le=37.0)
    longitude: float = Field(..., ge=68.0, le=97.0)
    accuracy_metres: float | None = Field(None, ge=0, le=1000)
    speed_kmh: float | None = Field(None, ge=0, le=200)
    altitude_metres: float | None = None


class GpsPingResponse(BaseModel):
    ping_recorded: bool
    zone_code: str | None
    in_active_disruption_zone: bool = False


# ── Zone ──────────────────────────────────────────────────────────────────────

class ZoneResponse(BaseModel):
    zone_id: UUID
    zone_code: str
    zone_name: str
    city: str
    risk_multiplier: float
    is_active: bool

    model_config = {"from_attributes": True}


class ZoneLookupRequest(BaseModel):
    """POST /api/v1/zones/lookup — find zone for a coordinate."""
    latitude: float = Field(..., ge=8.0, le=37.0)
    longitude: float = Field(..., ge=68.0, le=97.0)


class ZoneLookupResponse(BaseModel):
    found: bool
    zone: ZoneResponse | None = None
    message: str = ""
