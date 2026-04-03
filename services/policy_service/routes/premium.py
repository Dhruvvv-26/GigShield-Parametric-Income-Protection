"""
Policy Service — Premium Routes
POST /api/v1/premium/calculate
GET  /api/v1/premium/history/{worker_id}
"""
import logging
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.schemas import PremiumBreakdown, PremiumCalculateRequest, PremiumCalculateResponse
from services.premium_engine import PremiumCalculationEngine
from shared.config import get_settings
from shared.database import get_db
from shared.redis_client import cache_get, cache_set

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()
engine = PremiumCalculationEngine()


@router.post(
    "/calculate",
    response_model=PremiumCalculateResponse,
    summary="Calculate weekly premium for a worker",
    description="""
    Calculates the personalised weekly premium for a Q-Commerce rider.

    **Phase 2**: Rule-based formula — deterministic, fully auditable.
    **Phase 3**: Replaced by XGBoost + LightGBM ensemble with SHAP waterfall.

    Result is cached in Redis for 10 minutes and logged to premium_calculations table.
    """,
)
async def calculate_premium(
    payload: PremiumCalculateRequest,
    db: AsyncSession = Depends(get_db),
) -> PremiumCalculateResponse:

    # ── Cache check ───────────────────────────────────────────────────────────
    cache_key = (
        f"premium:{payload.worker_id}:{payload.zone_code}:"
        f"{payload.coverage_tier}:{payload.vehicle_type}"
    )
    cached = await cache_get(cache_key)
    if cached:
        import json
        return PremiumCalculateResponse(**json.loads(cached))

    # ── Resolve zone_id from zone_code (call Worker Service) ──────────────────
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            resp = await client.get(
                f"{settings.worker_service_url}/api/v1/zones/{payload.zone_code}"
            )
            resp.raise_for_status()
            zone_data = resp.json()
            zone_id = UUID(zone_data["zone_id"])
            city = zone_data["city"]
        except (httpx.HTTPError, KeyError) as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Zone '{payload.zone_code}' not found: {e}",
            )

    # ── Calculate and log ─────────────────────────────────────────────────────
    result = await engine.calculate_and_log(
        db=db,
        worker_id=payload.worker_id,
        zone_id=zone_id,
        zone_code=payload.zone_code,
        coverage_tier=payload.coverage_tier,
        vehicle_type=payload.vehicle_type,
        declared_daily_trips=payload.declared_daily_trips,
        declared_daily_income=payload.declared_daily_income,
        work_hours_profile=payload.work_hours_profile,
    )

    breakdown = PremiumBreakdown(**result["breakdown"])

    response = PremiumCalculateResponse(
        worker_id=payload.worker_id,
        zone_code=payload.zone_code,
        city=city,
        coverage_tier=payload.coverage_tier,
        weekly_premium=result["final_premium"],
        max_payout_per_event=result["max_payout_per_event"],
        max_payout_per_week=result["max_payout_per_week"],
        breakdown=breakdown,
        calculation_id=result["calculation_id"],
    )

    # Cache result
    import json
    await cache_set(cache_key, response.model_dump_json(), ttl=600)

    return response
