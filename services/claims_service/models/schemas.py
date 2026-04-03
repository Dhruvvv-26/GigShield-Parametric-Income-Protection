"""
Claims Service — Pydantic Schemas
Request/Response validation for all claims endpoints.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ── Request Schemas ──────────────────────────────────────────────────────────

class SensorDataPayload(BaseModel):
    """Sensor data submitted from the mobile app for fraud scoring."""
    gps_pings: list[dict] = Field(
        default_factory=list,
        description="List of GPS pings: [{lat, lng, accuracy_m, timestamp}]",
    )
    gps_cold_start_ms: Optional[int] = Field(
        None, description="Time taken to acquire first GPS lock in ms"
    )
    accelerometer_rms: float = Field(
        ..., description="Accelerometer RMS over 30-second window"
    )
    gyroscope_yaw_rate: float = Field(
        ..., description="Mean gyroscope yaw rate (rad/s)"
    )
    is_mock_location: Optional[bool] = Field(
        None, description="True if mock location detected on device"
    )
    is_developer_mode: Optional[bool] = Field(
        None, description="True if developer mode is enabled"
    )
    ip_address: Optional[str] = Field(
        None, description="Device IP for IP-GPS geo delta check"
    )
    ip_geo_lat: Optional[float] = Field(
        None, description="Latitude from IP geolocation lookup"
    )
    ip_geo_lng: Optional[float] = Field(
        None, description="Longitude from IP geolocation lookup"
    )
    photo_base64: Optional[str] = Field(
        None, max_length=2_097_152, description="Layer 5: Compressed base64 string of the biometric selfie (max ~2MB)"
    )
    active_zone_id: Optional[str] = Field(
        None, description="Layer 5: The ID of the zone the rider is currently claiming in"
    )
    camera_gps_lat: Optional[float] = Field(
        None, description="Layer 5: Hardware GPS latitude at moment of capture"
    )
    camera_gps_lng: Optional[float] = Field(
        None, description="Layer 5: Hardware GPS longitude at moment of capture"
    )
    capture_timestamp_ms: Optional[int] = Field(
        None, description="Layer 5: Unix timestamp in ms when selfie was captured"
    )


class ClaimAdminReviewRequest(BaseModel):
    """Admin override for claim status."""
    action: str = Field(
        ...,
        description="Action: 'approve', 'reject', 'release_hold'",
        pattern="^(approve|reject|release_hold)$",
    )
    reviewer_note: Optional[str] = Field(
        None, description="Admin note for audit trail"
    )


# ── Response Schemas ─────────────────────────────────────────────────────────

class ClaimResponse(BaseModel):
    claim_id: UUID
    policy_id: UUID
    worker_id: UUID
    trigger_event_id: UUID
    status: str
    payout_amount: float
    fraud_score: Optional[float] = None
    fraud_flags: Optional[list] = None
    created_at: datetime
    reviewed_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ClaimDetailResponse(ClaimResponse):
    """Extended claim response with trigger event context."""
    event_type: Optional[str] = None
    event_tier: Optional[str] = None
    zone_code: Optional[str] = None
    city: Optional[str] = None
    metric_value: Optional[float] = None


class ClaimListResponse(BaseModel):
    claims: list[ClaimResponse]
    total: int
    zone_code: Optional[str] = None


class ClaimCreatedEvent(BaseModel):
    """Internal event published when a claim is auto-created from a trigger."""
    claim_id: str
    policy_id: str
    worker_id: str
    trigger_event_id: str
    zone_code: str
    zone_id: str
    city: str
    event_type: str
    tier: str
    payout_amount: float
    fraud_score: float
    status: str
    worker_upi_id: Optional[str] = None
    worker_name: Optional[str] = None


class FraudScoreResponse(BaseModel):
    """Fraud score breakdown for transparency."""
    total_score: float
    gps_physics_score: float
    device_sensor_score: float
    network_geo_score: float
    behavioral_score: float
    flags: list[str]
    decision: str  # approved, soft_hold, blocked
