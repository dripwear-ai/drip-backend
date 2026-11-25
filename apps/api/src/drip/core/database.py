import time
from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from drip.core.config import settings

# Global async engine and sessionmaker
engine_kwargs: dict[str, Any] = {
    "echo": settings.DEBUG,
    "pool_pre_ping": True,
}

if settings.ENVIRONMENT == "test":
    engine_kwargs["poolclass"] = NullPool
else:
    engine_kwargs["pool_size"] = settings.DB_POOL_SIZE
    engine_kwargs["max_overflow"] = settings.DB_MAX_OVERFLOW
    engine_kwargs["pool_timeout"] = settings.DB_POOL_TIMEOUT

engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    **engine_kwargs,
)

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession]:
    """FastAPI dependency yielding an async database session."""
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def check_database_health() -> tuple[bool, float, str]:
    """Execute a simple query to verify database connectivity and measure latency.

    Returns:
        Tuple of (is_healthy, latency_ms, error_or_success_message)
    """
    start_time = time.perf_counter()
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        latency_ms = (time.perf_counter() - start_time) * 1000
        return True, round(latency_ms, 2), "PostgreSQL connection active"
    except Exception as e:
        latency_ms = (time.perf_counter() - start_time) * 1000
        return False, round(latency_ms, 2), f"PostgreSQL error: {type(e).__name__}"


async def close_database_connections() -> None:
    """Dispose the engine and close connection pools during application shutdown."""
    await engine.dispose()
