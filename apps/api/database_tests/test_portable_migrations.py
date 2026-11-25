from __future__ import annotations

import hashlib
import importlib
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from drip.core.migration_checkpoint import (
    PARENT_REVISION_ID,
    T_REVISION_ID,
    CheckpointPreconditionError,
    assert_pg17_bootstrap_baseline,
    database_attestation,
)
from scripts import bootstrap_identity_database as bootstrap_module

API_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = API_ROOT.parents[1]
HISTORICAL_HASHES = {
    "0001_initial_baseline.py": "5afd9c6f9c87b3f1b761b0ce8c07d79a00c816e5c62353248bb94f699e173e6f",
    "0002_require_pg18_uuidv7.py": "18e648442007bbc03d403242d2d3530ecbdb3f805e6c66c8405e6defb769c624",
}
TEST_URL = (
    f"postgresql+asyncpg://drip_pg17_test:{'a' * 64}"
    "@127.0.0.1:55436/drip_pg17_target"
)


def test_migration_graph_and_revision_storage_width():
    config = Config(str(API_ROOT / "alembic.ini"))
    scripts = ScriptDirectory.from_config(config)
    checkpoint = scripts.get_revision(T_REVISION_ID)

    assert checkpoint is not None
    assert checkpoint.revision == "0003_portable_identity_ckpt"
    assert len(checkpoint.revision) == 27
    assert checkpoint.down_revision == PARENT_REVISION_ID
    assert scripts.get_revision(PARENT_REVISION_ID).down_revision == "0001_initial_baseline"
    version_table = MigrationContext.configure(dialect_name="postgresql").impl.version_table_impl(
        version_table="alembic_version",
        version_table_schema="public",
        version_table_pk=True,
    )
    assert version_table.c.version_num.type.length == 32
    assert len(checkpoint.revision) <= version_table.c.version_num.type.length
    assert checkpoint.path.endswith("0003_portable_identity_checkpoint.py")


def test_historical_migration_hashes_match_pre_implementation_worktree():
    migration_dir = API_ROOT / "migrations" / "versions"
    for filename, expected_hash in HISTORICAL_HASHES.items():
        actual_hash = hashlib.sha256((migration_dir / filename).read_bytes()).hexdigest()
        assert actual_hash == expected_hash


def test_checkpoint_declares_no_domain_ddl_or_uuidv7_default():
    path = API_ROOT / "migrations" / "versions" / "0003_portable_identity_checkpoint.py"
    source = path.read_text(encoding="utf-8")

    assert "revision: str = T_REVISION_ID" in source
    assert "down_revision: str | None = PARENT_REVISION_ID" in source
    assert "verify_checkpoint(op.get_bind(), expected_revision=PARENT_REVISION_ID)" in source
    assert "op.create_table" not in source
    assert "uuidv7()" not in source
    assert "create_schema" not in source


def test_alembic_defaults_version_table_to_public():
    source = (API_ROOT / "migrations" / "env.py").read_text(encoding="utf-8")
    assert 'config.attributes.get("version_table_schema", "public")' in source


def test_pg17_harness_is_digest_pinned_ephemeral_and_loopback_only():
    compose = (REPO_ROOT / "infra" / "compose.pg17-test.yml").read_text(encoding="utf-8")
    runner = (REPO_ROOT / "scripts" / "test_pg17_migrations.ps1").read_text(encoding="utf-8")

    assert "postgres:17.12-alpine3.24@sha256:34261f594522cf41dfcb76aefd42b9d201098b0e6b23c9c68733f169e4218b6f" in compose
    assert "127.0.0.1:55436:5432" in compose
    assert "tmpfs:" in compose
    assert "volumes:" not in compose
    assert "[guid]::NewGuid()" in runner
    assert "docker compose -p $project" in runner
    assert "docker compose -p $project -f $composeFile down" in runner
    assert "down -v" not in runner


def test_offline_upgrade_to_checkpoint_fails_closed(monkeypatch):
    monkeypatch.setattr(
        "drip.core.config.settings.DATABASE_URL",
        "postgresql+asyncpg://synthetic:password@127.0.0.1/drip_test",
    )
    config = Config(str(API_ROOT / "alembic.ini"))
    with pytest.raises(RuntimeError, match="requires an online database preflight"):
        command.upgrade(config, T_REVISION_ID, sql=True)


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        "not-a-url",
        "postgresql://drip_pg17_test:secret@127.0.0.1:55436/drip_pg17_target",
        "postgresql+asyncpg://drip_pg17_test:secret@localhost:55436/drip_pg17_target",
        "postgresql+asyncpg://drip_pg17_test:secret@127.0.0.1:55435/drip_pg17_target",
        "postgresql+asyncpg://drip_pg17_test:secret@127.0.0.1:55436/other_db",
        TEST_URL + "?ssl=false",
        TEST_URL + "#fragment",
        TEST_URL.replace("127.0.0.1", "127.0.0.1.evil"),
        TEST_URL.replace("drip_pg17_test:", "drip_pg17_test@"),
    ],
    ids=[
        "missing",
        "empty",
        "malformed",
        "scheme",
        "host",
        "port",
        "database",
        "query",
        "fragment",
        "host-suffix",
        "authority",
    ],
)
def test_bootstrap_rejects_ambiguous_target_without_creating_engine(value, monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(
        bootstrap_module, "create_async_engine", lambda *args, **kwargs: calls.append(args)
    )

    with pytest.raises(bootstrap_module.CheckpointPreconditionError) as error:
        bootstrap_module.bootstrap(value, tmp_path / "receipt.json")

    assert calls == []
    assert "secret" not in str(error.value)
    assert "postgresql" not in str(error.value)
    receipt = (tmp_path / "receipt.json").read_text(encoding="utf-8")
    assert '"state": "preflight_rejected"' in receipt
    assert "secret" not in receipt
    assert "postgresql" not in receipt


def test_bootstrap_accepts_only_the_exact_harness_target_shape():
    parsed = bootstrap_module.validate_target_url(TEST_URL)
    assert parsed.drivername == "postgresql+asyncpg"
    assert parsed.username == "drip_pg17_test"
    assert parsed.host == "127.0.0.1"
    assert parsed.port == 55436
    assert parsed.database == "drip_pg17_target"


def test_import_does_not_create_database_engine(monkeypatch):
    import sqlalchemy.ext.asyncio
    original_factory = bootstrap_module.create_async_engine

    def forbidden(*args, **kwargs):
        raise AssertionError("Import attempted to create an engine.")

    monkeypatch.setattr(sqlalchemy.ext.asyncio, "create_async_engine", forbidden)
    importlib.reload(bootstrap_module)
    monkeypatch.setattr(bootstrap_module, "create_async_engine", original_factory)


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def __iter__(self):
        return iter(self._rows)


class _AttestationConnection:
    def __init__(self, version_num: int, encoding: str):
        self.version_num = version_num
        self.encoding = encoding

    def execute(self, _statement, _params=None):
        return _FakeResult(
            [
                {
                    "database_name": "drip_pg17_target",
                    "role_name": "drip_pg17_test",
                    "server_version_num": self.version_num,
                    "server_encoding": self.encoding,
                    "block_size": 8192,
                    "server_address": "127.0.0.1",
                    "system_identifier": "synthetic-test-identifier",
                }
            ]
        )


def test_pg17_preflight_rejects_other_major_before_catalog_inspection():
    connection = _AttestationConnection(version_num=180006, encoding="UTF8")
    with pytest.raises(CheckpointPreconditionError, match="requires PostgreSQL 17"):
        assert_pg17_bootstrap_baseline(connection)


def test_attestation_rejects_non_utf8_before_bootstrap_writes():
    connection = _AttestationConnection(version_num=170012, encoding="SQL_ASCII")
    with pytest.raises(CheckpointPreconditionError, match="encoding is unsupported"):
        database_attestation(connection, include_system_identifier=True)


def test_receipt_writer_refuses_to_overwrite_existing_file(tmp_path):
    receipt_path = tmp_path / "receipt.json"
    receipt = {"operation": "pg17_checkpoint_t", "state": "pending"}
    bootstrap_module._write_receipt(receipt_path, receipt, create=True)
    before = receipt_path.read_bytes()

    with pytest.raises(CheckpointPreconditionError, match="receipt already exists"):
        bootstrap_module._write_receipt(receipt_path, {"state": "replacement"}, create=True)

    assert receipt_path.read_bytes() == before


def test_receipt_diagnostics_never_echo_url_or_password(tmp_path):
    receipt_path = tmp_path / "receipt.json"
    receipt_path.write_text("postgresql+asyncpg://synthetic:do-not-log@host/db", encoding="utf-8")
    with pytest.raises(CheckpointPreconditionError) as error:
        bootstrap_module._read_receipt(receipt_path)
    assert "do-not-log" not in str(error.value)
    assert "postgresql" not in str(error.value)
