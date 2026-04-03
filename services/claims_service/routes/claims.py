"""
Claims Service — REST API Routes
Endpoints:
  GET  /api/v1/claims/{claim_id}              — single claim detail
  GET  /api/v1/claims/worker/{worker_id}       — claims for a worker
  GET  /api/v1/claims/zone/{zone_code}         — claims in a zone
  POST /api/v1/claims/sensor_data/{worker_id}  — receive sensor data from mobile app
  POST /api/v1/claims/admin/review/{claim_id}  — admin manual override
"""
import json
import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select, and_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from models.claim import Claim, TriggerEvent, Zone, Worker
from models.schemas import (
    ClaimAdminReviewRequest,
    ClaimDetailResponse,
    ClaimListResponse,
    ClaimResponse,
    SensorDataPayload,
)
from shared.database import get_db
from shared.redis_client import get_redis

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "/{claim_id}",
    response_model=ClaimDetailResponse,
    summary="Get claim by ID",
)
async def get_claim(
    claim_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve a single claim with trigger event context."""
    result = await db.execute(
        select(Claim).where(Claim.id == claim_id)
    )
    claim = result.scalar_one_or_none()
    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Claim {claim_id} not found",
        )

    # Fetch trigger event context
    te_result = await db.execute(
        select(TriggerEvent).where(TriggerEvent.id == claim.trigger_event_id)
    )
    trigger_event = te_result.scalar_one_or_none()

    # Fetch zone context
    zone_code = None
    city = None
    if trigger_event:
        z_result = await db.execute(
            select(Zone).where(Zone.id == trigger_event.zone_id)
        )
        zone = z_result.scalar_one_or_none()
        if zone:
            zone_code = zone.zone_code
            city = zone.city

    return ClaimDetailResponse(
        claim_id=claim.id,
        policy_id=claim.policy_id,
        worker_id=claim.worker_id,
        trigger_event_id=claim.trigger_event_id,
        status=claim.status,
        payout_amount=float(claim.payout_amount),
        fraud_score=float(claim.fraud_score) if claim.fraud_score else None,
        fraud_flags=claim.fraud_flags,
        created_at=claim.created_at,
        reviewed_at=claim.reviewed_at,
        completed_at=claim.completed_at,
        event_type=trigger_event.event_type if trigger_event else None,
        event_tier=trigger_event.tier if trigger_event else None,
        zone_code=zone_code,
        city=city,
        metric_value=float(trigger_event.metric_value) if trigger_event else None,
    )


@router.get(
    "/worker/{worker_id}",
    response_model=ClaimListResponse,
    summary="Get claims for a worker (payout history)",
)
async def get_worker_claims(
    worker_id: UUID,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve all claims for a specific worker, ordered by date descending."""
    result = await db.execute(
        select(Claim)
        .where(Claim.worker_id == worker_id)
        .order_by(desc(Claim.created_at))
        .limit(limit)
        .offset(offset)
    )
    claims = result.scalars().all()

    count_result = await db.execute(
        select(func.count(Claim.id)).where(Claim.worker_id == worker_id)
    )
    total = count_result.scalar() or 0

    return ClaimListResponse(
        claims=[
            ClaimResponse(
                claim_id=c.id,
                policy_id=c.policy_id,
                worker_id=c.worker_id,
                trigger_event_id=c.trigger_event_id,
                status=c.status,
                payout_amount=float(c.payout_amount),
                fraud_score=float(c.fraud_score) if c.fraud_score else None,
                fraud_flags=c.fraud_flags,
                created_at=c.created_at,
                reviewed_at=c.reviewed_at,
                completed_at=c.completed_at,
            )
            for c in claims
        ],
        total=total,
    )


@router.get(
    "/zone/{zone_code}",
    response_model=ClaimListResponse,
    summary="Get claims in a zone (admin dashboard)",
)
async def get_zone_claims(
    zone_code: str,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve claims for a specific zone. Used by admin dashboard."""
    # Resolve zone_code to zone_id
    zone_result = await db.execute(
        select(Zone).where(Zone.zone_code == zone_code)
    )
    zone = zone_result.scalar_one_or_none()
    if not zone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Zone '{zone_code}' not found",
        )

    # Get trigger events in this zone
    te_result = await db.execute(
        select(TriggerEvent.id).where(TriggerEvent.zone_id == zone.id)
    )
    trigger_event_ids = [row[0] for row in te_result.all()]

    if not trigger_event_ids:
        return ClaimListResponse(claims=[], total=0, zone_code=zone_code)

    # Get claims for these trigger events
    result = await db.execute(
        select(Claim)
        .where(Claim.trigger_event_id.in_(trigger_event_ids))
        .order_by(desc(Claim.created_at))
        .limit(limit)
    )
    claims = result.scalars().all()

    return ClaimListResponse(
        claims=[
            ClaimResponse(
                claim_id=c.id,
                policy_id=c.policy_id,
                worker_id=c.worker_id,
                trigger_event_id=c.trigger_event_id,
                status=c.status,
                payout_amount=float(c.payout_amount),
                fraud_score=float(c.fraud_score) if c.fraud_score else None,
                fraud_flags=c.fraud_flags,
                created_at=c.created_at,
                reviewed_at=c.reviewed_at,
                completed_at=c.completed_at,
            )
            for c in claims
        ],
        total=len(claims),
        zone_code=zone_code,
    )


@router.post(
    "/sensor_data/{worker_id}",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Receive sensor data from mobile app",
)
async def submit_sensor_data(
    worker_id: UUID,
    payload: SensorDataPayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Mobile app submits sensor data during active trigger events.
    Data is stored in Redis and used for fraud scoring when claims are created.

    SECURITY: The raw client IP is extracted from the TCP connection
    (request.client.host) and stored alongside the sensor payload.
    This IP is used by the fraud engine for server-side IPinfo.io
    geolocation — it CANNOT be spoofed by the mobile client.
    """
    # ── Layer 5 Zero-Trust: Time Lock ─────────────────────────────────────────
    if payload.capture_timestamp_ms:
        current_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        if abs(current_time_ms - payload.capture_timestamp_ms) > 300000:  # 5 minutes
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="STALE_CAPTURE_REJECTED"
            )

    # ── Layer 5 Zero-Trust: Zone Mismatch Lock ────────────────────────────────────
    result = await db.execute(select(Worker).where(Worker.id == worker_id))
    worker = result.scalar_one_or_none()
    
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")

    if not worker.primary_zone_id or str(worker.primary_zone_id) != payload.active_zone_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="ZONE_MISMATCH_REJECTED"
        )
        
    # ── Layer 5 Zero-Trust: Spatial Geo Lock (PostGIS) ────────────────────────────
    if payload.camera_gps_lat is not None and payload.camera_gps_lng is not None:
        spatial_query = select(Zone).where(
            and_(
                Zone.id == worker.primary_zone_id,
                func.ST_Within(
                    func.ST_SetSRID(func.ST_MakePoint(payload.camera_gps_lng, payload.camera_gps_lat), 4326),
                    Zone.boundary
                )
            )
        )
        spatial_result = await db.execute(spatial_query)
        valid_zone = spatial_result.scalar_one_or_none()
        
        if not valid_zone:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="OUT_OF_BOUNDS_REJECTED"
            )

    # Extract raw client IP from the TCP connection
    client_ip = request.client.host if request.client else None

    redis = await get_redis()
    sensor_key = f"sensor_data:{worker_id}"

    # Include server-extracted client IP in the stored payload
    data = payload.model_dump()
    data["_server_client_ip"] = client_ip
    
    # Strip heavy camera fields before passing to ML / Redis 
    data.pop("photo_base64", None)

    await redis.setex(
        sensor_key,
        3600,  # 1-hour TTL
        json.dumps(data),
    )
    logger.info(
        f"Sensor data received | worker={worker_id} | client_ip={client_ip} | gps_pings={len(payload.gps_pings)}"
    )
    return {"status": "accepted", "worker_id": str(worker_id), "client_ip_logged": True}


@router.post(
    "/admin/review/{claim_id}",
    response_model=ClaimResponse,
    summary="Admin manual review/override",
)
async def admin_review_claim(
    claim_id: UUID,
    request: ClaimAdminReviewRequest,
    db: AsyncSession = Depends(get_db),
):
    """Admin override for claim status. Supports approve, reject, release_hold."""
    result = await db.execute(
        select(Claim).where(Claim.id == claim_id)
    )
    claim = result.scalar_one_or_none()
    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Claim {claim_id} not found",
        )

    now = datetime.now(timezone.utc)

    if request.action == "approve":
        claim.status = "auto_approved"
        claim.reviewed_at = now
    elif request.action == "reject":
        claim.status = "rejected"
        claim.reviewed_at = now
    elif request.action == "release_hold":
        if claim.status != "soft_hold":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Can only release_hold on claims with status soft_hold",
            )
        claim.status = "auto_approved"
        claim.reviewed_at = now

    await db.flush()

    return ClaimResponse(
        claim_id=claim.id,
        policy_id=claim.policy_id,
        worker_id=claim.worker_id,
        trigger_event_id=claim.trigger_event_id,
        status=claim.status,
        payout_amount=float(claim.payout_amount),
        fraud_score=float(claim.fraud_score) if claim.fraud_score else None,
        fraud_flags=claim.fraud_flags,
        created_at=claim.created_at,
        reviewed_at=claim.reviewed_at,
        completed_at=claim.completed_at,
    )
