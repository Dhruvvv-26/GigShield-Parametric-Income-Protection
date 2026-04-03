# KavachAI — Trigger Engine
# Build context: repo root (.)
FROM python:3.11-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app:/app/shared
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc libgeos-dev curl && rm -rf /var/lib/apt/lists/*

FROM base AS builder
COPY ./services/trigger_engine/requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

FROM base AS production
COPY --from=builder /root/.local /home/kavachai/.local
ENV PATH=/home/kavachai/.local/bin:$PATH
COPY ./services/trigger_engine /app/
COPY ./shared /app/shared/
RUN useradd -m -u 1001 kavachai && chown -R kavachai:kavachai /app
USER kavachai
EXPOSE 8003
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
    CMD curl -sf http://localhost:8003/health || exit 1
# workers=1 is MANDATORY — APScheduler is not multi-process safe
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8003", \
     "--workers", "1", "--log-level", "info", "--proxy-headers"]
