from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from drip.core.config import settings
from drip.core.migration_checkpoint import T_REVISION_ID
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

API_ROOT = Path(__file__).resolve().parents[1]
PG18_MAJOR = 18


@asynccontextmanager
async def _disposable_pg18_database() -> AsyncIterator[str]:
    root_url = make_url(settings.DATABASE_URL)
    if (
        root_url.drivername != "postgresql+asyncpg"
        or root_url.host != "127.0.0.1"
        or root_url.port != 55435
        or root_url.database != "drip_gate_b_test"
    ):
        raise RuntimeError("PG18 migration test target is not the documented disposable endpoint.")
    admin_url = root_url.set(database="postgres")
    admin_engine = create_async_engine(admin_url, poolclass=NullPool)
    name = f"drip_migration_{uuid.uuid4().hex}"
    created = False
    try:
        async with admin_engine.connect() as connection:
            server_version = await connection.scalar(
                text("SELECT current_setting('server_version_num')::integer")
            )
            database_name = await connection.scalar(text("SELECT current_database()"))
            if database_name != "postgres" or server_version // 10000 != PG18_MAJOR:
                raise RuntimeError("PG18 disposable migration target failed server attestation.")
        async with admin_engine.connect() as connection:
            connection = await connection.execution_options(isolation_level="AUTOCOMMIT")
            await connection.execute(
                text(f'CREATE DATABASE "{name}" OWNER drip_test ENCODING \'UTF8\' TEMPLATE template0')
            )
            created = True
        yield root_url.set(database=name).render_as_string(hide_password=False)
    finally:
        await admin_engine.dispose()
        if created:
            cleanup_engine = create_async_engine(admin_url, poolclass=NullPool)
            try:
                async with cleanup_engine.connect() as connection:
                    connection = await connection.execution_options(isolation_level="AUTOCOMMIT")
                    active = await connection.scalar(
                        text(
                            "SELECT 1 FROM pg_catalog.pg_stat_activity "
                            "WHERE datname = :name AND pid <> pg_backend_pid() LIMIT 1"
                        ),
                        {"name": name},
                    )
                    if active:
                        raise RuntimeError("Task-created database still has active sessions; not dropping it.")
                    await connection.execute(text(f'DROP DATABASE "{name}"'))
            finally:
                await cleanup_engine.dispose()


async def _run_migration(database_url: str, revision: str) -> list[str]:
    engine = create_async_engine(make_url(database_url), poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            def run(sync_connection):
                config = Config(str(API_ROOT / "alembic.ini"))
                config.attributes["connection"] = sync_connection
                config.attributes["version_table_schema"] = "public"
                command.upgrade(config, revision)

            await connection.run_sync(run)
        async with engine.connect() as connection:
            rows = await connection.execute(
                text("SELECT version_num FROM public.alembic_version ORDER BY version_num")
            )
            return list(rows.scalars())
    finally:
        await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_pg18_fresh_upgrade_runs_0001_0002_then_t_and_uuidv7_assertion():
    async with _disposable_pg18_database() as database_url:
        assert await _run_migration(database_url, T_REVISION_ID) == [T_REVISION_ID]
        engine = create_async_engine(make_url(database_url), poolclass=NullPool)
        try:
            async with engine.connect() as connection:
                version = await connection.scalar(
                    text("SELECT pg_catalog.uuid_extract_version(pg_catalog.uuidv7())")
                )
                assert version == 7
                extension = await connection.scalar(
                    text("SELECT extname FROM pg_catalog.pg_extension WHERE extname = 'pgcrypto'")
                )
                assert extension == "pgcrypto"
        finally:
            await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_pg18_existing_revision_0002_upgrades_normally_to_t():
    async with _disposable_pg18_database() as database_url:
        assert await _run_migration(database_url, "0002_require_pg18_uuidv7") == [
            "0002_require_pg18_uuidv7"
        ]
        assert await _run_migration(database_url, T_REVISION_ID) == [T_REVISION_ID]
