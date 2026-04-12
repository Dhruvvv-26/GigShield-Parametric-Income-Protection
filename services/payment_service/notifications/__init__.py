"""
KavachAI — WhatsApp Notification Module (Twilio)
Sends payout notifications via WhatsApp using Twilio's API.

Graceful degradation: If TWILIO_ACCOUNT_SID is unset, sends are silently skipped
and logged. This ensures the payment pipeline never fails due to notifications.

Usage:
    from notifications.whatsapp import send_payout_notification
    await send_payout_notification(
        phone="+919876543210",
        rider_name="Arjun Kumar",
        payout_amount=350.00,
        event_type="aqi",
        zone_name="Rohini, Delhi",
        claim_id="CLM-2026-0041",
    )
"""
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# ── Twilio config — graceful if unset ─────────────────────────────────────────
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")

_client = None

if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
    try:
        from twilio.rest import Client
        _client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        logger.info("Twilio WhatsApp client initialized")
    except Exception as e:
        logger.warning(f"Twilio init failed (non-fatal): {e}")
else:
    logger.info("TWILIO_ACCOUNT_SID not set — WhatsApp notifications disabled (graceful)")


# ── Event type → emoji mapping ────────────────────────────────────────────────
EVENT_EMOJI = {
    "aqi": "🌫️",
    "heavy_rain": "🌧️",
    "extreme_heat": "🌡️",
    "cyclone": "🌀",
    "curfew": "🚫",
    "flood_alert": "🌊",
}


async def send_payout_notification(
    phone: str,
    rider_name: str,
    payout_amount: float,
    event_type: str,
    zone_name: str,
    claim_id: str,
    payout_mode: str = "lump_sum",
    installment: Optional[int] = None,
    total_installments: Optional[int] = None,
) -> bool:
    """
    Send a WhatsApp notification for payout.
    Returns True if sent successfully, False otherwise.
    Never raises — failures are logged and silently handled.
    """
    if not _client:
        logger.debug(f"WhatsApp skip (no client): {rider_name} / ₹{payout_amount}")
        return False

    if not phone or not phone.startswith("+"):
        logger.warning(f"Invalid phone for WhatsApp: {phone}")
        return False

    emoji = EVENT_EMOJI.get(event_type, "⚡")

    # Build message body
    if payout_mode == "drip_feed" and installment and total_installments:
        body = (
            f"{emoji} *KavachAI Payout — Installment {installment}/{total_installments}*\n\n"
            f"Hi {rider_name},\n"
            f"₹{payout_amount:.0f} has been sent to your UPI.\n\n"
            f"📍 Zone: {zone_name}\n"
            f"🏷️ Claim: {claim_id}\n"
            f"💧 Drip Mode: {installment}/{total_installments}\n\n"
            f"Powered by KavachAI ⚡"
        )
    else:
        body = (
            f"{emoji} *KavachAI Payout Confirmed*\n\n"
            f"Hi {rider_name},\n"
            f"₹{payout_amount:.0f} has been sent to your UPI.\n\n"
            f"📍 Zone: {zone_name}\n"
            f"🏷️ Claim: {claim_id}\n\n"
            f"Powered by KavachAI ⚡"
        )

    try:
        message = _client.messages.create(
            from_=TWILIO_WHATSAPP_FROM,
            body=body,
            to=f"whatsapp:{phone}",
        )
        logger.info(
            f"WhatsApp sent: sid={message.sid} to={phone} amount=₹{payout_amount}"
        )
        return True

    except Exception as e:
        logger.warning(f"WhatsApp send failed (non-fatal): {e}")
        return False


async def send_drip_completion_notification(
    phone: str,
    rider_name: str,
    total_amount: float,
    total_installments: int,
    zone_name: str,
    claim_id: str,
) -> bool:
    """
    Send a WhatsApp notification when all drip-feed installments are complete.
    """
    if not _client:
        return False

    if not phone or not phone.startswith("+"):
        return False

    body = (
        f"✅ *KavachAI — Drip Payout Complete*\n\n"
        f"Hi {rider_name},\n"
        f"All {total_installments} installments totalling ₹{total_amount:.0f} have been sent.\n\n"
        f"📍 Zone: {zone_name}\n"
        f"🏷️ Claim: {claim_id}\n\n"
        f"Thank you for using KavachAI ⚡"
    )

    try:
        message = _client.messages.create(
            from_=TWILIO_WHATSAPP_FROM,
            body=body,
            to=f"whatsapp:{phone}",
        )
        logger.info(f"WhatsApp drip-complete sent: sid={message.sid} to={phone}")
        return True
    except Exception as e:
        logger.warning(f"WhatsApp drip-complete failed (non-fatal): {e}")
        return False
