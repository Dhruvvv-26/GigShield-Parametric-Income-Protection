"""
Worker Service — Zone Routes
GET  /api/v1/zones
POST /api/v1/zones/lookup
GET  /api/v1/zones/{zone_code}
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from models.schemas import ZoneLookupRequest, ZoneLookupResponse, ZoneResponse
from services.zone_assignment import ZoneAssignmentService
from shared.database import get_db

router = APIRouter()
zone_service = ZoneAssignmentService()


@router.get(
    "",
    response_model=list[ZoneResponse],
    summary="List all active Q-Commerce zones",
)
async def list_zones(
    city: str | None = Query(None, description="Filter by city code"),
    db: AsyncSession = Depends(get_db),
) -> list[ZoneResponse]:
    zones = await zone_service.list_zones(db, city=city)
    return [
        ZoneResponse(
            zone_id=z.id,
            zone_code=z.zone_code,
            zone_name=z.zone_name,
            city=z.city,
            risk_multiplier=float(z.risk_multiplier),
            is_active=z.is_active,
        )
        for z in zones
    ]


@router.post(
    "/lookup",
    response_model=ZoneLookupResponse,
    summary="Find zone for GPS coordinates",
    description="PostGIS ST_Within query — returns zone within milliseconds.",
)
async def lookup_zone(
    payload: ZoneLookupRequest,
    db: AsyncSession = Depends(get_db),
) -> ZoneLookupResponse:
    zone = await zone_service.find_zone_for_coordinates(
        db, payload.latitude, payload.longitude
    )
    if not zone:
        return ZoneLookupResponse(
            found=False,
            message="Coordinates are outside all covered Q-Commerce zones",
        )
    return ZoneLookupResponse(
        found=True,
        zone=ZoneResponse(
            zone_id=zone.id,
            zone_code=zone.zone_code,
            zone_name=zone.zone_name,
            city=zone.city,
            risk_multiplier=float(zone.risk_multiplier),
            is_active=zone.is_active,
        ),
        message=f"Zone found: {zone.zone_name}",
    )


@router.get(
    "/{zone_code}",
    response_model=ZoneResponse,
    summary="Get zone by zone_code",
)
async def get_zone(
    zone_code: str,
    db: AsyncSession = Depends(get_db),
) -> ZoneResponse:
    zone = await zone_service.get_zone_by_code(db, zone_code)
    if not zone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Zone '{zone_code}' not found",
        )
    return ZoneResponse(
        zone_id=zone.id,
        zone_code=zone.zone_code,
        zone_name=zone.zone_name,
        city=zone.city,
        risk_multiplier=float(zone.risk_multiplier),
        is_active=zone.is_active,
    )
