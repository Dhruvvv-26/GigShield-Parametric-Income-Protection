"""
Worker Service — Worker Profile Routes
GET/PATCH /api/v1/riders/{worker_id}
POST /api/v1/riders/{worker_id}/gps
"""
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from geoalchemy2.shape import from_shape
from shapely.geometry import Point
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.schemas import (
    GpsPingRequest,
    GpsPingResponse,
    WorkerProfileResponse,
    WorkerUpdateRequest,
)
from models.worker import GpsPing, Worker
from services.zone_assignment import ZoneAssignmentService
from shared.database import get_db
from shared.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter()
zone_service = ZoneAssignmentService()


async def _get_worker_or_404(worker_id: UUID, db: AsyncSession) -> Worker:
    result = await db.execute(
        select(Worker).where(Worker.id == worker_id, Worker.is_active == True)
    )
    worker = result.scalar_one_or_none()
    if not worker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Worker {worker_id} not found",
        )
    return worker


@router.get(
    "/{worker_id}",
    response_model=WorkerProfileResponse,
    summary="Get worker profile",
)
async def get_worker(
    worker_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> WorkerProfileResponse:
    worker = await _get_worker_or_404(worker_id, db)

    # Load zone
    from models.worker import Zone
    zone_result = await db.execute(
        select(Zone).where(Zone.id == worker.zone_id)
    )
    zone = zone_result.scalar_one_or_none()

    return WorkerProfileResponse(
        worker_id=worker.id,
        full_name=worker.full_name,
        platform=worker.platform,
        vehicle_type=worker.vehicle_type,
        work_hours_profile=worker.work_hours_profile,
        declared_daily_trips=worker.declared_daily_trips,
        declared_daily_income=float(worker.declared_daily_income),
        zone_code=zone.zone_code if zone else "unassigned",
        zone_name=zone.zone_name if zone else "Unassigned",
        city=zone.city if zone else "unknown",
        kyc_status=worker.kyc_status,
        is_active=worker.is_active,
        created_at=worker.created_at,
    )


@router.patch(
    "/{worker_id}",
    response_model=WorkerProfileResponse,
    summary="Update worker profile",
)
async def update_worker(
    worker_id: UUID,
    payload: WorkerUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> WorkerProfileResponse:
    worker = await _get_worker_or_404(worker_id, db)

    if payload.declared_daily_trips is not None:
        worker.declared_daily_trips = payload.declared_daily_trips
    if payload.declared_daily_income is not None:
        worker.declared_daily_income = payload.declared_daily_income
    if payload.work_hours_profile is not None:
        worker.work_hours_profile = payload.work_hours_profile
    if payload.upi_id is not None:
        from routes.registration import _encrypt_upi
        worker.upi_id = _encrypt_upi(payload.upi_id)

    logger.info("Worker profile updated", worker_id=str(worker_id))

    # Re-fetch with zone
    return await get_worker(worker_id, db)


@router.post(
    "/{worker_id}/gps",
    response_model=GpsPingResponse,
    summary="Record GPS ping from worker app",
    description="Called every 5 minutes by the React Native app. Used for fraud detection.",
)
async def record_gps_ping(
    worker_id: UUID,
    payload: GpsPingRequest,
    db: AsyncSession = Depends(get_db),
) -> GpsPingResponse:
    worker = await _get_worker_or_404(worker_id, db)

    point_wkb = from_shape(
        Point(payload.longitude, payload.latitude), srid=4326
    )

    ping = GpsPing(
        worker_id=worker_id,
        location=point_wkb,
        accuracy_m=payload.accuracy_metres,
        speed_kmh=payload.speed_kmh,
        altitude_m=payload.altitude_metres,
    )
    db.add(ping)

    # Update worker's current location + re-check zone assignment
    zone = await zone_service.find_zone_for_coordinates(
        db, payload.latitude, payload.longitude
    )
    worker.work_location = point_wkb
    if zone:
        worker.zone_id = zone.id

    return GpsPingResponse(
        ping_recorded=True,
        zone_code=zone.zone_code if zone else None,
        in_active_disruption_zone=False,  # Phase 3: check active trigger events
    )


@router.delete(
    "/{worker_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate worker (GDPR/PDPB soft delete)",
)
async def deactivate_worker(
    worker_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    worker = await _get_worker_or_404(worker_id, db)
    worker.is_active = False
    worker.phone_hash = "DELETED"
    worker.upi_id = None
    worker.device_fingerprint = None
    logger.info("Worker deactivated (GDPR)", worker_id=str(worker_id))
