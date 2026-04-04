"""
Payment Service — REST API Routes
Endpoints:
  GET  /api/v1/payments/{payment_id}          — single payment detail
  GET  /api/v1/payments/worker/{worker_id}     — payment history for worker
  GET  /api/v1/payments/summary                — loss ratio + financial KPIs
  POST /api/v1/payments/webhook                — Razorpay webhook handler
"""
import json
import logging
from datetime import datetime, timezone, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from models.payment import Payment, PaymentAuditLog, Claim, Policy
from models.schemas import (
    PaymentListResponse,
    PaymentResponse,
    PaymentSummaryResponse,
    RazorpayWebhookPayload,
)
from shared.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


# ── IMPORTANT: /summary and /worker/{id} MUST be declared before /{payment_id}
# FastAPI matches routes in declaration order. A catch-all UUID path param
# would swallow "summary" as a (failing) UUID parse attempt otherwise.


@router.get(
    "/summary",
    response_model=PaymentSummaryResponse,
    summary="Financial summary — loss ratio & KPIs",
)
async def get_payment_summary(
    db: AsyncSession = Depends(get_db),
):
    """
    Returns the key financial metrics for admin dashboard.
    Loss ratio = (total payouts / total premiums) × 100
    Target: 65% loss ratio for actuarial viability.
    """
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)

    # Total premiums this week (from active policies)
    premium_result = await db.execute(
        select(func.sum(Policy.weekly_premium)).where(
            Policy.status == "active",
        )
    )
    total_premiums = float(premium_result.scalar() or 0)

    # Total payouts this week
    payout_result = await db.execute(
        select(func.sum(Payment.amount)).where(
            and_(
                Payment.status.in_(["completed", "processing"]),
                Payment.initiated_at >= week_ago,
            )
        )
    )
    total_payouts = float(payout_result.scalar() or 0)

    # Loss ratio
    loss_ratio = (total_payouts / total_premiums * 100) if total_premiums > 0 else 0.0

    # Active policies
    active_result = await db.execute(
        select(func.count(Policy.id)).where(Policy.status == "active")
    )
    active_policies = active_result.scalar() or 0

    # Claims this week
    claims_result = await db.execute(
        select(func.count(Claim.id)).where(Claim.created_at >= week_ago)
    )
    claims_this_week = claims_result.scalar() or 0

    # Payment status counts
    completed_result = await db.execute(
        select(func.count(Payment.id)).where(
            and_(Payment.status == "completed", Payment.initiated_at >= week_ago)
        )
    )
    payments_completed = completed_result.scalar() or 0

    pending_result = await db.execute(
        select(func.count(Payment.id)).where(
            and_(Payment.status.in_(["pending", "processing"]), Payment.initiated_at >= week_ago)
        )
    )
    payments_pending = pending_result.scalar() or 0

    failed_result = await db.execute(
        select(func.count(Payment.id)).where(
            and_(Payment.status == "failed", Payment.initiated_at >= week_ago)
        )
    )
    payments_failed = failed_result.scalar() or 0

    # Average payout
    avg_result = await db.execute(
        select(func.avg(Payment.amount)).where(
            and_(
                Payment.status.in_(["completed", "processing"]),
                Payment.initiated_at >= week_ago,
            )
        )
    )
    avg_payout = float(avg_result.scalar() or 0)

    # Daily volume (today)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    daily_result = await db.execute(
        select(func.sum(Payment.amount)).where(
            and_(
                Payment.status.in_(["completed", "processing"]),
                Payment.initiated_at >= today_start,
            )
        )
    )
    daily_volume = float(daily_result.scalar() or 0)

    return PaymentSummaryResponse(
        total_premiums_this_week=round(total_premiums, 2),
        total_payouts_this_week=round(total_payouts, 2),
        loss_ratio_percent=round(loss_ratio, 2),
        active_policies=active_policies,
        claims_this_week=claims_this_week,
        payments_completed=payments_completed,
        payments_pending=payments_pending,
        payments_failed=payments_failed,
        avg_payout_amount=round(avg_payout, 2),
        daily_payout_volume=round(daily_volume, 2),
    )


@router.get(
    "/worker/{worker_id}",
    response_model=PaymentListResponse,
    summary="Get payment history for a worker",
)
async def get_worker_payments(
    worker_id: UUID,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve all payments for a specific worker."""
    result = await db.execute(
        select(Payment)
        .where(Payment.worker_id == worker_id)
        .order_by(desc(Payment.initiated_at))
        .limit(limit)
    )
    payments = result.scalars().all()

    count_result = await db.execute(
        select(func.count(Payment.id)).where(Payment.worker_id == worker_id)
    )
    total = count_result.scalar() or 0

    return PaymentListResponse(
        payments=[
            PaymentResponse(
                payment_id=p.id,
                claim_id=p.claim_id,
                worker_id=p.worker_id,
                amount=float(p.amount),
                status=p.status,
                razorpay_payout_id=p.razorpay_payout_id,
                upi_id_masked=p.upi_id_masked,
                initiated_at=p.initiated_at,
                completed_at=p.completed_at,
                failed_at=p.failed_at,
                failure_reason=p.failure_reason,
            )
            for p in payments
        ],
        total=total,
        worker_id=str(worker_id),
    )


@router.get(
    "/{payment_id}",
    response_model=PaymentResponse,
    summary="Get payment by ID",
)
async def get_payment(
    payment_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve a single payment record."""
    result = await db.execute(
        select(Payment).where(Payment.id == payment_id)
    )
    payment = result.scalar_one_or_none()
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Payment {payment_id} not found",
        )

    return PaymentResponse(
        payment_id=payment.id,
        claim_id=payment.claim_id,
        worker_id=payment.worker_id,
        amount=float(payment.amount),
        status=payment.status,
        razorpay_payout_id=payment.razorpay_payout_id,
        upi_id_masked=payment.upi_id_masked,
        initiated_at=payment.initiated_at,
        completed_at=payment.completed_at,
        failed_at=payment.failed_at,
        failure_reason=payment.failure_reason,
    )


@router.post(
    "/webhook",
    status_code=status.HTTP_200_OK,
    summary="Razorpay webhook handler",
)
async def razorpay_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Handle Razorpay webhook events:
    - payout.processed → update payment status to COMPLETED
    - payout.failed → update payment status to FAILED
    """
    body = await request.body()

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    event = payload.get("event", "")
    payout_entity = payload.get("payload", {}).get("payout", {}).get("entity", {})
    payout_id = payout_entity.get("id")

    if not payout_id:
        logger.warning("Webhook event without payout_id", extra={"event": event})
        return {"status": "ignored"}

    # Find payment by Razorpay payout ID
    result = await db.execute(
        select(Payment).where(Payment.razorpay_payout_id == payout_id)
    )
    payment = result.scalar_one_or_none()

    if not payment:
        logger.warning(
            "Webhook for unknown payout",
            extra={"payout_id": payout_id, "event": event},
        )
        return {"status": "not_found"}

    if event == "payout.processed":
        old_status = payment.status
        payment.status = "completed"
        payment.completed_at = datetime.now(timezone.utc)

        audit = PaymentAuditLog(
            payment_id=payment.id,
            old_status=old_status,
            new_status="completed",
            changed_by="razorpay-webhook",
            note=f"Payout processed: {payout_id}",
        )
        db.add(audit)

        logger.info(
            "Payout completed via webhook",
            extra={"payment_id": str(payment.id), "payout_id": payout_id},
        )

    elif event == "payout.failed":
        old_status = payment.status
        payment.status = "failed"
        payment.failed_at = datetime.now(timezone.utc)
        payment.failure_reason = payout_entity.get("failure_reason", "Unknown")

        audit = PaymentAuditLog(
            payment_id=payment.id,
            old_status=old_status,
            new_status="failed",
            changed_by="razorpay-webhook",
            note=f"Payout failed: {payout_entity.get('failure_reason', 'Unknown')}",
        )
        db.add(audit)

        logger.error(
            "Payout failed via webhook",
            extra={
                "payment_id": str(payment.id),
                "payout_id": payout_id,
                "reason": payout_entity.get("failure_reason"),
            },
        )

    await db.flush()
    return {"status": "ok", "event": event, "payout_id": payout_id}
