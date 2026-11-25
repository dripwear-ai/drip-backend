import io
from pathlib import Path

from alembic import command
from alembic.config import Config
from drip.core.config import settings
from drip.models.base import UUIDPrimaryKeyMixin
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.schema import CreateTable

API_ROOT = Path(__file__).resolve().parents[1]


class ProbeBase(DeclarativeBase):
    pass


class UUIDProbe(UUIDPrimaryKeyMixin, ProbeBase):
    __tablename__ = "gate_b_uuid_probe"
    __table_args__ = {"prefixes": ["TEMPORARY"]}


def test_uuid_primary_key_is_exclusively_server_generated_v7():
    column = UUIDProbe.__table__.c.id
    assert column.default is None
    assert str(column.server_default.arg) == "uuidv7()"
    ddl = str(CreateTable(UUIDProbe.__table__).compile(dialect=postgresql.dialect()))
    assert "DEFAULT uuidv7()" in ddl
    assert "uuid4" not in ddl
    assert "gen_random_uuid" not in ddl


def test_offline_migrations_accept_percent_encoded_credentials(monkeypatch):
    # Exercise the real env.py path through Alembic, without a database connection.
    url = "postgresql+asyncpg://synthetic:pa%40ss%25word%2Fonly@localhost/drip_test"
    monkeypatch.setattr(settings, "DATABASE_URL", url)
    output = io.StringIO()
    config = Config(str(API_ROOT / "alembic.ini"), output_buffer=output)
    # The historical chain remains renderable offline; T requires online preflight.
    command.upgrade(config, "0002_require_pg18_uuidv7", sql=True)
    assert config.get_main_option("sqlalchemy.url") == url
    sql = output.getvalue()
    assert "CREATE EXTENSION IF NOT EXISTS pgcrypto" in sql
    assert "pg_catalog.uuidv7()" in sql
    assert "0002_require_pg18_uuidv7" in sql
    assert "pa%40ss" not in sql
