# ============================================================
# KavachAI — ML Service
# Multi-stage Docker build for production
# Build context: repo root (.)
# ============================================================

FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ── Dependencies stage ────────────────────────────────────────────────────────
FROM base AS builder

COPY ./services/ml_service/requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt \
    --extra-index-url https://download.pytorch.org/whl/cpu

# ── Production stage ──────────────────────────────────────────────────────────
FROM base AS production

# Copy installed packages from builder
COPY --from=builder /root/.local /home/kavachai/.local
ENV PATH=/home/kavachai/.local/bin:$PATH

# Copy application code
COPY ./services/ml_service /app/
COPY ./ml /app/ml/

# Non-root user for security
RUN useradd -m -u 1001 kavachai && chown -R kavachai:kavachai /app
USER kavachai

EXPOSE 8006

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
    CMD curl -sf http://localhost:8006/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8006", \
     "--workers", "1", "--log-level", "info", "--proxy-headers"]
