"""
Worker Service — Zone Assignment Service
Core PostGIS spatial query logic.
Finds which Q-Commerce zone a given GPS coordinate falls within.
"""
import logging
from uuid import UUID

from geoalchemy2.functions import ST_Within, ST_SetSRID, ST_MakePoint
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.worker import Zone, Worker
from shared.redis_client import cache_get, cache_set

logger = logging.getLogger(__name__)


class ZoneAssignmentService:
    """
    Handles all spatial zone assignment operations.
    All zone matching is PostGIS-local — zero external API dependency.
    """

    CACHE_TTL = 3600  # 1 hour — zone polygons don't change

    async def find_zone_for_coordinates(
        self,
        db: AsyncSession,
        latitude: float,
        longitude: float,
    ) -> Zone | None:
        """
        Core function: Given a GPS coordinate, find which zone it falls within.
        Uses PostGIS ST_Within for sub-millisecond GIST-indexed spatial lookup.

        Equivalent SQL:
            SELECT * FROM zones
            WHERE ST_Within(
                ST_SetSRID(ST_MakePoint(:lon, :lat), 4326),
                boundary
            )
            AND is_active = TRUE
            LIMIT 1;
        """
        cache_key = f"zone_lookup:{latitude:.4f}:{longitude:.4f}"
        cached = await cache_get(cache_key)
        if cached:
            zone_code = cached
            result = await db.execute(
                select(Zone).where(Zone.zone_code == zone_code)
            )
            return result.scalar_one_or_none()

        point = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)

        result = await db.execute(
            select(Zone)
            .where(Zone.is_active == True)
            .where(ST_Within(point, Zone.boundary))
            .limit(1)
        )
        zone = result.scalar_one_or_none()

        if zone:
            await cache_set(cache_key, zone.zone_code, ttl=self.CACHE_TTL)

        return zone

    async def assign_zone_to_worker(
        self,
        db: AsyncSession,
        worker: Worker,
        latitude: float,
        longitude: float,
    ) -> Zone | None:
        """
        Find and assign a zone to a worker based on their work location.
        Updates worker.zone_id and work_location in the database.
        Returns the assigned zone, or None if outside all covered zones.
        """
        from geoalchemy2.shape import from_shape
        from shapely.geometry import Point

        zone = await self.find_zone_for_coordinates(db, latitude, longitude)

        # Update worker's spatial data
        point_wkb = from_shape(Point(longitude, latitude), srid=4326)
        worker.work_location = point_wkb
        worker.zone_id = zone.id if zone else None

        logger.info(
            f"Zone assigned",
            extra={
                "worker_id": str(worker.id),
                "zone": zone.zone_code if zone else "none",
                "lat": latitude,
                "lon": longitude,
            },
        )
        return zone

    async def get_workers_in_zone(
        self,
        db: AsyncSession,
        zone_id: UUID,
        active_only: bool = True,
    ) -> list[Worker]:
        """
        Retrieve all workers assigned to a given zone.
        Used by Claims Service to identify who gets a payout after a trigger event.
        """
        query = select(Worker).where(Worker.zone_id == zone_id)
        if active_only:
            query = query.where(Worker.is_active == True)

        result = await db.execute(query)
        return list(result.scalars().all())

    async def list_zones(
        self,
        db: AsyncSession,
        city: str | None = None,
    ) -> list[Zone]:
        """List all active zones, optionally filtered by city."""
        query = select(Zone).where(Zone.is_active == True)
        if city:
            query = query.where(Zone.city == city)
        query = query.order_by(Zone.city, Zone.zone_name)

        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_zone_by_code(
        self,
        db: AsyncSession,
        zone_code: str,
    ) -> Zone | None:
        result = await db.execute(
            select(Zone).where(Zone.zone_code == zone_code)
        )
        return result.scalar_one_or_none()
