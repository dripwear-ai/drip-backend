from unittest.mock import patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root_endpoint(client: AsyncClient):
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "DRIP 2.0 API"
    assert data["status"] == "online"


@pytest.mark.asyncio
async def test_liveness_probe(client: AsyncClient):
    response = await client.get("/api/v1/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "alive"
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_readiness_probe_all_healthy(client: AsyncClient):
    with patch(
        "drip.api.v1.health.check_database_health",
        return_value=(True, 2.5, "PostgreSQL connection active"),
    ):
        with patch(
            "drip.api.v1.health.check_redis_health",
            return_value=(True, 1.2, "Redis connection active"),
        ):
            response = await client.get("/api/v1/health/ready")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert data["services"]["postgres"]["status"] == "healthy"
            assert data["services"]["redis"]["status"] == "healthy"


@pytest.mark.asyncio
async def test_readiness_probe_degraded_when_db_down(client: AsyncClient):
    with patch(
        "drip.api.v1.health.check_database_health",
        return_value=(False, 10.0, "PostgreSQL connection refused"),
    ):
        with patch(
            "drip.api.v1.health.check_redis_health",
            return_value=(True, 1.2, "Redis connection active"),
        ):
            response = await client.get("/api/v1/health/ready")
            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "unhealthy"
            assert data["services"]["postgres"]["status"] == "unhealthy"
            assert data["services"]["redis"]["status"] == "healthy"


@pytest.mark.asyncio
async def test_readiness_probe_degraded_when_redis_down(client: AsyncClient):
    with patch(
        "drip.api.v1.health.check_database_health",
        return_value=(True, 2.5, "PostgreSQL connection active"),
    ):
        with patch(
            "drip.api.v1.health.check_redis_health", return_value=(False, 15.0, "Redis timeout")
        ):
            response = await client.get("/api/v1/health/ready")
            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "unhealthy"
            assert data["services"]["postgres"]["status"] == "healthy"
            assert data["services"]["redis"]["status"] == "unhealthy"
