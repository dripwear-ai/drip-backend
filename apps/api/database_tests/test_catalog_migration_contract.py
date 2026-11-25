from __future__ import annotations

import importlib.util
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from drip.models.base import Base
from sqlalchemy import MetaData, Table

API_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = API_ROOT / "migrations" / "versions" / "0005_catalog_foundation.py"


def _load_migration():
    spec = importlib.util.spec_from_file_location("catalog_foundation_migration", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_catalog_migration_is_followed_by_the_curated_outfit_revision():
    config = Config(str(API_ROOT / "alembic.ini"))
    script = ScriptDirectory.from_config(config)
    revision = script.get_revision("0005_catalog_foundation")
    assert revision is not None
    assert revision.down_revision == "0004_identity_foundation"
    assert script.get_current_head() == "0006_curated_outfits"
    assert _load_migration().revision == "0005_catalog_foundation"


def test_migration_and_sqlalchemy_share_catalog_table_column_contract():
    migration = _load_migration()
    created: dict[str, set[str]] = {}
    migration_metadata = MetaData()

    class OperationsRecorder:
        @staticmethod
        def execute(statement: str) -> None:
            assert isinstance(statement, str)

        @staticmethod
        def create_table(name, *elements, **kwargs) -> None:
            table = Table(name, migration_metadata, *elements, **kwargs)
            created[name] = set(table.columns.keys())

        @staticmethod
        def create_foreign_key(*args, **kwargs) -> None:
            return None

        @staticmethod
        def create_index(*args, **kwargs) -> None:
            return None

    migration.op = OperationsRecorder()
    migration.upgrade()

    expected = {
        table.name: set(table.columns.keys())
        for table in Base.metadata.tables.values()
        if table.schema == "drip_catalog"
        and table.name in {"brands", "merchants", "publications", "products", "listings", "variants", "prices"}
    }
    assert created == expected
