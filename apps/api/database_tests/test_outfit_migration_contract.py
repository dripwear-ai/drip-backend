from __future__ import annotations

import importlib.util
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from drip.models.base import Base
from sqlalchemy import Column, MetaData, Table
from sqlalchemy.dialects.postgresql import UUID

API_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = API_ROOT / "migrations" / "versions" / "0006_curated_outfits.py"


def _load_migration():
    spec = importlib.util.spec_from_file_location("curated_outfits_migration", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_outfit_migration_extends_catalog_as_current_head():
    script = ScriptDirectory.from_config(Config(str(API_ROOT / "alembic.ini")))
    revision = script.get_revision("0006_curated_outfits")
    assert revision is not None
    assert revision.down_revision == "0005_catalog_foundation"
    assert script.get_current_head() == "0006_curated_outfits"
    assert _load_migration().revision == "0006_curated_outfits"


def test_outfit_migration_and_metadata_have_the_same_tables_and_columns():
    migration = _load_migration()
    created: dict[str, set[str]] = {}
    migration_metadata = MetaData()
    Table("products", migration_metadata, Column("id", UUID(as_uuid=True), primary_key=True), schema="drip_catalog")
    Table("brands", migration_metadata, Column("id", UUID(as_uuid=True), primary_key=True), schema="drip_catalog")

    class OperationsRecorder:
        @staticmethod
        def execute(_statement: str) -> None:
            return None

        @staticmethod
        def create_table(name, *elements, **kwargs) -> None:
            table = Table(name, migration_metadata, *elements, **kwargs)
            created[name] = set(table.columns.keys())

        @staticmethod
        def create_foreign_key(*_args, **_kwargs) -> None:
            return None

        @staticmethod
        def create_index(*_args, **_kwargs) -> None:
            return None

    migration.op = OperationsRecorder()
    migration.upgrade()
    expected = {
        table.name: set(table.columns.keys())
        for table in Base.metadata.tables.values()
        if table.schema == "drip_catalog"
        and table.name in {"outfits", "outfit_items", "outfit_publications"}
    }
    assert created == expected


def test_outfit_migration_grants_runtime_only_read_access_to_public_feed_tables():
    source = MIGRATION_PATH.read_text(encoding="utf-8")
    assert "GRANT SELECT ON TABLE drip_catalog.outfits, drip_catalog.outfit_items TO drip_identity_runtime" in source
    assert "drip_catalog.outfit_publications TO drip_identity_runtime" not in source
    assert "REVOKE ALL ON TABLE drip_catalog.outfits, drip_catalog.outfit_items, drip_catalog.outfit_publications FROM PUBLIC" in source
