"""Database-free contract checks for identity SQLAlchemy metadata."""

from inspect import unwrap
from typing import cast
from uuid import RFC_4122, UUID

from drip.core.identifiers import new_uuid7
from drip.models import Base, ExternalIdentityMapping, IdentityUser
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.dialects.postgresql import dialect
from sqlalchemy.schema import CreateTable

SCHEMA = "drip_identity"


def _checks(table: Table) -> dict[str, str]:
    checks: dict[str, str] = {}
    for constraint in table.constraints:
        if isinstance(constraint, CheckConstraint):
            assert constraint.name is not None
            checks[cast(str, constraint.name)] = " ".join(
                str(constraint.sqltext).split()
            )
    return checks


def test_identity_tables_are_registered_in_the_private_schema() -> None:
    assert IdentityUser.__table__ in Base.metadata.tables.values()
    assert ExternalIdentityMapping.__table__ in Base.metadata.tables.values()
    assert IdentityUser.__table__.fullname == f"{SCHEMA}.users"
    assert ExternalIdentityMapping.__table__.fullname == f"{SCHEMA}.external_identities"


def test_user_columns_defaults_and_uuid7_generation_contract() -> None:
    table = IdentityUser.__table__
    user_id = table.c.id
    assert isinstance(user_id.type, PG_UUID)
    assert user_id.type.as_uuid is True
    assert user_id.primary_key and not user_id.nullable
    assert user_id.default is not None and unwrap(user_id.default.arg) is new_uuid7
    assert user_id.server_default is None

    generated = unwrap(user_id.default.arg)()
    assert isinstance(generated, UUID)
    assert generated.version == 7
    assert generated.variant == RFC_4122

    assert table.c.status.server_default is not None
    assert str(table.c.status.server_default.arg) == "'disabled'"
    assert isinstance(table.c.created_at.type, DateTime)
    assert isinstance(table.c.updated_at.type, DateTime)
    assert table.c.created_at.type.timezone is True
    assert table.c.updated_at.type.timezone is True
    assert table.c.created_at.server_default is not None
    assert table.c.updated_at.server_default is not None
    assert table.c.id.info["immutable"] is True
    assert table.c.created_at.info["immutable"] is True
    assert table.c.updated_at.info["update_policy"] == (
        "database-trigger-required-in-later-slice"
    )

    checks = _checks(table)
    assert "active" in checks["ck_identity_users_status"]
    assert "disabled" in checks["ck_identity_users_status"]
    assert "deletion_pending" in checks["ck_identity_users_status"]
    assert "uuid_send" in checks["ck_identity_users_uuid_v7"]
    assert "uuid_send" in checks["ck_identity_users_uuid_rfc_variant"]
    assert "updated_at >= created_at" in checks["ck_identity_users_updated_at_order"]


def test_external_identity_has_exact_composite_key_and_one_identity_per_user() -> None:
    table = ExternalIdentityMapping.__table__
    assert [column.name for column in table.primary_key.columns] == ["issuer", "subject"]
    assert isinstance(table.c.issuer.type, Text)
    assert isinstance(table.c.subject.type, Text)
    assert table.c.issuer.type.collation == "C"
    assert table.c.subject.type.collation == "C"
    assert not table.c.issuer.nullable
    assert not table.c.subject.nullable
    assert not table.c.provider.nullable
    assert not table.c.user_id.nullable

    unique_user_constraints = [
        constraint
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
        and [column.name for column in constraint.columns] == ["user_id"]
    ]
    assert len(unique_user_constraints) == 1
    assert unique_user_constraints[0].name == "uq_identity_external_identity_user_id"

    foreign_keys = [
        constraint
        for constraint in table.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    ]
    assert len(foreign_keys) == 1
    foreign_key = foreign_keys[0]
    assert foreign_key.elements[0].target_fullname == f"{SCHEMA}.users.id"
    assert foreign_key.onupdate == "RESTRICT"
    assert foreign_key.ondelete == "RESTRICT"

    checks = _checks(table)
    assert checks["ck_identity_external_issuer_format"] == (
        "octet_length(issuer) BETWEEN 1 AND 260 AND issuer ~ "
        "'^https://([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?[.])+[a-z]{2,63}/$'"
    )
    assert checks["ck_identity_external_subject_bytes"] == (
        "octet_length(subject) BETWEEN 1 AND 1024 AND subject ~ '[^[:space:]]'"
    )
    assert checks["ck_identity_external_provider"] == "provider = 'auth0'"
    assert checks["ck_identity_external_timestamps_equal"] == "updated_at = created_at"
    assert all(column.info["immutable"] is True for column in table.columns)
    assert table.c.created_at.server_default is not None
    assert table.c.updated_at.server_default is not None


def test_metadata_ddl_has_no_database_uuid_generator_or_security_objects() -> None:
    pg_dialect = dialect()  # type: ignore[no-untyped-call]
    user_ddl = str(CreateTable(IdentityUser.__table__).compile(dialect=pg_dialect))
    mapping_ddl = str(
        CreateTable(ExternalIdentityMapping.__table__).compile(dialect=pg_dialect)
    )

    assert 'CREATE TABLE drip_identity.users' in user_ddl
    assert 'CREATE TABLE drip_identity.external_identities' in mapping_ddl
    assert "uuidv7()" not in user_ddl
    assert "DEFAULT uuidv7()" not in user_ddl
    assert "CREATE POLICY" not in user_ddl + mapping_ddl
    assert "CREATE TRIGGER" not in user_ddl + mapping_ddl
