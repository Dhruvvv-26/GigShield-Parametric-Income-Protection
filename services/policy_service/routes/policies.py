"""
Policy Service — Policy Routes
POST   /api/v1/policies
GET    /api/v1/policies/{policy_id}
GET    /api/v1/policies/worker/{worker_id}
PATCH  /api/v1/policies/{policy_id}/activate
POST   /api/v1/policies/{policy_id}/renew
"""
import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.policy import Policy
from models.schemas import (
    PolicyActivateRequest,
    PolicyCreateRequest,
    PolicyListResponse,
    PolicyResponse,
)
from services.premium_engine import PremiumCalculationEngine
from shared.config import get_settings
from shared.database import get_db
from shared.logging_config import get_logger
from shared.redis_client import cache_delete

logger = get_logger(__name__)
router = APIRouter()
settings = get_settings()
premium_engine = PremiumCalculationEngine()

COVERAGE_PERIOD_DAYS = 7  # Weekly policy


async def _policy_to_response(policy: Policy, db) -> PolicyResponse:
    """Convert ORM Policy to response schema, fetching zone details."""
    from sqlalchemy import text
    zone_result = await db.execute(
        text("SELECT zone_code, zone_name, city FROM zones WHERE id = :id"),
        {"id": str(policy.zone_id)},
    )
    zone_row = zone_result.fetchone()
    zone_code = zone_row[0] if zone_row else "unknown"
    zone_name = zone_row[1] if zone_row else "Unknown"
    city      = zone_row[2] if zone_row else "unknown"

    return PolicyResponse(
        policy_id=policy.id,
        worker_id=policy.worker_id,
        zone_code=zone_code,
        zone_name=zone_name,
        city=city,
        coverage_tier=policy.coverage_tier,
        status=policy.status,
        weekly_premium=float(policy.weekly_premium),
        max_payout_per_event=float(policy.max_payout_per_event),
        max_payout_per_week=float(policy.max_payout_per_week),
        coverage_start=policy.coverage_start,
        coverage_end=policy.coverage_end,
        created_at=policy.created_at,
    )


@router.post(
    "",
    response_model=PolicyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new weekly policy",
    description="""
    Creates a KavachAI parametric insurance policy for a Q-Commerce rider.

    Flow:
    1. Fetch worker profile from Worker Service
    2. Calculate premium for their zone + tier
    3. Create policy in PENDING_PAYMENT status
    4. Call /activate once Razorpay payment is confirmed (Week 4)
    """,
)
async def create_policy(
    payload: PolicyCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> PolicyResponse:

    # ── 1. Check for existing active policy ───────────────────────────────────
    now = datetime.now(timezone.utc)
    existing = await db.execute(
        select(Policy)
        .where(Policy.worker_id == payload.worker_id)
        .where(Policy.status == "active")
        .where(Policy.coverage_end > now)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Worker already has an active policy. Renew after current policy expires.",
        )

    # ── 2. Fetch worker profile ───────────────────────────────────────────────
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            resp = await client.get(
                f"{settings.worker_service_url}/api/v1/riders/{payload.worker_id}"
            )
            resp.raise_for_status()
            worker = resp.json()
        except httpx.HTTPError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Worker {payload.worker_id} not found: {e}",
            )

    # ── 3. Fetch zone details ─────────────────────────────────────────────────
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            zone_resp = await client.get(
                f"{settings.worker_service_url}/api/v1/zones/{worker['zone_code']}"
            )
            zone_resp.raise_for_status()
            zone = zone_resp.json()
        except httpx.HTTPError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Could not fetch zone for worker: {e}",
            )

    # ── 4. Calculate premium ──────────────────────────────────────────────────
    calc = premium_engine.calculate(
        zone_code=worker["zone_code"],
        coverage_tier=payload.coverage_tier,
        vehicle_type=worker["vehicle_type"],
        declared_daily_trips=worker["declared_daily_trips"],
        declared_daily_income=worker["declared_daily_income"],
        work_hours_profile=worker["work_hours_profile"],
    )

    # ── 5. Create policy ──────────────────────────────────────────────────────
    policy = Policy(
        worker_id=payload.worker_id,
        zone_id=UUID(zone["zone_id"]),
        coverage_tier=payload.coverage_tier,
        status="active" if payload.razorpay_payment_id else "pending_payment",
        weekly_premium=calc["final_premium"],
        max_payout_per_event=calc["max_payout_per_event"],
        max_payout_per_week=calc["max_payout_per_week"],
        razorpay_payment_id=payload.razorpay_payment_id,
        coverage_start=now if payload.razorpay_payment_id else None,
        coverage_end=(now + timedelta(days=COVERAGE_PERIOD_DAYS))
        if payload.razorpay_payment_id else None,
    )
    db.add(policy)
    await db.flush()

    logger.info(
        "Policy created",
        policy_id=str(policy.id),
        worker_id=str(payload.worker_id),
        tier=payload.coverage_tier,
        premium=calc["final_premium"],
        status=policy.status,
    )

    return await _policy_to_response(policy, db)


@router.get(
    "/worker/{worker_id}",
    response_model=PolicyListResponse,
    summary="Get all policies for a worker",
)
async def get_worker_policies(
    worker_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> PolicyListResponse:
    result = await db.execute(
        select(Policy)
        .where(Policy.worker_id == worker_id)
        .order_by(Policy.created_at.desc())
        .limit(50)
    )
    policies = list(result.scalars().all())
    now = datetime.now(timezone.utc)

    responses = [await _policy_to_response(p, db) for p in policies]
    active_count = sum(
        1 for p in policies
        if p.status == "active" and p.coverage_end and p.coverage_end > now
    )

    return PolicyListResponse(
        policies=responses,
        total=len(responses),
        active_count=active_count,
    )


@router.get(
    "/{policy_id}",
    response_model=PolicyResponse,
    summary="Get policy by ID",
)
async def get_policy(
    policy_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> PolicyResponse:
    result = await db.execute(select(Policy).where(Policy.id == policy_id))
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail=f"Policy {policy_id} not found")
    return await _policy_to_response(policy, db)


@router.patch(
    "/{policy_id}/activate",
    response_model=PolicyResponse,
    summary="Activate policy after payment confirmation",
    description="Called by Payment Service webhook (Week 4) when Razorpay confirms payment.",
)
async def activate_policy(
    policy_id: UUID,
    payload: PolicyActivateRequest,
    db: AsyncSession = Depends(get_db),
) -> PolicyResponse:
    result = await db.execute(select(Policy).where(Policy.id == policy_id))
    policy = result.scalar_one_or_none()

    if not policy:
        raise HTTPException(status_code=404, detail=f"Policy {policy_id} not found")
    if policy.status == "active":
        raise HTTPException(status_code=409, detail="Policy is already active")
    if policy.status == "cancelled":
        raise HTTPException(status_code=422, detail="Cannot activate a cancelled policy")

    now = datetime.now(timezone.utc)
    policy.status = "active"
    policy.razorpay_payment_id = payload.razorpay_payment_id
    policy.coverage_start = now
    policy.coverage_end = now + timedelta(days=COVERAGE_PERIOD_DAYS)

    logger.info("Policy activated", policy_id=str(policy_id))
    return await _policy_to_response(policy, db)


@router.post(
    "/{policy_id}/renew",
    response_model=PolicyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Renew an expiring policy",
    description="Creates a new policy starting from the current policy's expiry date.",
)
async def renew_policy(
    policy_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> PolicyResponse:
    result = await db.execute(select(Policy).where(Policy.id == policy_id))
    existing = result.scalar_one_or_none()

    if not existing:
        raise HTTPException(status_code=404, detail="Policy not found")

    now = datetime.now(timezone.utc)

    # Recalculate premium (seasonal factors change week to week)
    from sqlalchemy import text
    zone_result = await db.execute(
        text("SELECT zone_code FROM zones WHERE id = :id"),
        {"id": str(existing.zone_id)},
    )
    zone_row = zone_result.fetchone()
    zone_code = zone_row[0] if zone_row else "delhi_rohini"

    # Fetch worker for vehicle/trips/hours
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            resp = await client.get(
                f"{settings.worker_service_url}/api/v1/riders/{existing.worker_id}"
            )
            worker = resp.json()
        except httpx.HTTPError:
            worker = {
                "vehicle_type": "bicycle",
                "declared_daily_trips": 28,
                "declared_daily_income": 1200,
                "work_hours_profile": "full_day",
            }

    calc = premium_engine.calculate(
        zone_code=zone_code,
        coverage_tier=existing.coverage_tier,
        vehicle_type=worker.get("vehicle_type", "bicycle"),
        declared_daily_trips=worker.get("declared_daily_trips", 28),
        declared_daily_income=worker.get("declared_daily_income", 1200),
        work_hours_profile=worker.get("work_hours_profile", "full_day"),
    )

    renewed = Policy(
        worker_id=existing.worker_id,
        zone_id=existing.zone_id,
        coverage_tier=existing.coverage_tier,
        status="pending_payment",
        weekly_premium=calc["final_premium"],
        max_payout_per_event=calc["max_payout_per_event"],
        max_payout_per_week=calc["max_payout_per_week"],
    )
    db.add(renewed)
    await db.flush()

    logger.info(
        "Policy renewed",
        old_policy_id=str(policy_id),
        new_policy_id=str(renewed.id),
        new_premium=calc["final_premium"],
    )

    return await _policy_to_response(renewed, db)
