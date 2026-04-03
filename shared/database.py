"""
GigShield — Shared Database Module
Async SQLAlchemy engine + session factory.
All services import get_db() as a FastAPI dependency.
"""
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from shared.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""
    pass


# ── Engine ────────────────────────────────────────────────────────────────────

def _build_engine(pool_size: int | None = None):
    """
    Build async engine.
    NullPool is used for services that run in multi-process/worker contexts
    to avoid connection leaks across forks.
    """
    connect_args: dict = {
        "server_settings": {
            "application_name": settings.service_name,
        }
    }

    if pool_size is None:
        # Use connection pool (default for single-process services)
        return create_async_engine(
            settings.database_url,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_timeout=settings.db_pool_timeout,
            pool_pre_ping=True,  # Validates connections before checkout
            echo=settings.env == "development",
            connect_args=connect_args,
        )
    else:
        return create_async_engine(
            settings.database_url,
            poolclass=NullPool,
            echo=settings.env == "development",
            connect_args=connect_args,
        )


engine = _build_engine()

AsyncSessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


# ── FastAPI Dependency ────────────────────────────────────────────────────────

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides a database session.
    Session is committed on success, rolled back on exception,
    and closed in all cases.

    Usage:
        @router.post("/")
        async def create(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ── Context Manager ───────────────────────────────────────────────────────────

@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager version for use outside of FastAPI request cycle
    (e.g., background tasks, startup/shutdown events).

    Usage:
        async with get_db_context() as db:
            ...
    """
    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ── Lifecycle ─────────────────────────────────────────────────────────────────

async def init_db() -> None:
    """Called at service startup to verify DB connectivity."""
    try:
        async with engine.connect() as conn:
            from sqlalchemy import text
            await conn.execute(text("SELECT 1"))
        logger.info("Database connection verified ✓")
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        raise


async def close_db() -> None:
    """Called at service shutdown to cleanly close the connection pool."""
    await engine.dispose()
    logger.info("Database connection pool closed ✓")
