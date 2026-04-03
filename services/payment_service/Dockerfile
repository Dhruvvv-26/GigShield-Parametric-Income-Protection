# ============================================================
# GigShield — Payment Service
# Multi-stage Docker build for production
# Build context: repo root (.)
# ============================================================

FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app:/app/shared

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ── Dependencies stage ────────────────────────────────────────────────────────
FROM base AS builder

COPY ./services/payment_service/requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ── Production stage ──────────────────────────────────────────────────────────
FROM base AS production

COPY --from=builder /root/.local /home/gigshield/.local
ENV PATH=/home/gigshield/.local/bin:$PATH

# Copy application code (context = repo root)
COPY ./services/payment_service /app/
COPY ./shared /app/shared/

RUN useradd -m -u 1001 gigshield && chown -R gigshield:gigshield /app
USER gigshield

EXPOSE 8005

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
    CMD curl -sf http://localhost:8005/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8005", \
     "--workers", "1", "--log-level", "info", "--proxy-headers"]
