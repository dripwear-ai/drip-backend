from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Response, status
from pydantic import BaseModel, Field

from drip.core.config import settings
from drip.core.database import check_database_health
from drip.core.redis import check_redis_health

router = APIRouter(prefix="/health", tags=["Infrastructure Health"])


class ServiceHealthModel(BaseModel):
    status: Literal["healthy", "degraded", "unhealthy"]
    latency_ms: float | None = None
    message: str


class LiveResponseModel(BaseModel):
    status: Literal["alive"]
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class ReadyResponseModel(BaseModel):
    status: Literal["healthy", "degraded", "unhealthy"]
    version: str
    environment: str
    services: dict[str, ServiceHealthModel]
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


@router.get(
    "/live",
    response_model=LiveResponseModel,
    status_code=status.HTTP_200_OK,
    summary="Liveness Probe",
    description="Returns 200 immediately to indicate the application process is running and accepting connections.",
)
async def liveness_probe() -> LiveResponseModel:
    return LiveResponseModel(status="alive")


@router.get(
    "/ready",
    response_model=ReadyResponseModel,
    status_code=status.HTTP_200_OK,
    summary="Readiness Probe",
    description="Validates that all upstream dependencies (PostgreSQL, Redis) are reachable and healthy.",
)
async def readiness_probe(response: Response) -> ReadyResponseModel:
    db_ok, db_lat, db_msg = await check_database_health()
    redis_ok, redis_lat, redis_msg = await check_redis_health()

    services = {
        "postgres": ServiceHealthModel(
            status="healthy" if db_ok else "unhealthy",
            latency_ms=db_lat,
            message=db_msg,
        ),
        "redis": ServiceHealthModel(
            status="healthy" if redis_ok else "unhealthy",
            latency_ms=redis_lat,
            message=redis_msg,
        ),
    }

    all_healthy = db_ok and redis_ok
    overall_status: Literal["healthy", "degraded", "unhealthy"] = (
        "healthy" if all_healthy else "unhealthy"
    )

    if not all_healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return ReadyResponseModel(
        status=overall_status,
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
        services=services,
    )
