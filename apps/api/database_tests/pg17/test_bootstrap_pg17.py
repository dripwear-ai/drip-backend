from __future__ import annotations

import os
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from alembic import command
from drip.core.migration_checkpoint import (
    PG17_ADMIN_DATABASE,
    PG17_BOOTSTRAP_URL_PATTERN,
    PG17_TARGET_DATABASE,
    T_REVISION_ID,
    database_attestation,
)
from scripts.bootstrap_identity_database import (
    _alembic_config,
    _migration_environment,
    bootstrap,
)
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine
from sqlalchemy.pool import NullPool

pytestmark = pytest.mark.integration
ADMIN_URL_PATTERN = re.compile(
    r"^postgresql\+asyncpg://drip_pg17_test:[0-9a-f]{64}"
    r"@127\.0\.0\.1:55436/drip_pg17_admin$"
)


def _admin_url() -> str:
    value = os.environ.get("DRIP_PG17_TEST_ADMIN_URL", "")
    if ADMIN_URL_PATTERN.fullmatch(value) is None:
        raise RuntimeError("The guarded PG17 test harness environment is unavailable.")
    return value


@asynccontextmanager
async def disposable_database(encoding: str = "UTF8") -> AsyncIterator[str]:
    admin_url = make_url(_admin_url())
    admin_engine = create_async_engine(
        admin_url,
        poolclass=NullPool,
        connect_args={"timeout": 5.0, "command_timeout": 15.0},
    )
    database_name = PG17_TARGET_DATABASE
    created = False
    try:
        async with admin_engine.connect() as connection:
            attestation = await connection.run_sync(
                lambda sync_connection: database_attestation(
                    sync_connection, include_system_identifier=True
                )
            )
            if (
                attestation["database_name"] != PG17_ADMIN_DATABASE
                or attestation["role_name"] != "drip_pg17_test"
                or attestation["server_version_num"] // 10000 != 17
            ):
                raise RuntimeError("The disposable PG17 administrative target failed attestation.")
            exists = await connection.scalar(
                text("SELECT 1 FROM pg_catalog.pg_database WHERE datname = :name"),
                {"name": database_name},
            )
            if exists:
                raise RuntimeError("The task-scoped PG17 database already exists; refusing to reuse it.")

        async with admin_engine.connect() as connection:
            connection = await connection.execution_options(isolation_level="AUTOCOMMIT")
            locale_options = " LC_COLLATE 'C' LC_CTYPE 'C'" if encoding == "SQL_ASCII" else ""
            await connection.execute(
                text(
                    f'CREATE DATABASE "{database_name}" OWNER drip_pg17_test '
                    f"ENCODING '{encoding}'{locale_options} TEMPLATE template0"
                )
            )
            created = True

        url = admin_url.set(database=database_name).render_as_string(hide_password=False)
        yield url
    finally:
        await admin_engine.dispose()
        if created:
            cleanup_engine = create_async_engine(
                admin_url,
                poolclass=NullPool,
                connect_args={"timeout": 5.0, "command_timeout": 15.0},
            )
            try:
                async with cleanup_engine.connect() as connection:
                    connection = await connection.execution_options(isolation_level="AUTOCOMMIT")
                    active = await connection.scalar(
                        text(
                            "SELECT 1 FROM pg_catalog.pg_stat_activity "
                            "WHERE datname = :name AND pid <> pg_backend_pid() LIMIT 1"
                        ),
                        {"name": database_name},
                    )
                    if active:
                        raise RuntimeError("Task-scoped database still has active sessions; not dropping it.")
                    await connection.execute(text(f'DROP DATABASE "{database_name}"'))
            finally:
                await cleanup_engine.dispose()


def _bootstrap_url(target_url: str) -> str:
    return make_url(target_url).render_as_string(hide_password=False)


async def _revision(connection: AsyncConnection) -> list[str]:
    table_exists = await connection.scalar(text("SELECT to_regclass('public.alembic_version')"))
    if table_exists is None:
        return []
    return list(
        (
            await connection.execute(
                text("SELECT version_num FROM public.alembic_version ORDER BY version_num")
            )
        ).scalars()
    )


async def _execute_upgrade(target_url: str, revision: str) -> None:
    engine = create_async_engine(make_url(target_url), poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            def run(sync_connection):
                config = _alembic_config(sync_connection)
                with _migration_environment(target_url):
                    command.upgrade(config, revision)

            await connection.run_sync(run)
    finally:
        await engine.dispose()


async def _execute_downgrade(target_url: str, revision: str) -> None:
    engine = create_async_engine(make_url(target_url), poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            def run(sync_connection):
                config = _alembic_config(sync_connection)
                with _migration_environment(target_url):
                    command.downgrade(config, revision)

            await connection.run_sync(run)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_pg17_ordinary_historical_upgrade_fails_at_0002_without_false_checkpoint(tmp_path):
    async with disposable_database() as target_url:
        with pytest.raises(Exception, match="DRIP requires PostgreSQL 18"):
            await _execute_upgrade(target_url, "head")

        engine = create_async_engine(make_url(target_url), poolclass=NullPool)
        try:
            async with engine.connect() as connection:
                revisions = await _revision(connection)
                assert T_REVISION_ID not in revisions
                assert "head" not in revisions
        finally:
            await engine.dispose()


@pytest.mark.asyncio
async def test_pg17_bootstrap_executes_0001_stamps_exact_t_and_is_idempotent(tmp_path):
    async with disposable_database() as target_url:
        url = _bootstrap_url(target_url)
        receipt = tmp_path / "bootstrap-receipt.json"
        assert re.fullmatch(PG17_BOOTSTRAP_URL_PATTERN, url)

        assert await bootstrap(url, receipt) == "adopted"
        receipt_data = receipt.read_text(encoding="utf-8")
        assert '"extension_provenance": "created_by_0001"' in receipt_data
        assert '"revision": "0003_portable_identity_ckpt"' in receipt_data
        assert await bootstrap(url, receipt) == "already_adopted"

        engine = create_async_engine(make_url(target_url), poolclass=NullPool)
        try:
            async with engine.connect() as connection:
                assert await _revision(connection) == [T_REVISION_ID]
                extension = await connection.scalar(
                    text("SELECT extname FROM pg_catalog.pg_extension WHERE extname = 'pgcrypto'")
                )
                assert extension == "pgcrypto"
        finally:
            await engine.dispose()


@pytest.mark.asyncio
async def test_pg17_failure_after_0001_rolls_back_and_same_receipt_can_retry(tmp_path):
    async with disposable_database() as target_url:
        url = _bootstrap_url(target_url)
        receipt = tmp_path / "bootstrap-receipt.json"

        def interrupt_before_stamp(_connection):
            raise RuntimeError("injected transaction interruption")

        with pytest.raises(RuntimeError, match="injected transaction interruption"):
            await bootstrap(url, receipt, before_stamp_hook=interrupt_before_stamp)

        engine = create_async_engine(make_url(target_url), poolclass=NullPool)
        try:
            async with engine.connect() as connection:
                assert await _revision(connection) == []
                assert await connection.scalar(
                    text("SELECT 1 FROM pg_catalog.pg_extension WHERE extname = 'pgcrypto'")
                ) is None
        finally:
            await engine.dispose()

        assert await bootstrap(url, receipt) == "adopted"


@pytest.mark.asyncio
async def test_pg17_bootstrap_refuses_unknown_public_object(tmp_path):
    async with disposable_database() as target_url:
        engine = create_async_engine(make_url(target_url), poolclass=NullPool)
        try:
            async with engine.begin() as connection:
                await connection.execute(text("CREATE TABLE public.unapproved_object (id integer)"))
        finally:
            await engine.dispose()

        with pytest.raises(Exception, match="unaccounted application objects"):
            await bootstrap(_bootstrap_url(target_url), tmp_path / "receipt.json")


@pytest.mark.asyncio
async def test_pg17_bootstrap_refuses_existing_revision_table(tmp_path):
    async with disposable_database() as target_url:
        engine = create_async_engine(make_url(target_url), poolclass=NullPool)
        try:
            async with engine.begin() as connection:
                await connection.execute(
                    text("CREATE TABLE public.alembic_version (version_num varchar(32) NOT NULL)")
                )
                await connection.execute(
                    text("INSERT INTO public.alembic_version (version_num) VALUES ('unexplained')")
                )
        finally:
            await engine.dispose()

        with pytest.raises(Exception, match="revision-table location|revision state"):
            await bootstrap(_bootstrap_url(target_url), tmp_path / "receipt.json")


@pytest.mark.asyncio
async def test_pg17_bootstrap_rejects_non_utf8_database_before_migration(tmp_path):
    async with disposable_database(encoding="SQL_ASCII") as target_url:
        with pytest.raises(Exception, match="encoding is unsupported"):
            await bootstrap(_bootstrap_url(target_url), tmp_path / "receipt.json")

        engine = create_async_engine(make_url(target_url), poolclass=NullPool)
        try:
            async with engine.connect() as connection:
                assert await _revision(connection) == []
        finally:
            await engine.dispose()


@pytest.mark.asyncio
async def test_pg17_downgrade_below_checkpoint_is_rejected(tmp_path):
    async with disposable_database() as target_url:
        await bootstrap(_bootstrap_url(target_url), tmp_path / "bootstrap-receipt.json")
        with pytest.raises(Exception, match="Downgrade below checkpoint T"):
            await _execute_downgrade(target_url, "0002_require_pg18_uuidv7")

        engine = create_async_engine(make_url(target_url), poolclass=NullPool)
        try:
            async with engine.connect() as connection:
                assert await _revision(connection) == [T_REVISION_ID]
        finally:
            await engine.dispose()
