import os
import uuid

import pytest
from alembic import command
from alembic.config import Config
from drip.core.config import settings
from drip.core.database import check_database_health, engine
from drip.core.redis import check_redis_health
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.disposable_targets import validate_disposable_targets
from tests.test_migrations import API_ROOT, UUIDProbe

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def require_disposable_targets():
    # Startup preflight already ran before these modules were imported. Recheck
    # here to catch environment/settings drift before each live test.
    database_url, redis_url = validate_disposable_targets(os.environ)
    if settings.DATABASE_URL != database_url or settings.REDIS_URL != redis_url:
        pytest.fail("Disposable test settings changed after preflight.", pytrace=False)


@pytest.mark.asyncio
async def test_live_database_connection():
    is_healthy, latency, message = await check_database_health()
    assert is_healthy is True
    assert latency > 0
    assert "PostgreSQL" in message


@pytest.mark.asyncio
async def test_live_postgresql18_uuidv7():
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT uuidv7()"))
        val = result.scalar()
        assert val is not None
        assert val.version == 7
        version = await conn.scalar(text("SHOW server_version_num"))
        assert 180000 <= int(version) < 190000
        assert (
            await conn.scalar(text("SELECT pg_catalog.uuid_extract_version(pg_catalog.uuidv7())"))
            == 7
        )


@pytest.mark.asyncio
async def test_live_redis_connection():
    is_healthy, latency, message = await check_redis_health()
    assert is_healthy is True
    assert latency > 0
    assert "Redis" in message


@pytest.mark.asyncio
async def test_live_readiness_probe_integration(client: AsyncClient):
    response = await client.get("/api/v1/health/ready")
    assert response.status_code == 200, f"Readiness failed: {response.json()}"
    data = response.json()
    assert data["status"] == "healthy"
    assert data["services"]["postgres"]["status"] == "healthy"
    assert data["services"]["redis"]["status"] == "healthy"
    assert data["services"]["postgres"]["latency_ms"] > 0
    assert data["services"]["redis"]["latency_ms"] > 0


@pytest.mark.asyncio
async def test_migration_roundtrip_and_actual_uuid_defaults():
    # Everything, including the uniquely named schema, is rolled back. Existing data is untouched.
    schema = "gate_b_" + uuid.uuid4().hex
    async with engine.connect() as conn:
        transaction = await conn.begin()
        try:
            await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
            await conn.execute(text(f'SET LOCAL search_path TO "{schema}", public'))

            def migrate(connection):
                config = Config(str(API_ROOT / "alembic.ini"))
                config.attributes["connection"] = connection
                config.attributes["version_table_schema"] = schema
                command.upgrade(config, "0002_require_pg18_uuidv7")
                command.downgrade(config, "base")
                command.upgrade(config, "0002_require_pg18_uuidv7")

            await conn.run_sync(migrate)
            assert (
                await conn.scalar(text("SELECT version_num FROM alembic_version"))
                == "0002_require_pg18_uuidv7"
            )
            await conn.run_sync(UUIDProbe.__table__.create)
            direct = await conn.scalar(
                text("INSERT INTO gate_b_uuid_probe DEFAULT VALUES RETURNING id")
            )
            assert direct.version == 7
            async with AsyncSession(bind=conn) as session:
                entity = UUIDProbe()
                session.add(entity)
                await session.flush()
                assert entity.id.version == 7
        finally:
            await transaction.rollback()
