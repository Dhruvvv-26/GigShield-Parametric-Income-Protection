"""
Trigger Engine — Status Routes
GET /api/v1/trigger/status        — All active triggers across cities
GET /api/v1/trigger/status/{zone} — Active triggers for a specific zone
GET /api/v1/trigger/history       — Recent trigger events from DB
"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "/status",
    summary="Get active trigger events across all cities",
    description="Returns all unresolved trigger events. Used by admin dashboard.",
)
async def get_trigger_status(
    city: str | None = Query(None, description="Filter by city code"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    query = """
        SELECT
            te.id,
            te.event_type,
            te.tier,
            te.metric_value,
            te.metric_unit,
            te.data_source,
            te.detected_at,
            te.sustained_since,
            z.zone_code,
            z.zone_name,
            z.city
        FROM trigger_events te
        JOIN zones z ON z.id = te.zone_id
        WHERE te.resolved_at IS NULL
        {city_filter}
        ORDER BY te.detected_at DESC
        LIMIT 100
    """
    city_filter = "AND z.city = :city" if city else ""
    result = await db.execute(
        text(query.format(city_filter=city_filter)),
        {"city": city} if city else {},
    )
    rows = result.fetchall()

    active_triggers = [
        {
            "trigger_id":    str(row[0]),
            "event_type":    row[1],
            "tier":          row[2],
            "metric_value":  float(row[3]) if row[3] else None,
            "metric_unit":   row[4],
            "data_source":   row[5],
            "detected_at":   row[6].isoformat() if row[6] else None,
            "sustained_since": row[7].isoformat() if row[7] else None,
            "zone_code":     row[8],
            "zone_name":     row[9],
            "city":          row[10],
        }
        for row in rows
    ]

    return {
        "active_trigger_count": len(active_triggers),
        "active_triggers": active_triggers,
        "as_of": datetime.now(timezone.utc).isoformat(),
    }


@router.get(
    "/history",
    summary="Recent trigger events (last 24 hours)",
)
async def get_trigger_history(
    hours: int = Query(24, ge=1, le=168, description="Lookback window in hours"),
    event_type: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    query = """
        SELECT
            te.id, te.event_type, te.tier, te.metric_value,
            te.metric_unit, te.data_source, te.detected_at,
            z.zone_code, z.city,
            COUNT(c.id) AS claims_generated
        FROM trigger_events te
        JOIN zones z ON z.id = te.zone_id
        LEFT JOIN claims c ON c.trigger_event_id = te.id
        WHERE te.detected_at > NOW() - INTERVAL ':hours hours'
        {event_filter}
        GROUP BY te.id, z.zone_code, z.city
        ORDER BY te.detected_at DESC
        LIMIT 200
    """
    event_filter = "AND te.event_type = :event_type" if event_type else ""
    params = {"hours": hours}
    if event_type:
        params["event_type"] = event_type

    try:
        result = await db.execute(
            text(query.format(event_filter=event_filter).replace(
                "':hours hours'", f"'{hours} hours'"
            )),
            params,
        )
        rows = result.fetchall()
    except Exception:
        rows = []

    return {
        "lookback_hours": hours,
        "total_events": len(rows),
        "events": [
            {
                "trigger_id":       str(row[0]),
                "event_type":       row[1],
                "tier":             row[2],
                "metric_value":     float(row[3]) if row[3] else None,
                "metric_unit":      row[4],
                "data_source":      row[5],
                "detected_at":      row[6].isoformat() if row[6] else None,
                "zone_code":        row[7],
                "city":             row[8],
                "claims_generated": int(row[9]) if row[9] else 0,
            }
            for row in rows
        ],
    }
