from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from drip.api.router import api_v1_router
from drip.catalog.request_limits import DiscoveryRequestLimitMiddleware
from drip.core.config import settings
from drip.core.database import close_database_connections
from drip.core.errors import setup_error_handlers
from drip.core.logging import setup_logging
from drip.core.redis import close_redis_connections


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Application lifespan context manager managing startup and graceful shutdown."""
    # Startup actions
    setup_logging(settings.LOG_LEVEL)
    settings.validate_production_security()

    yield

    # Graceful shutdown actions
    await close_database_connections()
    await close_redis_connections()


def create_app() -> FastAPI:
    """FastAPI application factory for DRIP 2.0."""
    app = FastAPI(
        title="DRIP 2.0 API",
        version=settings.VERSION,
        description="Authoritative backend modular monolith API for DRIP 2.0",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
    )

    # Safe CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    app.add_middleware(DiscoveryRequestLimitMiddleware)

    # Error handling
    setup_error_handlers(app)

    # Mount API routers
    app.include_router(api_v1_router)

    @app.get("/", tags=["Root"])
    async def root() -> dict[str, str]:
        return {
            "name": "DRIP 2.0 API",
            "version": settings.VERSION,
            "status": "online",
            "docs": "/docs" if not settings.is_production else "disabled in production",
        }

    return app


# Default app instance for ASGI servers
app = create_app()
