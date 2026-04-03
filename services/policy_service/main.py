"""
KavachAI — Policy Service
Responsibility: Policy creation, renewal, expiry, premium calculation.
Port: 8002
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

from routes.policies import router as policies_router
from routes.premium import router as premium_router

configure_logging()
logger = get_logger(__name__)
settings = get_settings()

# ── Prometheus Metrics ────────────────────────────────────────────────────────

REQUEST_COUNT = Counter(
    "policy_service_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
)
REQUEST_LATENCY = Histogram(
    "policy_service_request_latency_seconds",
    "HTTP request latency",
    ["method", "endpoint"],
)
POLICY_CREATED = Counter(
    "policies_created_total",
    "Total policies created",
    ["coverage_tier", "city"],
)
PREMIUM_CALCULATED = Counter(
    "premium_calculations_total",
    "Total premium calculations served",
    ["calculation_method"],
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Policy Service starting up...")
    await init_db()
    await init_redis()
    logger.info("Policy Service ready", port=settings.service_port)
    yield
    logger.info("Policy Service shutting down...")
    await close_db()
    await close_redis()


app = FastAPI(
    title="KavachAI Policy Service",
    description="Parametric insurance policy lifecycle management + premium calculation",
    version="1.0.0",
    docs_url="/docs" if settings.env == "development" else None,
    redoc_url="/redoc" if settings.env == "development" else None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH"],
    allow_headers=["*"],
)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    latency = time.perf_counter() - start
    REQUEST_COUNT.labels(request.method, request.url.path, response.status_code).inc()
    REQUEST_LATENCY.labels(request.method, request.url.path).observe(latency)
    return response


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception", exc_info=exc, path=request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


app.include_router(premium_router, prefix="/api/v1/premium", tags=["Premium"])
app.include_router(policies_router, prefix="/api/v1/policies", tags=["Policies"])

metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


@app.get("/health", tags=["Infra"])
async def health_check():
    return {"status": "healthy", "service": "policy-service", "version": "1.0.0"}


@app.get("/ready", tags=["Infra"])
async def readiness_check():
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
