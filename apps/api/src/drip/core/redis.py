import time
from collections.abc import AsyncGenerator
from typing import Any

import redis.asyncio as aioredis
from redis.asyncio import Redis

from drip.core.config import settings

redis_client: Redis[Any] | None = None


def get_redis_client() -> Redis[Any]:
    """Return the global Redis client instance, initializing it if necessary."""
    global redis_client
    if redis_client is None:
        redis_client = aioredis.from_url(
            settings.REDIS_URL,
            socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
            decode_responses=True,
        )
    return redis_client


async def get_redis() -> AsyncGenerator[Redis[Any]]:
    """FastAPI dependency for injecting Redis client."""
    client = get_redis_client()
    yield client


async def check_redis_health() -> tuple[bool, float, str]:
    """Execute a ping against Redis and measure latency.

    Returns:
        Tuple of (is_healthy, latency_ms, error_or_success_message)
    """
    start_time = time.perf_counter()
    try:
        client = get_redis_client()
        try:
            pong = await client.ping()
        except RuntimeError:
            # Reconnect if event loop changed (common in async test runners and worker resets)
            await close_redis_connections()
            client = get_redis_client()
            pong = await client.ping()

        latency_ms = (time.perf_counter() - start_time) * 1000
        if pong:
            return True, round(latency_ms, 2), "Redis connection active"
        return False, round(latency_ms, 2), "Redis ping returned false"
    except Exception as e:
        latency_ms = (time.perf_counter() - start_time) * 1000
        return False, round(latency_ms, 2), f"Redis error: {type(e).__name__}"


async def close_redis_connections() -> None:
    """Close Redis client during application shutdown."""
    global redis_client
    if redis_client is not None:
        await redis_client.aclose()  # type: ignore[attr-defined]
        redis_client = None
