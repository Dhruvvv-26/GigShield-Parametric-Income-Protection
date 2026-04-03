"""
Trigger Engine — Zone Resolver
Resolves city-level trigger events to specific zone polygons.
All queries are local PostGIS — zero external API calls at runtime.
"""
import logging
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class Zone:
    """Lightweight zone object — avoids importing Worker Service ORM models."""
    def __init__(self, id, zone_code, zone_name, city):
        self.id = id
        self.zone_code = zone_code
        self.zone_name = zone_name
        self.city = city


class ZoneResolver:
    """
    Resolves trigger events to affected zones.
    Used by all pollers to determine which zones to emit events for.
    """

    async def get_zones_for_city(
        self,
        db: AsyncSession,
        city: str,
    ) -> list[Zone]:
        """
        Return all active zones for a given city.
        Called when a city-level trigger is detected.
        """
        result = await db.execute(
            text(
                "SELECT id, zone_code, zone_name, city FROM zones "
                "WHERE city = :city AND is_active = TRUE"
            ),
            {"city": city},
        )
        rows = result.fetchall()
        return [Zone(id=r[0], zone_code=r[1], zone_name=r[2], city=r[3]) for r in rows]

    async def get_zone_by_code(
        self,
        db: AsyncSession,
        zone_code: str,
    ) -> Zone | None:
        result = await db.execute(
            text("SELECT id, zone_code, zone_name, city FROM zones WHERE zone_code = :code"),
            {"code": zone_code},
        )
        row = result.fetchone()
        if row:
            return Zone(id=row[0], zone_code=row[1], zone_name=row[2], city=row[3])
        return None

    async def find_zone_for_point(
        self,
        db: AsyncSession,
        latitude: float,
        longitude: float,
    ) -> Zone | None:
        """
        PostGIS ST_Within query — find zone for a GPS coordinate.
        Used during claim verification to confirm worker was in disruption zone.
        """
        result = await db.execute(
            text(
                "SELECT id, zone_code, zone_name, city FROM zones "
                "WHERE is_active = TRUE "
                "AND ST_Within("
                "    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326),"
                "    boundary"
                ") LIMIT 1"
            ),
            {"lat": latitude, "lon": longitude},
        )
        row = result.fetchone()
        if row:
            return Zone(id=row[0], zone_code=row[1], zone_name=row[2], city=row[3])
        return None
