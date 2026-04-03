"""
KavachAI Notification Service — OneSignal Push Notifications
==============================================================
Sends instant push notifications to gig riders when:
  1. A parametric trigger fires in their zone
  2. A payout is processed and credited to their UPI

Uses the OneSignal REST API (https://onesignal.com/api/v1/notifications)
with the free tier (unlimited mobile push, 10K web push).

Environment Variables:
  ONESIGNAL_APP_ID    — Your OneSignal App ID
  ONESIGNAL_REST_KEY  — Your OneSignal REST API Key (starts with "Basic ")

Usage:
    from notification_service.sender import send_payout_notification, send_trigger_notification

    await send_payout_notification(
        player_id="onesignal-player-id-for-rider",
        rider_name="Arjun",
        amount=350,
        event_type="aqi",
        zone="Rohini",
    )
"""
import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger("notification_service")

# ── Configuration ─────────────────────────────────────────────────────────────
ONESIGNAL_APP_ID = os.environ.get("ONESIGNAL_APP_ID", "")
ONESIGNAL_REST_KEY = os.environ.get("ONESIGNAL_REST_KEY", "")
ONESIGNAL_API_URL = "https://onesignal.com/api/v1/notifications"

# ── Event type to human-readable label ────────────────────────────────────────
EVENT_LABELS = {
    "aqi": "Poor Air Quality",
    "heavy_rain": "Heavy Rainfall",
    "extreme_heat": "Extreme Heat",
    "cyclone": "Cyclonic Wind",
    "flood_alert": "Flood Alert",
    "curfew": "Curfew / Section 144",
}

TIER_LABELS = {
    "tier1": "Tier 1",
    "tier2": "Tier 2",
    "tier3": "Tier 3 (Extreme)",
}


async def send_payout_notification(
    player_id: str,
    rider_name: str,
    amount: float,
    event_type: str,
    zone: str,
    tier: str = "tier1",
    transaction_id: Optional[str] = None,
) -> dict:
    """
    Send a push notification when a payout is processed.

    Args:
        player_id: OneSignal player_id for the rider's device
        rider_name: Rider's display name
        amount: Payout amount in INR
        event_type: Trigger event type (aqi, heavy_rain, etc.)
        zone: Zone name (e.g., "Rohini")
        tier: Trigger tier
        transaction_id: Optional UPI transaction reference

    Returns:
        OneSignal API response dict, or error dict
    """
    event_label = EVENT_LABELS.get(event_type, event_type.replace("_", " ").title())
    tier_label = TIER_LABELS.get(tier, tier.upper())

    heading = f"₹{amount:.0f} Payout Processed! 🎉"
    content = (
        f"Hi {rider_name}, your {tier_label} payout of ₹{amount:.0f} for "
        f"{event_label} in {zone} has been credited to your UPI."
    )

    if transaction_id:
        content += f" Ref: {transaction_id}"

    return await _send_notification(
        player_id=player_id,
        heading=heading,
        content=content,
        data={
            "type": "payout_processed",
            "amount": amount,
            "event_type": event_type,
            "zone": zone,
            "tier": tier,
            "transaction_id": transaction_id,
        },
    )


async def send_trigger_notification(
    player_id: str,
    rider_name: str,
    event_type: str,
    zone: str,
    tier: str,
    metric_value: float,
    metric_unit: str,
    payout_amount: float,
) -> dict:
    """
    Send a push notification when a trigger fires in the rider's zone.

    Args:
        player_id: OneSignal player_id for the rider's device
        rider_name: Rider's display name
        event_type: Trigger event type
        zone: Zone name
        tier: Trigger tier
        metric_value: The actual metric value (e.g., AQI 420)
        metric_unit: Unit of measurement
        payout_amount: Expected payout amount

    Returns:
        OneSignal API response dict, or error dict
    """
    event_label = EVENT_LABELS.get(event_type, event_type.replace("_", " ").title())
    tier_label = TIER_LABELS.get(tier, tier.upper())

    heading = f"⚡ {event_label} Alert — {zone}"
    content = (
        f"Hi {rider_name}, {event_label} has crossed {tier_label} threshold "
        f"({metric_value} {metric_unit}) in {zone}. "
        f"Expected payout: ₹{payout_amount:.0f}. Stay safe!"
    )

    return await _send_notification(
        player_id=player_id,
        heading=heading,
        content=content,
        data={
            "type": "trigger_fired",
            "event_type": event_type,
            "zone": zone,
            "tier": tier,
            "metric_value": metric_value,
            "payout_amount": payout_amount,
        },
    )


async def send_bulk_trigger_notification(
    player_ids: list[str],
    event_type: str,
    zone: str,
    tier: str,
    metric_value: float,
    metric_unit: str,
    payout_amount: float,
) -> dict:
    """
    Send a push notification to multiple riders when a zone-wide trigger fires.
    Uses OneSignal's include_player_ids for batch delivery.
    """
    event_label = EVENT_LABELS.get(event_type, event_type.replace("_", " ").title())
    tier_label = TIER_LABELS.get(tier, tier.upper())

    heading = f"⚡ {tier_label} {event_label} — {zone}"
    content = (
        f"{event_label} has reached {metric_value} {metric_unit} in {zone}. "
        f"Your ₹{payout_amount:.0f} payout is being processed automatically."
    )

    return await _send_notification_bulk(
        player_ids=player_ids,
        heading=heading,
        content=content,
        data={
            "type": "trigger_fired_bulk",
            "event_type": event_type,
            "zone": zone,
            "tier": tier,
            "metric_value": metric_value,
            "payout_amount": payout_amount,
        },
    )


# ── Internal: OneSignal REST API call ─────────────────────────────────────────

async def _send_notification(
    player_id: str,
    heading: str,
    content: str,
    data: Optional[dict] = None,
) -> dict:
    """Send a push notification to a single device via OneSignal REST API."""
    if not ONESIGNAL_APP_ID or not ONESIGNAL_REST_KEY:
        logger.warning(
            f"OneSignal not configured — notification skipped | "
            f"heading={heading[:50]} | player_id={player_id}"
        )
        return {"status": "skipped", "reason": "ONESIGNAL credentials not set"}

    payload = {
        "app_id": ONESIGNAL_APP_ID,
        "include_player_ids": [player_id],
        "headings": {"en": heading},
        "contents": {"en": content},
        "data": data or {},
        "android_accent_color": "FF00C9B1",  # KavachAI teal
        "small_icon": "ic_notification",
        "priority": 10,
    }

    return await _post_onesignal(payload)


async def _send_notification_bulk(
    player_ids: list[str],
    heading: str,
    content: str,
    data: Optional[dict] = None,
) -> dict:
    """Send a push notification to multiple devices via OneSignal REST API."""
    if not ONESIGNAL_APP_ID or not ONESIGNAL_REST_KEY:
        logger.warning(
            f"OneSignal not configured — bulk notification skipped | "
            f"heading={heading[:50]} | recipients={len(player_ids)}"
        )
        return {"status": "skipped", "reason": "ONESIGNAL credentials not set"}

    # OneSignal limit: 2,000 player_ids per request
    # For KavachAI's ~1,000 riders per city, single batch is fine
    payload = {
        "app_id": ONESIGNAL_APP_ID,
        "include_player_ids": player_ids[:2000],
        "headings": {"en": heading},
        "contents": {"en": content},
        "data": data or {},
        "android_accent_color": "FF00C9B1",
        "small_icon": "ic_notification",
        "priority": 10,
    }

    return await _post_onesignal(payload)


async def _post_onesignal(payload: dict) -> dict:
    """Execute the POST request to OneSignal REST API."""
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Authorization": f"Basic {ONESIGNAL_REST_KEY}",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                ONESIGNAL_API_URL,
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            result = resp.json()

        notification_id = result.get("id", "unknown")
        recipients = result.get("recipients", 0)
        logger.info(
            f"OneSignal notification sent | id={notification_id} | recipients={recipients}"
        )
        return {"status": "sent", "notification_id": notification_id, "recipients": recipients}

    except httpx.HTTPStatusError as e:
        error_body = e.response.text[:500]
        logger.error(
            f"OneSignal API error | status={e.response.status_code} | body={error_body}"
        )
        return {"status": "error", "http_status": e.response.status_code, "detail": error_body}

    except httpx.RequestError as e:
        logger.error(f"OneSignal request failed | error={e}")
        return {"status": "error", "detail": str(e)}

    except Exception as e:
        logger.error(f"OneSignal unexpected error | error={e}")
        return {"status": "error", "detail": str(e)}
