"""
GigShield — Payment Service
Responsibility:
  - Consume approved/soft_hold claims from Redpanda
  - Create Razorpay UPI payouts (test mode)
  - Enforce financial controls (daily cap, velocity limits)
  - Record payments and audit log
  - Emit payments.completed events
  - Dispatch FCM push notifications directly via firebase-admin (no Notification Service)
  - Store notifications in Redis for mobile app polling
Port: 8005
"""
import asyncio
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Gauge, Histogram, make_asgi_app

from shared.config import get_settings
from shared.database import close_db, init_db
from shared.logging_config import configure_logging, get_logger
from shared.messaging import GigShieldProducer
from shared.redis_client import close_redis, init_redis

from consumers.claims_consumer import ClaimsPaymentConsumer
from routes.payments import router as payments_router

configure_logging()
logger = get_logger(__name__)
settings = get_settings()

# ── Prometheus Metrics ────────────────────────────────────────────────────────

PAYMENTS_TOTAL = Counter(
    "payments_total", "Total payments processed", ["status", "mode"]
)
PAYOUT_AMOUNT = Histogram(
    "payout_amount_rupees", "Payout amounts in rupees",
    buckets=[50, 100, 150, 200, 300, 400, 500, 700, 1000, 1500, 2000],
)
LOSS_RATIO = Gauge(
    "loss_ratio_percent", "Current loss ratio percentage"
)

# ── Global Producer ───────────────────────────────────────────────────────────
producer = GigShieldProducer()
consumer: ClaimsPaymentConsumer | None = None
consumer_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global consumer, consumer_task

    logger.info("Payment Service starting up...")
    await init_db()
    await init_redis()
    await producer.start()

    # Start Redpanda consumer
    consumer = ClaimsPaymentConsumer(producer=producer)
    await consumer.start()
    consumer_task = asyncio.create_task(consumer.consume())
    logger.info("Claims payment consumer started ✓")

    yield

    logger.info("Payment Service shutting down...")
    if consumer:
        await consumer.stop()
    if consumer_task:
        consumer_task.cancel()
        try:
            await consumer_task
        except asyncio.CancelledError:
            pass
    await producer.stop()
    await close_db()
    await close_redis()
    logger.info("Payment Service shutdown complete ✓")


app = FastAPI(
    title="GigShield Payment Service",
    description="Razorpay UPI payouts, financial controls, loss ratio analytics",
    version="2.0.0",
    docs_url="/docs" if settings.env == "development" else None,
    redoc_url="/redoc" if settings.env == "development" else None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception", exc_info=exc, path=request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


app.include_router(payments_router, prefix="/api/v1/payments", tags=["Payments"])

metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


@app.get("/health", tags=["Infra"])
async def health_check():
    return {
        "status": "healthy",
        "service": "payment-service",
        "version": "2.0.0",
        "consumer_running": consumer_task is not None and not consumer_task.done(),
    }


@app.get("/ready", tags=["Infra"])
async def readiness_check():
    from shared.database import engine as db_engine
    from shared.redis_client import get_redis
    from sqlalchemy import text

    checks = {}
    try:
        async with db_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}"

    try:
        redis = await get_redis()
        await redis.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {e}"

    checks["redpanda_consumer"] = (
        "ok" if consumer_task and not consumer_task.done() else "not_running"
    )

    all_ok = all(v == "ok" for v in checks.values())
    return JSONResponse(
        status_code=200 if all_ok else 503,
        content={"status": "ready" if all_ok else "not_ready", "checks": checks},
    )


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.service_port,
        reload=False,
        log_level=settings.log_level.lower(),
        workers=1,
    )
