"""
GigShield — Worker Service
Responsibility: Rider registration, profile management, GPS zone assignment.
Port: 8001
"""
import time
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram, make_asgi_app

from shared.config import get_settings
from shared.database import close_db, init_db
from shared.logging_config import configure_logging, get_logger
from shared.redis_client import close_redis, init_redis

from routes.registration import router as registration_router
from routes.zones import router as zones_router
from routes.workers import router as workers_router

configure_logging()
logger = get_logger(__name__)
settings = get_settings()

# ── Prometheus Metrics ────────────────────────────────────────────────────────

REQUEST_COUNT = Counter(
    "worker_service_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
)
REQUEST_LATENCY = Histogram(
    "worker_service_request_latency_seconds",
    "HTTP request latency",
    ["method", "endpoint"],
)
REGISTRATION_COUNT = Counter(
    "worker_registrations_total",
    "Total worker registrations",
    ["platform", "city"],
)


# ── App Lifecycle ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──
    logger.info("Worker Service starting up...")
    await init_db()
    await init_redis()
    logger.info(
        "Worker Service ready",
        port=settings.service_port,
        env=settings.env,
    )
    yield
    # ── Shutdown ──
    logger.info("Worker Service shutting down...")
    await close_db()
    await close_redis()
    logger.info("Worker Service shutdown complete ✓")


# ── FastAPI App ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="GigShield Worker Service",
    description="Q-Commerce rider registration and zone assignment",
    version="1.0.0",
    docs_url="/docs" if settings.env == "development" else None,
    redoc_url="/redoc" if settings.env == "development" else None,
    lifespan=lifespan,
)

# ── Middleware ────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    """Log every request with method, path, status, and latency."""
    start = time.perf_counter()
    response = await call_next(request)
    latency = time.perf_counter() - start

    logger.info(
        "HTTP request",
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        latency_ms=round(latency * 1000, 2),
    )

    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path,
        status_code=response.status_code,
    ).inc()
    REQUEST_LATENCY.labels(
        method=request.method,
        endpoint=request.url.path,
    ).observe(latency)

    return response


# ── Exception Handlers ────────────────────────────────────────────────────────

@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(
        status_code=422,
        content={"detail": str(exc), "type": "validation_error"},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception", exc_info=exc, path=request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# ── Routes ────────────────────────────────────────────────────────────────────

app.include_router(registration_router, prefix="/api/v1/riders", tags=["Registration"])
app.include_router(workers_router, prefix="/api/v1/riders", tags=["Workers"])
app.include_router(zones_router, prefix="/api/v1/zones", tags=["Zones"])

# Prometheus metrics endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


@app.get("/health", tags=["Infra"])
async def health_check():
    return {
        "status": "healthy",
        "service": settings.service_name,
        "version": "1.0.0",
        "env": settings.env,
    }


@app.get("/ready", tags=["Infra"])
async def readiness_check():
    """Deep health check — verifies DB and Redis connectivity."""
    from shared.database import engine
    from shared.redis_client import get_redis
    from sqlalchemy import text

    checks = {}
    try:
        async with engine.connect() as conn:
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
        reload=settings.env == "development",
        log_level=settings.log_level.lower(),
        workers=1,
    )
