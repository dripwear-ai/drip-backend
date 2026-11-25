from __future__ import annotations

import hashlib
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

API_ROOT = Path(__file__).resolve().parents[1]
MIGRATION = API_ROOT / "migrations" / "versions" / "0004_identity_foundation.py"


def test_identity_migration_follows_checkpoint_and_catalog_is_current_head():
    scripts = ScriptDirectory.from_config(Config(str(API_ROOT / "alembic.ini")))
    migration = scripts.get_revision("0004_identity_foundation")

    assert migration is not None
    assert migration.down_revision == "0003_portable_identity_ckpt"
    assert scripts.get_heads() == ["0006_curated_outfits"]


def test_identity_migration_keeps_historical_migration_bytes_unchanged():
    versions = API_ROOT / "migrations" / "versions"
    expected = {
        "0001_initial_baseline.py": "5afd9c6f9c87b3f1b761b0ce8c07d79a00c816e5c62353248bb94f699e173e6f",
        "0002_require_pg18_uuidv7.py": "18e648442007bbc03d403242d2d3530ecbdb3f805e6c66c8405e6defb769c624",
    }
    assert {
        name: hashlib.sha256((versions / name).read_bytes()).hexdigest()
        for name in expected
    } == expected


def test_identity_migration_is_fail_closed_and_has_no_role_creation_or_client_identity_key():
    source = MIGRATION.read_text(encoding="utf-8")
    preflight = source.index("op.execute(_PREFLIGHT)")
    ddl_loop = source.index("for statement in _UPGRADE_DDL:")

    assert "server_encoding" in source
    assert "requires UTF8" in source
    assert "current_user <> 'drip_identity_migrator'" in source
    assert "CREATE ROLE" not in source.upper()
    assert "AND NOT ROLBYPASSRLS" in source.upper()
    assert "FORCE ROW LEVEL SECURITY" in source
    assert "0003_portable_identity_ckpt" in source
    assert "email" not in source.lower()
    assert preflight < ddl_loop


def test_identity_migration_uses_exact_private_capabilities_and_no_table_uuid_default():
    source = MIGRATION.read_text(encoding="utf-8")

    assert "CREATE TABLE drip_identity.users" in source
    assert "CREATE TABLE drip_identity.external_identities" in source
    assert "DEFAULT 'disabled'" in source
    assert "get_byte(pg_catalog.uuid_send(id), 6)" in source
    assert 'issuer text COLLATE "C"' in source
    assert 'subject text COLLATE "C"' in source
    assert "octet_length(issuer) BETWEEN 1 AND 260" in source
    assert "octet_length(subject) BETWEEN 1 AND 1024" in source
    assert "ON UPDATE RESTRICT ON DELETE RESTRICT" in source
    assert "CREATE FUNCTION drip_identity.lookup_identity" in source
    assert "CREATE FUNCTION drip_identity.register_identity" in source
    assert "CREATE FUNCTION drip_identity.identity_tables_empty_for_migration" in source
    assert "GRANT EXECUTE ON FUNCTION drip_identity.lookup_identity(text, text, text) TO drip_identity_runtime" in source
    assert "GRANT EXECUTE ON FUNCTION drip_identity.register_identity(uuid, text, text, text) TO drip_identity_runtime" in source
    assert "identity_tables_empty_for_migration() TO drip_identity_migrator" in source
    assert "DEFAULT pg_catalog.uuidv7" not in source


def test_identity_downgrade_requires_empty_tables_and_does_not_cascade():
    source = MIGRATION.read_text(encoding="utf-8")

    assert "FROM drip_identity.identity_tables_empty_for_migration()" in source
    assert "if not empty[\"users_empty\"] or not empty[\"external_identities_empty\"]" in source
    assert '"DROP TABLE drip_identity.external_identities"' in source
    assert '"DROP TABLE drip_identity.users"' in source
    assert "CASCADE" not in source.upper()
