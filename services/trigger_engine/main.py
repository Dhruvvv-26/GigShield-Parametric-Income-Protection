"""
KavachAI — Trigger Engine
Responsibility:
  - Poll OpenWeatherMap every 15 minutes
  - Poll CPCB AQI every 60 minutes
  - Parse NDMA/IMD RSS feeds every 5 minutes
  - Evaluate threshold rules against PostGIS zone polygons
  - Emit payout trigger events to Redpanda: processed.trigger.events
  - Expose POST /api/v1/trigger/test for demo and smoke-testing

Port: 8003
"""
import asyncio
from contextlib import asynccontextmanager

import uvicorn
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Gauge, make_asgi_app

from shared.config import get_settings
from shared.database import close_db, init_db
from shared.logging_config import configure_logging, get_logger
from shared.messaging import KavachAIProducer
from shared.redis_client import close_redis, init_redis

from schedulers.owm_poller import OpenWeatherMapPoller
from schedulers.cpcb_poller import CPCBPoller
from schedulers.ndma_poller import NDMAPoller
from routes.trigger_test import router as trigger_test_router
from routes.trigger_status import router as trigger_status_router

configure_logging()
logger = get_logger(__name__)
settings = get_settings()

# ── Prometheus Metrics ────────────────────────────────────────────────────────

TRIGGER_EVENTS_TOTAL = Counter(
    "trigger_events_total",
    "Total trigger events fired",
    ["event_type", "tier", "city"],
)
ACTIVE_DISRUPTION_ZONES = Gauge(
    "active_disruption_zones",
    "Current number of zones with active disruption events",
    ["event_type"],
)
POLL_ERRORS_TOTAL = Counter(
    "trigger_engine_poll_errors_total",
    "API poll errors",
    ["source"],
)
LAST_POLL_TIMESTAMP = Gauge(
    "trigger_engine_last_poll_timestamp",
    "Unix timestamp of last successful poll",
    ["source"],
)

# ── Global Producer ───────────────────────────────────────────────────────────
# Shared across all pollers — single producer instance per service
producer = KavachAIProducer()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ───────────────────────────────────────────────────────────────
    logger.info("Trigger Engine starting up...")
    await init_db()
    await init_redis()
    await producer.start()

    # ── APScheduler setup ─────────────────────────────────────────────────────
    scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")
    app.state.scheduler = scheduler

    owm_poller   = OpenWeatherMapPoller(producer=producer)
    cpcb_poller  = CPCBPoller(producer=producer)
    ndma_poller  = NDMAPoller(producer=producer)

    # OpenWeatherMap: every 15 minutes (96 calls/day — well within 1,000/day free limit)
    scheduler.add_job(
        owm_poller.run,
        trigger=IntervalTrigger(minutes=settings.trigger_poll_interval_minutes),
        id="owm_poll",
        name="OpenWeatherMap Poller",
        replace_existing=True,
        max_instances=1,      # Prevent overlapping runs
    )

    # CPCB AQI: every 60 minutes (AQI readings update hourly max)
    scheduler.add_job(
        cpcb_poller.run,
        trigger=IntervalTrigger(minutes=60),
        id="cpcb_poll",
        name="CPCB AQI Poller",
        replace_existing=True,
        max_instances=1,
    )

    # NDMA/IMD RSS: every 5 minutes (RSS feeds update frequently during events)
    scheduler.add_job(
        ndma_poller.run,
        trigger=IntervalTrigger(minutes=5),
        id="ndma_poll",
        name="NDMA/IMD RSS Poller",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.start()
    logger.info(
        "APScheduler started",
        jobs=len(scheduler.get_jobs()),
        owm_interval_min=settings.trigger_poll_interval_minutes,
    )

    # ── Run first poll immediately on startup ─────────────────────────────────
    asyncio.create_task(owm_poller.run())
    asyncio.create_task(cpcb_poller.run())

    yield

    # ── Shutdown ──────────────────────────────────────────────────────────────
    logger.info("Trigger Engine shutting down...")
    scheduler.shutdown(wait=False)
    await producer.stop()
    await close_db()
    await close_redis()
    logger.info("Trigger Engine shutdown complete ✓")


app = FastAPI(
    title="KavachAI Trigger Engine",
    description="Parametric trigger detection: OWM + CPCB + NDMA → Redpanda",
    version="1.0.0",
    docs_url="/docs" if settings.env == "development" else None,
    redoc_url="/redoc" if settings.env == "development" else None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception", exc_info=exc, path=request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


app.include_router(trigger_test_router, prefix="/api/v1/trigger", tags=["Trigger"])
app.include_router(trigger_status_router, prefix="/api/v1/trigger", tags=["Trigger"])

metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


@app.get("/health", tags=["Infra"])
async def health_check():
    scheduler = getattr(app.state, "scheduler", None)
    return {
        "status": "healthy",
        "service": "trigger-engine",
        "scheduler_running": scheduler.running if scheduler else False,
        "scheduled_jobs": len(scheduler.get_jobs()) if scheduler else 0,
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

    try:
        # Verify Redpanda connectivity
        checks["redpanda"] = "ok" if producer._producer else "not_started"
    except Exception as e:
        checks["redpanda"] = f"error: {e}"

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
        reload=False,   # APScheduler + reload = bad interaction
        log_level=settings.log_level.lower(),
        workers=1,      # MUST be 1 — APScheduler is not multi-process safe
    )
