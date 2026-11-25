import os
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from tests.disposable_targets import (
    UnsafeTestTarget,
    prepare_test_environment,
    validate_disposable_targets,
)


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config: pytest.Config) -> None:
    # Configuration precedes test-module imports, unlike autouse fixtures.
    try:
        prepare_test_environment(os.environ, config.getoption("markexpr"))
        # Settings construction performs no engine/client creation. Check the
        # effective parser result as well as the supplied strings before collection.
        from drip.core.config import settings

        validate_disposable_targets(
            {
                "DRIP_TEST_DATABASE_URL": settings.DATABASE_URL,
                "DRIP_TEST_REDIS_URL": settings.REDIS_URL,
            }
        )
    except UnsafeTestTarget as exc:
        raise pytest.UsageError(str(exc)) from None


@pytest.fixture(autouse=True)
async def cleanup_connections():
    from drip.core.database import engine
    from drip.core.redis import close_redis_connections

    yield
    await engine.dispose()
    await close_redis_connections()


@pytest.fixture
def app():
    from drip.main import create_app

    return create_app()


@pytest.fixture
async def client(app) -> AsyncGenerator[AsyncClient]:
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
