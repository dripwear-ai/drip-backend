"""Guarded local PostgreSQL 17 adoption to portable checkpoint T.

This command is intentionally restricted to the dedicated ephemeral test target.
It is not a managed, shared, staging, or production database bootstrap utility.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import tempfile
from collections.abc import Callable, Coroutine
from contextlib import contextmanager
from datetime import UTC, datetime
from getpass import getuser
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from drip.core.migration_checkpoint import (
    BASELINE_REVISION_ID,
    PG17_BOOTSTRAP_URL_PATTERN,
    PG17_TARGET_DATABASE,
    PG17_TEST_PORT,
    PG17_TEST_USER,
    T_REVISION_ID,
    CheckpointPreconditionError,
    assert_pg17_bootstrap_baseline,
    checkpoint_manifest,
    database_attestation,
    manifest_sha256,
    revision_tables,
    verify_0001_effects,
)
from sqlalchemy import Connection, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine
from sqlalchemy.pool import NullPool

API_ROOT = Path(__file__).resolve().parents[1] / "apps" / "api"
MIGRATION_LOCK_ID = 6_897_410_231_113_117
TOOL_VERSION = "batch-2b-2b-checkpoint-1"


def validate_target_url(raw_url: object) -> URL:
    """Accept only the URL shape emitted by the dedicated test harness."""
    if not isinstance(raw_url, str) or re.fullmatch(PG17_BOOTSTRAP_URL_PATTERN, raw_url) is None:
        raise CheckpointPreconditionError("PG17 bootstrap target configuration is invalid.")
    try:
        url = make_url(raw_url)
    except Exception:
        raise CheckpointPreconditionError("PG17 bootstrap target configuration is invalid.") from None
    if (
        url.drivername != "postgresql+asyncpg"
        or url.username != PG17_TEST_USER
        or url.host != "127.0.0.1"
        or url.port != PG17_TEST_PORT
        or url.database != PG17_TARGET_DATABASE
        or url.query
        or not url.password
    ):
        raise CheckpointPreconditionError("PG17 bootstrap target configuration is invalid.")
    return url


def _read_receipt(path: Path) -> dict[str, Any] | None:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError:
        raise CheckpointPreconditionError("PG17 bootstrap receipt cannot be read.") from None
    try:
        receipt = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise CheckpointPreconditionError("PG17 bootstrap receipt is invalid.") from None
    if not isinstance(receipt, dict) or receipt.get("operation") != "pg17_checkpoint_t":
        raise CheckpointPreconditionError("PG17 bootstrap receipt is invalid.")
    return receipt


def _write_receipt(path: Path, receipt: dict[str, Any], *, create: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(receipt, sort_keys=True, indent=2) + "\n"
    if create:
        # Exclusive creation prevents a stale receipt from being overwritten. A
        # partial file after interruption remains an invalid/manual-review state.
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            raise CheckpointPreconditionError("PG17 bootstrap receipt already exists.") from None
        except OSError:
            raise CheckpointPreconditionError("PG17 bootstrap receipt cannot be created.") from None
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
        except OSError:
            raise CheckpointPreconditionError("PG17 bootstrap receipt cannot be written.") from None
        return

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".pending", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except FileExistsError:
        raise CheckpointPreconditionError("PG17 bootstrap receipt update is already in progress.") from None
    except OSError:
        raise CheckpointPreconditionError("PG17 bootstrap receipt cannot be updated.") from None
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def _record_failure_if_absent(path: Path, category: str) -> None:
    """Retain a redacted failure receipt without replacing retry/reconciliation state."""
    if path.exists():
        return
    failure = {
        "format_version": 1,
        "operation": "pg17_checkpoint_t",
        "state": "preflight_rejected",
        "failure_category": category,
        "operator": getuser(),
        "tool_version": TOOL_VERSION,
        "occurred_at": datetime.now(UTC).isoformat(),
    }
    try:
        _write_receipt(path, failure, create=True)
    except (OSError, CheckpointPreconditionError):
        # Receipt failure must not replace the fixed safe diagnostic.
        return


def _target_record(attestation: dict[str, Any]) -> dict[str, Any]:
    return {
        "database_name": PG17_TARGET_DATABASE,
        "role_name": PG17_TEST_USER,
        "server_major": 17,
        "server_version_num": attestation["server_version_num"],
        "server_encoding": attestation["server_encoding"],
        "block_size": attestation["block_size"],
        "system_identifier": attestation["system_identifier"],
        "host": "127.0.0.1",
        "port": PG17_TEST_PORT,
    }


async def _check_existing_t(
    connection: AsyncConnection,
    receipt_path: Path,
    receipt: dict[str, Any] | None,
) -> bool:
    """Verify T against an existing receipt; returns true for a verified no-op."""
    def verify(sync_connection):
        target = _target_record(
            database_attestation(sync_connection, include_system_identifier=True)
        )
        manifest = checkpoint_manifest(sync_connection, T_REVISION_ID)
        return target, manifest

    target, manifest = await connection.run_sync(verify)
    if receipt is None or receipt.get("target") != target:
        raise CheckpointPreconditionError("Existing T has no matching bootstrap receipt.")
    if receipt.get("expected_t_manifest_sha256") != manifest_sha256(manifest):
        raise CheckpointPreconditionError("Existing T manifest does not match its receipt.")
    if receipt.get("state") == "pending":
        receipt["state"] = "succeeded"
        receipt["reconciled_after_unknown_outcome"] = True
        receipt["completed_at"] = datetime.now(UTC).isoformat()
        receipt["post_manifest"] = manifest
        _write_receipt(receipt_path, receipt)
    elif receipt.get("state") != "succeeded":
        raise CheckpointPreconditionError("Existing T receipt state is not valid.")
    return True


@contextmanager
def _migration_environment(database_url: str):
    controlled = {
        "ENVIRONMENT": "test",
        "DRIP_ENV_FILE": "",
        "DATABASE_URL": database_url,
    }
    original = {key: os.environ.get(key) for key in controlled}
    try:
        os.environ.update(controlled)
        yield
    finally:
        for key, value in original.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _alembic_config(connection) -> Config:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.attributes["connection"] = connection
    config.attributes["version_table_schema"] = "public"
    return config


async def _run_command(connection: AsyncConnection, operation: str, revision: str, url: str) -> None:
    def run(sync_connection) -> None:
        config = _alembic_config(sync_connection)
        with _migration_environment(url):
            if operation == "upgrade":
                command.upgrade(config, revision)
            elif operation == "stamp":
                command.stamp(config, revision)
            else:
                raise AssertionError("Unsupported internal Alembic operation.")

    await connection.run_sync(run)


def bootstrap(
    database_url: object,
    receipt_file: str | Path,
    *,
    before_stamp_hook: Callable[[Connection], None] | None = None,
) -> Coroutine[Any, Any, str]:
    """Validate the allowlisted URL synchronously, before engine or loop creation."""
    receipt_path = Path(receipt_file)
    try:
        url = validate_target_url(database_url)
    except CheckpointPreconditionError:
        _record_failure_if_absent(receipt_path, "target_configuration_rejected")
        raise
    return _bootstrap_with_failure_receipt(
        url,
        receipt_path,
        before_stamp_hook=before_stamp_hook,
    )


async def _bootstrap_with_failure_receipt(
    url: URL,
    receipt_path: Path,
    *,
    before_stamp_hook: Callable[[Connection], None] | None,
) -> str:
    try:
        return await _bootstrap_validated(
            url,
            receipt_path,
            before_stamp_hook=before_stamp_hook,
        )
    except CheckpointPreconditionError:
        _record_failure_if_absent(receipt_path, "target_or_migration_precondition_rejected")
        raise
    except Exception:
        _record_failure_if_absent(receipt_path, "database_operation_failed")
        raise


async def _bootstrap_validated(
    url: URL,
    receipt_file: str | Path,
    *,
    before_stamp_hook: Callable[[Connection], None] | None = None,
) -> str:
    url_for_settings = url.render_as_string(hide_password=False)
    receipt_path = Path(receipt_file)
    receipt = _read_receipt(receipt_path)
    engine = create_async_engine(
        url,
        poolclass=NullPool,
        connect_args={"timeout": 5.0, "command_timeout": 15.0},
    )
    try:
        async with engine.connect() as connection:
            target = _target_record(
                await connection.run_sync(
                    lambda sync_connection: database_attestation(
                        sync_connection, include_system_identifier=True
                    )
                )
            )
            current_revisions = await connection.run_sync(revision_tables)
            if current_revisions:
                # Only an exact, receipt-backed T may be accepted as an idempotent retry.
                if current_revisions != [{"schema_name": "public", "relation_kind": "r"}]:
                    raise CheckpointPreconditionError("Existing revision-table location is unexpected.")
                verified = await _check_existing_t(connection, receipt_path, receipt)
                if verified:
                    return "already_adopted"

            preflight = await connection.run_sync(assert_pg17_bootstrap_baseline)
            baseline_hash = manifest_sha256(preflight)
            if receipt is not None:
                if (
                    receipt.get("state") != "pending"
                    or receipt.get("target") != target
                    or receipt.get("baseline_manifest_sha256") != baseline_hash
                ):
                    raise CheckpointPreconditionError("Existing bootstrap receipt does not match target.")
            else:
                receipt = {
                    "format_version": 1,
                    "operation": "pg17_checkpoint_t",
                    "state": "pending",
                    "target": target,
                    "route": "guarded_local_pg17_fresh_bootstrap",
                    "operator": getuser(),
                    "tool_version": TOOL_VERSION,
                    "started_at": datetime.now(UTC).isoformat(),
                    "baseline_manifest": preflight,
                    "baseline_manifest_sha256": baseline_hash,
                    "note": "0001 executed; PG18-only 0002 assertion intentionally not run on PG17.",
                }
                _write_receipt(receipt_path, receipt, create=True)

        # Repeat all read-only checks under a bounded advisory lock before writes.
        async with engine.connect() as connection:
            async with connection.begin():
                await connection.execute(text("SET LOCAL lock_timeout = '5s'"))
                await connection.execute(text("SET LOCAL statement_timeout = '15s'"))
                await connection.execute(
                    text("SELECT pg_catalog.pg_advisory_xact_lock(:lock_id)"),
                    {"lock_id": MIGRATION_LOCK_ID},
                )
                locked_preflight = await connection.run_sync(assert_pg17_bootstrap_baseline)
                if manifest_sha256(locked_preflight) != baseline_hash:
                    raise CheckpointPreconditionError("PG17 bootstrap target changed after preflight.")

                await _run_command(connection, "upgrade", BASELINE_REVISION_ID, url_for_settings)
                verified_0001 = await connection.run_sync(
                    lambda sync_connection: verify_0001_effects(sync_connection, locked_preflight)
                )
                await connection.run_sync(
                    lambda sync_connection: _verify_expected_revision(
                        sync_connection, BASELINE_REVISION_ID
                    )
                )
                if before_stamp_hook is not None:
                    await connection.run_sync(before_stamp_hook)
                await _run_command(connection, "stamp", T_REVISION_ID, url_for_settings)
                post_manifest = await connection.run_sync(
                    lambda sync_connection: checkpoint_manifest(sync_connection, T_REVISION_ID)
                )
                receipt["extension_provenance"] = verified_0001["extension_provenance"]
                receipt["post_manifest"] = post_manifest
                receipt["expected_t_manifest_sha256"] = manifest_sha256(post_manifest)
                _write_receipt(receipt_path, receipt)

        # Commit completed. Re-attest on a new connection before reporting success.
        async with engine.connect() as connection:
            committed_target, committed_manifest = await connection.run_sync(
                lambda sync_connection: (
                    _target_record(
                        database_attestation(sync_connection, include_system_identifier=True)
                    ),
                    checkpoint_manifest(sync_connection, T_REVISION_ID),
                )
            )
        if committed_target != target or manifest_sha256(committed_manifest) != receipt.get(
            "expected_t_manifest_sha256"
        ):
            raise CheckpointPreconditionError("Post-commit checkpoint verification failed.")
        receipt["state"] = "succeeded"
        receipt["completed_at"] = datetime.now(UTC).isoformat()
        _write_receipt(receipt_path, receipt)
        return "adopted"
    finally:
        await engine.dispose()


def _verify_expected_revision(connection, expected_revision: str) -> None:
    from drip.core.migration_checkpoint import revision_tables

    if revision_tables(connection) != [{"schema_name": "public", "relation_kind": "r"}]:
        raise CheckpointPreconditionError("Bootstrap revision-table location changed unexpectedly.")
    rows = connection.execute(
        text("SELECT version_num FROM public.alembic_version ORDER BY version_num")
    ).scalars().all()
    if rows != [expected_revision]:
        raise CheckpointPreconditionError("Bootstrap revision state is unexpected.")


async def _main(receipt_path: Path) -> int:
    raw_url = os.environ.get("DRIP_PG17_BOOTSTRAP_DATABASE_URL")
    try:
        result = await bootstrap(raw_url, receipt_path)
    except CheckpointPreconditionError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except Exception as exc:
        # Exception messages can contain driver URLs or SQL parameters; log only its type.
        print(f"PG17 bootstrap failed safely ({type(exc).__name__}).", file=sys.stderr)
        return 1
    print(f"PG17 checkpoint operation completed: {result}.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", required=True, type=Path)
    args = parser.parse_args()
    return asyncio.run(_main(args.receipt))


if __name__ == "__main__":
    raise SystemExit(main())
