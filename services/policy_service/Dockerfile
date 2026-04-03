# KavachAI — Policy Service
# Build context: repo root (.)
FROM python:3.11-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app:/app/shared
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc libgeos-dev curl && rm -rf /var/lib/apt/lists/*

FROM base AS builder
COPY ./services/policy_service/requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

FROM base AS production
COPY --from=builder /root/.local /home/kavachai/.local
ENV PATH=/home/kavachai/.local/bin:$PATH
COPY ./services/policy_service /app/
COPY ./shared /app/shared/
RUN useradd -m -u 1001 kavachai && chown -R kavachai:kavachai /app
USER kavachai
EXPOSE 8002
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
    CMD curl -sf http://localhost:8002/health || exit 1
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002", \
     "--workers", "2", "--log-level", "info", "--proxy-headers"]
