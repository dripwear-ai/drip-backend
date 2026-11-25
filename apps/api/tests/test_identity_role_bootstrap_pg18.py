from __future__ import annotations

import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import pytest
from alembic import command
from alembic.config import Config
from apps.api.database_tests.identity_role_acceptance import (
    RedactedTestSecret,
    migrate_as_migrator,
    verify_catalog_foundation,
    verify_identity_foundation,
    verify_public_catalog_api,
)
from drip.core.config import settings
from drip.core.migration_checkpoint import T_REVISION_ID
from scripts.provision_test_identity_roles import (
    authorize_test_migrator_checkpoint,
    provision_test_roles,
)
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

pytestmark = pytest.mark.integration


async def _upgrade_as_disposable_admin(database_url, revision: str) -> None:
    engine = create_async_engine(make_url(database_url), poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            def run(sync_connection) -> None:
                config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
                config.attributes["connection"] = sync_connection
                config.attributes["version_table_schema"] = "public"
                command.upgrade(config, revision)

            await connection.run_sync(run)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_pg18_role_bootstrap_is_independent_atomic_verified_and_idempotent():
    admin_url = make_url(settings.DATABASE_URL)
    assert (
        admin_url.drivername,
        admin_url.host,
        admin_url.port,
        admin_url.database,
        admin_url.username,
    ) == ("postgresql+asyncpg", "127.0.0.1", 55435, "drip_gate_b_test", "drip_test")
    migrator_password = RedactedTestSecret(secrets.token_hex(32))
    runtime_password = RedactedTestSecret(secrets.token_hex(32))
    admin_engine = create_async_engine(admin_url, poolclass=NullPool)
    migrator_engine = None
    runtime_engine = None
    try:
        async with admin_engine.connect() as connection:
            info = (
                await connection.execute(
                    text(
                        "SELECT current_database(), session_user, current_setting('server_version_num')::int, "
                        "current_setting('server_encoding') FROM pg_catalog.pg_roles "
                        "WHERE rolname = session_user AND rolsuper"
                    )
                )
            ).one()
            assert info == ("drip_gate_b_test", "drip_test", 180006, "UTF8")

        first = await provision_test_roles(
            admin_url.render_as_string(hide_password=False),
            migrator_password=migrator_password.reveal(),
            runtime_password=runtime_password.reveal(),
        )
        assert (first.state, first.server_major, first.database) == (
            "created",
            18,
            "drip_gate_b_test",
        )
        second = await provision_test_roles(
            admin_url.render_as_string(hide_password=False),
            migrator_password=migrator_password.reveal(),
            runtime_password=runtime_password.reveal(),
        )
        assert (second.state, second.server_major, second.database) == (
            "verified_noop",
            18,
            "drip_gate_b_test",
        )

        migrator_engine = create_async_engine(
            admin_url.set(
                username="drip_identity_migrator", password=migrator_password.reveal()
            ),
            poolclass=NullPool,
        )
        runtime_engine = create_async_engine(
            admin_url.set(
                username="drip_identity_runtime", password=runtime_password.reveal()
            ),
            poolclass=NullPool,
        )
        async with migrator_engine.connect() as connection:
            assert await connection.scalar(text("SELECT current_user")) == "drip_identity_migrator"
            assert await connection.scalar(text("SELECT has_database_privilege(current_user, current_database(), 'CREATE')"))
        async with runtime_engine.connect() as connection:
            assert await connection.scalar(text("SELECT current_user")) == "drip_identity_runtime"
            assert not await connection.scalar(text("SELECT has_database_privilege(current_user, current_database(), 'CREATE')"))

        await _upgrade_as_disposable_admin(admin_url, T_REVISION_ID)
        await authorize_test_migrator_checkpoint(settings.DATABASE_URL)
        migrator_url = admin_url.set(
            username="drip_identity_migrator", password=migrator_password.reveal()
        )
        runtime_url = admin_url.set(
            username="drip_identity_runtime", password=runtime_password.reveal()
        )
        await migrate_as_migrator(migrator_url, "0004_identity_foundation")
        await verify_identity_foundation(admin_url, runtime_url, migrator_url)
        await migrate_as_migrator(migrator_url, "head")
        await verify_catalog_foundation(admin_url, runtime_url, migrator_url)
        await verify_public_catalog_api(admin_url, runtime_url)
    finally:
        if migrator_engine is not None:
            await migrator_engine.dispose()
        if runtime_engine is not None:
            await runtime_engine.dispose()
        await admin_engine.dispose()
