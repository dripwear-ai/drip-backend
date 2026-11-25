from __future__ import annotations

import inspect

import pytest
from drip.catalog.abuse import require_public_catalog_rate_limit
from drip.core.config import settings
from drip.core.errors import DripException, ServiceUnavailableException
from starlette.requests import Request


class RedisProbe:
    def __init__(self, result: int = 1, failure: Exception | None = None) -> None:
        self.result = result
        self.failure = failure
        self.key: str | None = None

    async def eval(self, script: str, key_count: int, key: str, rate: int, burst: int) -> int:
        self.key = key
        if self.failure is not None:
            raise self.failure
        return self.result


def _request() -> Request:
    return Request({"type": "http", "client": ("203.0.113.50", 12345), "headers": []})


def _run_immediate(coroutine):
    if not inspect.iscoroutine(coroutine):
        raise TypeError("Expected a coroutine.")
    try:
        coroutine.send(None)
    except StopIteration as completed:
        return completed.value
    finally:
        if coroutine.cr_await is not None:
            coroutine.close()
    raise AssertionError("Redis test double unexpectedly suspended on external I/O.")


def test_unconfigured_public_limits_fail_closed_without_using_redis(monkeypatch):
    monkeypatch.setattr(settings, "CATALOG_PUBLIC_RATE_PER_MINUTE", None)
    monkeypatch.setattr(settings, "CATALOG_PUBLIC_RATE_BURST", None)
    redis = RedisProbe()
    with pytest.raises(ServiceUnavailableException, match="not configured"):
        _run_immediate(require_public_catalog_rate_limit(_request(), redis))
    assert redis.key is None


def test_public_rate_limiter_uses_ephemeral_hmac_key_and_sanitizes_redis_failure(monkeypatch):
    monkeypatch.setattr(settings, "CATALOG_PUBLIC_RATE_PER_MINUTE", 60)
    monkeypatch.setattr(settings, "CATALOG_PUBLIC_RATE_BURST", 10)
    redis = RedisProbe()
    _run_immediate(require_public_catalog_rate_limit(_request(), redis))
    assert redis.key is not None
    assert "203.0.113.50" not in redis.key

    failing = RedisProbe(failure=RuntimeError("private redis detail"))
    with pytest.raises(ServiceUnavailableException, match="unavailable") as error:
        _run_immediate(require_public_catalog_rate_limit(_request(), failing))
    assert "private redis detail" not in str(error.value)


def test_public_rate_limiter_returns_429_when_token_bucket_is_empty(monkeypatch):
    monkeypatch.setattr(settings, "CATALOG_PUBLIC_RATE_PER_MINUTE", 60)
    monkeypatch.setattr(settings, "CATALOG_PUBLIC_RATE_BURST", 10)
    with pytest.raises(DripException) as error:
        _run_immediate(require_public_catalog_rate_limit(_request(), RedisProbe(result=0)))
    assert error.value.status_code == 429
