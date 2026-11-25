"""Ephemeral fail-closed abuse controls for public catalog reads."""

from __future__ import annotations

import hashlib
import hmac
from typing import Annotated, Protocol

from fastapi import Depends, Request

from drip.core.config import settings
from drip.core.errors import DripException, ServiceUnavailableException
from drip.core.redis import get_redis_client

_TOKEN_BUCKET_SCRIPT = """
local now = redis.call('TIME')
local now_ms = tonumber(now[1]) * 1000 + math.floor(tonumber(now[2]) / 1000)
local state = redis.call('HMGET', KEYS[1], 'tokens', 'updated_ms')
local capacity = tonumber(ARGV[2]) * 1000
local tokens = tonumber(state[1]) or capacity
local updated_ms = tonumber(state[2]) or now_ms
local elapsed_ms = math.max(0, now_ms - updated_ms)
tokens = math.min(capacity, tokens + elapsed_ms * tonumber(ARGV[1]) / 60)
local allowed = 0
if tokens >= 1000 then
    tokens = tokens - 1000
    allowed = 1
end
redis.call('HSET', KEYS[1], 'tokens', tokens, 'updated_ms', now_ms)
redis.call('PEXPIRE', KEYS[1], math.max(120000, math.ceil(capacity * 120000 / (tonumber(ARGV[1]) * 1000))))
return allowed
"""

class RedisEval(Protocol):
    async def eval(self, script: str, key_count: int, *keys_and_args: str | int) -> int: ...


def get_catalog_redis_client() -> RedisEval:
    """Resolve Redis only when a public request reaches this dependency."""
    return get_redis_client()


RedisClient = Annotated[RedisEval, Depends(get_catalog_redis_client)]


async def require_public_catalog_rate_limit(request: Request, redis: RedisClient) -> None:
    """Apply a shared token bucket without persisting raw client addresses."""
    rate = settings.CATALOG_PUBLIC_RATE_PER_MINUTE
    burst = settings.CATALOG_PUBLIC_RATE_BURST
    client = request.client
    if rate is None or burst is None or client is None or not client.host:
        raise ServiceUnavailableException("Public catalog abuse protection is not configured.")

    key_digest = hmac.new(
        settings.SECRET_KEY.encode("utf-8"), client.host.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    try:
        allowed = await redis.eval(
            _TOKEN_BUCKET_SCRIPT,
            1,
            f"drip:catalog:public:rate:{key_digest}",
            rate,
            burst,
        )
    except Exception:
        raise ServiceUnavailableException("Public catalog abuse protection is unavailable.") from None
    if not allowed:
        raise DripException("Catalog request limit exceeded.", "RATE_LIMITED", 429)
