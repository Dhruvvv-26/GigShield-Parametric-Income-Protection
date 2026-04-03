"""
Payment Service — Claims Consumer (with inline FCM push)
Subscribes to: claims.approved, claims.soft_hold
Consumer group: payment_consumer

On each approved/soft_hold claim:
1. Redis SETNX idempotency check: "payment:{claim_id}"
2. Financial controls: daily cap ₹2,000, velocity limit 3/7 days
3. Create payment record (status=PENDING)
4. Call Razorpay test mode payout API
5. Update payment status → PROCESSING
6. Write to payment_audit_log (append-only)
7. Emit to payments.completed topic
8. Send FCM push notification to rider's device (firebase-admin direct)
9. Store notification in Redis for mobile app polling
"""
import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from models.payment import Payment, PaymentAuditLog, Claim, Worker
from services.razorpay_client import RazorpayPayoutClient
from shared.config import get_settings
from shared.database import get_db_context
from shared.messaging import GigShieldConsumer, GigShieldProducer
from shared.redis_client import get_redis

logger = logging.getLogger(__name__)
settings = get_settings()
razorpay = RazorpayPayoutClient()

# ── Firebase Admin SDK (direct, no HTTP call to Notification Service) ────────

_firebase_initialized = False

def _init_firebase():
    """Initialize Firebase Admin SDK once."""
    global _firebase_initialized
    if _firebase_initialized:
        return True
        
    if not settings.fcm_dispatch_enabled:
        logger.info("FCM disabled via config (fcm_dispatch_enabled=False)")
        return False

    sa_path = getattr(settings, "firebase_service_account_path", "")
    if not sa_path:
        # Fallback to older setting name
        sa_path = getattr(settings, "firebase_credentials", "")
        
    if not sa_path:
        logger.info("FCM disabled: FIREBASE_SERVICE_ACCOUNT_PATH not set")
        return False
        
    try:
        import firebase_admin
        from firebase_admin import credentials
        if not firebase_admin._apps:
            cred = credentials.Certificate(sa_path)
            firebase_admin.initialize_app(cred)
        _firebase_initialized = True
        logger.info("Firebase Admin SDK initialized ✓")
        return True
    except Exception as e:
        logger.warning(f"Firebase init failed (FCM push disabled): {e}")
        return False


def _build_fcm_body(status: str, amount: float, held_amount: float, event_type: str, city: str) -> dict:
    """
    Build FCM notification title + body per spec.
    Three templates:
      APPROVED:  "₹{amount} credited to your UPI. Disruption cover applied."
      SOFT_HOLD: "₹{amount} credited. ₹{held_amount} under 2-hour verification."
      BLOCKED:   "Your claim is under review. Our team will contact you within 24 hours."
    """
    if status in ("completed", "auto_approved", "approved"):
        title = "GigShield — Payout Confirmed ✓"
        body = f"₹{amount:.0f} credited to your UPI. Disruption cover applied."
    elif status == "soft_hold":
        title = "GigShield — Partial Payout"
        body = f"₹{amount:.0f} credited. ₹{held_amount:.0f} under 2-hour verification."
    else:
        title = "GigShield — Claim Update"
        body = "Your claim is under review. Our team will contact you within 24 hours."
    return {"title": title, "body": body}


async def _dispatch_fcm_and_store(worker_id: str, payment_event: dict, redis) -> str:
    """
    Send FCM push notification to rider's device AND store in Redis.
    FCM failure is logged but NEVER fails the payout — payout is the critical path.
    Returns notification_id.
    """
    amount = float(payment_event.get("amount", 0))
    status = payment_event.get("status", "completed")
    event_type = payment_event.get("event_type", "disruption")
    city = payment_event.get("city", "your zone")
    held_amount = float(payment_event.get("held_amount", 0))

    fcm_body = _build_fcm_body(status, amount, held_amount, event_type, city)
    title = fcm_body["title"]
    body = fcm_body["body"]

    notification_id = str(uuid.uuid4())
    notif_payload = {
        "notification_id": notification_id,
        "worker_id": worker_id,
        "title": title,
        "body": body,
        "data": {
            "type": "payout_confirmed" if status in ("completed", "auto_approved", "approved") else "claim_update",
            "amount": str(amount),
            "event_type": event_type,
        },
        "payment_id": payment_event.get("payment_id"),
        "payout_id": payment_event.get("payout_id"),
        "amount": amount,
        "event_type": event_type,
        "zone_code": payment_event.get("zone_code"),
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "read": False,
    }

    # Always store in Redis for mobile app polling
    await redis.lpush(f"notifications:{worker_id}", json.dumps(notif_payload))
    await redis.ltrim(f"notifications:{worker_id}", 0, 49)
    await redis.lpush("notifications:all", json.dumps(notif_payload))
    await redis.ltrim("notifications:all", 0, 199)

    # Send real FCM push if enabled and configured
    if settings.fcm_dispatch_enabled and _init_firebase():
        try:
            fcm_token = await redis.get(f"fcm_token:{worker_id}")
            if fcm_token:
                if isinstance(fcm_token, bytes):
                    fcm_token = fcm_token.decode("utf-8")
                from firebase_admin import messaging
                message = messaging.Message(
                    notification=messaging.Notification(title=title, body=body),
                    data={
                        "type": "payout_confirmed",
                        "amount": str(amount),
                        "event_type": event_type,
                        "notification_id": notification_id,
                    },
                    token=fcm_token,
                )
                response = messaging.send(message)
                logger.info(f"📱 FCM push sent: {response}")
            else:
                logger.debug(f"No FCM token registered for worker {worker_id[:8]}…")
        except Exception as e:
            # FCM failure is best-effort — NEVER fail the payout
            logger.warning(f"FCM push failed (notification stored in Redis): {e}")
    elif not settings.fcm_dispatch_enabled:
        logger.info(f"📱 FCM disabled (fcm_dispatch_enabled=False). Payload: {title} | {body}")
    else:
        logger.info(f"📱 Push stored in Redis only (Firebase not configured): {title}")

    return notification_id


# ── Financial Control Constants ──────────────────────────────────────────────

DAILY_PAYOUT_CAP_PER_WORKER = 2000.0   # ₹2,000 per worker per day
MAX_PAYOUTS_PER_7_DAYS = 3             # Velocity limit


class ClaimsPaymentConsumer(GigShieldConsumer):
    """
    Consumes approved and soft_hold claims from Redpanda.
    Creates payments via Razorpay, emits completion events,
    and dispatches FCM push notifications directly (no Notification Service).
    """

    def __init__(self, producer: GigShieldProducer):
        super().__init__(
            topics=[settings.topic_claims_approved, "claims.soft_hold"],
            group_id="payment_consumer",
        )
        self._producer = producer

    async def process_message(self, message: dict) -> None:
        """Process a single claim event and create payment."""
        payload = message.get("payload", message)
        claim_id = payload.get("claim_id")
        worker_id = payload.get("worker_id")
        payout_amount = float(payload.get("payout_amount", 0))
        zone_code = payload.get("zone_code", "unknown")
        city = payload.get("city", "unknown")
        event_type = payload.get("event_type", "unknown")
        tier = payload.get("tier", "tier1")
        status = payload.get("status", "auto_approved")
        worker_upi_id = payload.get("worker_upi_id")
        worker_name = payload.get("worker_name", "Rider")

        if not claim_id or not worker_id:
            logger.error("Claim event missing required fields", extra={"payload": payload})
            return

        logger.info(
            "Processing claim for payment",
            extra={
                "claim_id": claim_id,
                "worker_id": worker_id,
                "amount": payout_amount,
                "status": status,
            },
        )

        redis = await get_redis()

        # ── Idempotency Check ────────────────────────────────────────────────
        idem_key = f"payment:{claim_id}"
        lock_acquired = await redis.set(
            f"lock:{idem_key}", "1", nx=True, ex=86400  # 24-hour TTL
        )
        if not lock_acquired:
            logger.info(
                "Duplicate payment prevented by idempotency key",
                extra={"claim_id": claim_id},
            )
            return

        async with get_db_context() as db:
            # ── Financial Controls ───────────────────────────────────────────
            worker_uuid = uuid.UUID(worker_id)

            # Check 1: Daily payout cap
            today_start = datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            daily_key = f"daily_payout:{worker_id}:{today_start.date().isoformat()}"
            daily_total_str = await redis.get(daily_key)
            daily_total = float(daily_total_str) if daily_total_str else 0.0

            if daily_total + payout_amount > DAILY_PAYOUT_CAP_PER_WORKER:
                logger.warning(
                    "Daily payout cap exceeded",
                    extra={
                        "worker_id": worker_id,
                        "daily_total": daily_total,
                        "amount": payout_amount,
                        "cap": DAILY_PAYOUT_CAP_PER_WORKER,
                    },
                )
                # Still create payment but mark as pending review
                payout_amount = min(payout_amount, DAILY_PAYOUT_CAP_PER_WORKER - daily_total)
                if payout_amount <= 0:
                    logger.info("Worker hit daily cap, skipping payment")
                    return

            # Check 2: Velocity limit (3 payouts in 7 days)
            velocity_key = f"payout_history:{worker_id}"
            now_ts = datetime.now(timezone.utc).timestamp()
            seven_days_ago_ts = (datetime.now(timezone.utc) - timedelta(days=7)).timestamp()

            # Clean old entries from sorted set
            await redis.zremrangebyscore(velocity_key, "-inf", str(seven_days_ago_ts))
            recent_payouts = await redis.zcard(velocity_key)

            if recent_payouts >= MAX_PAYOUTS_PER_7_DAYS:
                logger.warning(
                    "Velocity limit reached",
                    extra={
                        "worker_id": worker_id,
                        "recent_payouts": recent_payouts,
                        "limit": MAX_PAYOUTS_PER_7_DAYS,
                    },
                )
                return

            # ── Create Payment Record ────────────────────────────────────────
            # Look up worker UPI if not provided
            if not worker_upi_id:
                worker_result = await db.execute(
                    select(Worker).where(Worker.id == worker_uuid)
                )
                worker = worker_result.scalar_one_or_none()
                if worker and worker.upi_id:
                    worker_upi_id = worker.upi_id
                    worker_name = worker.full_name or worker_name
                else:
                    worker_upi_id = "demo@upi"  # Fallback for demo

            payment = Payment(
                claim_id=uuid.UUID(claim_id),
                worker_id=worker_uuid,
                amount=payout_amount,
                status="pending",
                upi_id_masked=razorpay._mask_upi(worker_upi_id),
                initiated_at=datetime.now(timezone.utc),
            )
            db.add(payment)
            await db.flush()

            # Audit log: PENDING
            audit_pending = PaymentAuditLog(
                payment_id=payment.id,
                old_status=None,
                new_status="pending",
                changed_by="payment-service",
                note=f"Payment created for claim {claim_id}",
            )
            db.add(audit_pending)

            # ── Razorpay Payout ──────────────────────────────────────────────
            narration = f"GigShield {event_type} payout — {zone_code}"
            payout_result = await razorpay.create_payout(
                worker_upi_id=worker_upi_id,
                amount_rupees=payout_amount,
                narration=narration,
                claim_id=claim_id,
                worker_name=worker_name,
            )

            payout_id = payout_result.get("payout_id")
            payout_status = payout_result.get("status", "failed")

            if payout_id:
                payment.razorpay_payout_id = payout_id
                payment.status = "processing"

                # Audit log: PROCESSING
                audit_processing = PaymentAuditLog(
                    payment_id=payment.id,
                    old_status="pending",
                    new_status="processing",
                    changed_by="payment-service",
                    note=f"Razorpay payout initiated: {payout_id}",
                )
                db.add(audit_processing)

                # Update daily payout counter
                await redis.incrbyfloat(daily_key, payout_amount)
                await redis.expire(daily_key, 86400)

                # Add to velocity sorted set
                await redis.zadd(velocity_key, {str(payment.id): now_ts})
                await redis.expire(velocity_key, 7 * 86400)

                # In test mode, auto-complete the payment after a short delay
                if payout_result.get("mode") == "test":
                    payment.status = "completed"
                    payment.completed_at = datetime.now(timezone.utc)

                    # Update claim status to completed
                    claim_result = await db.execute(
                        select(Claim).where(Claim.id == uuid.UUID(claim_id))
                    )
                    claim = claim_result.scalar_one_or_none()
                    if claim:
                        claim.status = "completed"
                        claim.completed_at = datetime.now(timezone.utc)

                    audit_completed = PaymentAuditLog(
                        payment_id=payment.id,
                        old_status="processing",
                        new_status="completed",
                        changed_by="payment-service",
                        note=f"Test mode auto-complete. Razorpay: {payout_id}",
                    )
                    db.add(audit_completed)

                # ── Emit payment event ───────────────────────────────────────
                payment_event = {
                    "payment_id": str(payment.id),
                    "claim_id": claim_id,
                    "worker_id": worker_id,
                    "amount": float(payout_amount),
                    "payout_id": payout_id,
                    "status": payment.status,
                    "event_type": event_type,
                    "zone_code": zone_code,
                    "city": city,
                    "worker_name": worker_name,
                    "upi_id_masked": razorpay._mask_upi(worker_upi_id),
                    "held_amount": 0,
                }

                # Calculate held_amount for soft_hold
                if status == "soft_hold":
                    payment_event["held_amount"] = float(payout_amount)

                await self._producer.publish(
                    topic="payments.completed",
                    event_type="payment.completed",
                    payload=payment_event,
                    source_service="payment-service",
                    key=worker_id,
                )

                logger.info(
                    "Payment completed",
                    extra={
                        "payment_id": str(payment.id),
                        "claim_id": claim_id,
                        "payout_id": payout_id,
                        "amount": payout_amount,
                        "mode": payout_result.get("mode"),
                    },
                )

                # ── FCM Push + Redis Notification (direct, no HTTP) ──────────
                try:
                    notif_id = await _dispatch_fcm_and_store(
                        worker_id=worker_id,
                        payment_event=payment_event,
                        redis=redis,
                    )
                    logger.info(
                        "Notification dispatched",
                        extra={"notification_id": notif_id, "worker_id": worker_id[:8]},
                    )
                except Exception as notif_err:
                    # FCM failure NEVER fails the payout — best-effort only
                    logger.warning(f"Notification dispatch failed (non-fatal): {notif_err}")
            else:
                payment.status = "failed"
                payment.failure_reason = payout_result.get("error", "Unknown error")
                payment.failed_at = datetime.now(timezone.utc)

                audit_failed = PaymentAuditLog(
                    payment_id=payment.id,
                    old_status="pending",
                    new_status="failed",
                    changed_by="payment-service",
                    note=f"Razorpay payout failed: {payout_result.get('error', 'Unknown')}",
                )
                db.add(audit_failed)

                logger.error(
                    "Payment failed",
                    extra={
                        "payment_id": str(payment.id),
                        "claim_id": claim_id,
                        "error": payout_result.get("error"),
                    },
                )

            await db.flush()
