"""
KavachAI — Shared Redis Client
Used for: premium caching, fraud scores, session tokens,
deduplication locks, rate limiting counters.
"""
import logging
from typing import Any

import redis.asyncio as aioredis
from redis.asyncio import Redis

from shared.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_redis_client: Redis | None = None


async def get_redis() -> Redis:
    """
    FastAPI dependency / module-level accessor for the Redis client.
    Raises if Redis is unavailable.
    """
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
            health_check_interval=30,
        )
    return _redis_client


async def init_redis() -> None:
    client = await get_redis()
    await client.ping()
    logger.info("Redis connection verified ✓")


async def close_redis() -> None:
    global _redis_client
    if _redis_client:
        await _redis_client.aclose()
        _redis_client = None
    logger.info("Redis connection closed ✓")


# ── Helper utilities ──────────────────────────────────────────────────────────

async def cache_set(key: str, value: Any, ttl: int | None = None) -> None:
    client = await get_redis()
    ttl = ttl or settings.redis_cache_ttl_seconds
    await client.setex(key, ttl, str(value))


async def cache_get(key: str) -> str | None:
    client = await get_redis()
    return await client.get(key)


async def cache_delete(key: str) -> None:
    client = await get_redis()
    await client.delete(key)


async def acquire_lock(lock_key: str, ttl_seconds: int = 30) -> bool:
    """
    Distributed lock using Redis SETNX.
    Returns True if lock acquired, False if already held.
    Used for deduplication in Claims Service (Redpanda consumer).
    """
    client = await get_redis()
    result = await client.set(
        f"lock:{lock_key}",
        "1",
        nx=True,
        ex=ttl_seconds,
    )
    return result is True


async def release_lock(lock_key: str) -> None:
    client = await get_redis()
    await client.delete(f"lock:{lock_key}")
