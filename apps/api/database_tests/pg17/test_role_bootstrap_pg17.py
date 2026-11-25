from __future__ import annotations

import os
import secrets

import pytest
from apps.api.database_tests.identity_role_acceptance import (
    RedactedTestSecret,
    migrate_as_migrator,
    verify_catalog_foundation,
    verify_identity_foundation,
    verify_public_catalog_api,
)
from drip.core.migration_checkpoint import T_REVISION_ID
from scripts.bootstrap_identity_database import bootstrap as bootstrap_pg17_checkpoint
from scripts.provision_test_identity_roles import (
    authorize_test_migrator_checkpoint,
    provision_test_roles,
)
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

pytestmark = pytest.mark.integration


def _admin_url() -> str:
    value = os.environ.get("DRIP_PG17_TEST_ADMIN_URL", "")
    url = make_url(value) if value else None
    if (
        url is None
        or url.host != "127.0.0.1"
        or url.port != 55436
        or url.database != "drip_pg17_admin"
        or url.username != "drip_pg17_test"
        or not url.password
        or url.query
    ):
        raise RuntimeError("The guarded PG17 test harness environment is unavailable.")
    return value


@pytest.mark.asyncio
async def test_pg17_role_bootstrap_is_independent_atomic_verified_and_idempotent(tmp_path):
    admin_url = make_url(_admin_url())
    database = "drip_pg17_target"
    engine = create_async_engine(admin_url, poolclass=NullPool)
    created = False
    migrator_password = RedactedTestSecret(secrets.token_hex(32))
    runtime_password = RedactedTestSecret(secrets.token_hex(32))
    try:
        async with engine.connect() as connection:
            info = (
                await connection.execute(
                    text(
                        "SELECT current_database(), session_user, current_setting('server_version_num')::int, "
                        "current_setting('server_encoding') FROM pg_catalog.pg_roles "
                        "WHERE rolname = session_user AND rolsuper"
                    )
                )
            ).one()
            assert info == ("drip_pg17_admin", "drip_pg17_test", 170012, "UTF8")
            assert await connection.scalar(
                text("SELECT 1 FROM pg_catalog.pg_database WHERE datname = :name"),
                {"name": database},
            ) is None

        async with engine.connect() as connection:
            connection = await connection.execution_options(isolation_level="AUTOCOMMIT")
            await connection.exec_driver_sql(
                f'CREATE DATABASE "{database}" OWNER drip_pg17_test ENCODING \'UTF8\' TEMPLATE template0'
            )
            created = True

        target_url = admin_url.set(database=database)
        first = await provision_test_roles(
            target_url.render_as_string(hide_password=False),
            migrator_password=migrator_password.reveal(),
            runtime_password=runtime_password.reveal(),
        )
        assert (first.state, first.server_major, first.database) == ("created", 17, database)
        second = await provision_test_roles(
            target_url.render_as_string(hide_password=False),
            migrator_password=migrator_password.reveal(),
            runtime_password=runtime_password.reveal(),
        )
        assert (second.state, second.server_major, second.database) == (
            "verified_noop",
            17,
            database,
        )

        checkpoint_receipt = tmp_path / "checkpoint-receipt.json"
        assert await bootstrap_pg17_checkpoint(
            target_url.render_as_string(hide_password=False), checkpoint_receipt
        ) == "adopted"
        assert T_REVISION_ID == "0003_portable_identity_ckpt"
        await authorize_test_migrator_checkpoint(target_url.render_as_string(hide_password=False))

        migrator_engine = create_async_engine(
            admin_url.set(
                username="drip_identity_migrator",
                password=migrator_password.reveal(),
                database=database,
            ),
            poolclass=NullPool,
        )
        runtime_engine = create_async_engine(
            admin_url.set(
                username="drip_identity_runtime",
                password=runtime_password.reveal(),
                database=database,
            ),
            poolclass=NullPool,
        )
        try:
            async with migrator_engine.connect() as connection:
                assert await connection.scalar(text("SELECT current_user")) == "drip_identity_migrator"
                assert await connection.scalar(text("SELECT has_database_privilege(current_user, current_database(), 'CREATE')"))
            async with runtime_engine.connect() as connection:
                assert await connection.scalar(text("SELECT current_user")) == "drip_identity_runtime"
                assert not await connection.scalar(text("SELECT has_database_privilege(current_user, current_database(), 'CREATE')"))
        finally:
            await migrator_engine.dispose()
            await runtime_engine.dispose()

        migrator_url = admin_url.set(
            username="drip_identity_migrator",
            password=migrator_password.reveal(),
            database=database,
        )
        runtime_url = admin_url.set(
            username="drip_identity_runtime",
            password=runtime_password.reveal(),
            database=database,
        )
        await migrate_as_migrator(migrator_url, "0004_identity_foundation")
        await verify_identity_foundation(target_url, runtime_url, migrator_url)
        await migrate_as_migrator(migrator_url, "head")
        await verify_catalog_foundation(target_url, runtime_url, migrator_url)
        await verify_public_catalog_api(target_url, runtime_url)
    finally:
        await engine.dispose()
        if created:
            cleanup = create_async_engine(admin_url, poolclass=NullPool)
            try:
                async with cleanup.connect() as connection:
                    connection = await connection.execution_options(isolation_level="AUTOCOMMIT")
                    active = await connection.scalar(
                        text(
                            "SELECT 1 FROM pg_catalog.pg_stat_activity "
                            "WHERE datname = :name AND pid <> pg_backend_pid() LIMIT 1"
                        ),
                        {"name": database},
                    )
                    if active:
                        raise RuntimeError("Task-created PG17 test database still has active sessions.")
                    await connection.exec_driver_sql(f'DROP DATABASE "{database}"')
            finally:
                await cleanup.dispose()
