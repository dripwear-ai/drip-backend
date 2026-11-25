"""SQLAlchemy metadata for DRIP's private identity foundation.

This module declares storage shape only. It does not create the PostgreSQL
schema, enforce privileges/RLS, or implement identity registration.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    PrimaryKeyConstraint,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from drip.core.identifiers import new_uuid7
from drip.models.base import Base

IDENTITY_SCHEMA = "drip_identity"


class IdentityUser(Base):
    """DRIP-owned internal user row; metadata only, not an authorization grant."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'disabled', 'deletion_pending')",
            name="ck_identity_users_status",
        ),
        CheckConstraint(
            "((get_byte(uuid_send(id), 6) >> 4) = 7)",
            name="ck_identity_users_uuid_v7",
        ),
        CheckConstraint(
            "((get_byte(uuid_send(id), 8) & 192) = 128)",
            name="ck_identity_users_uuid_rfc_variant",
        ),
        CheckConstraint(
            "updated_at >= created_at",
            name="ck_identity_users_updated_at_order",
        ),
        {"schema": IDENTITY_SCHEMA},
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=new_uuid7,
        nullable=False,
        info={"immutable": True, "identifier_owner": "application"},
    )
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'disabled'"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        info={"immutable": True, "timestamp_owner": "database"},
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        info={
            "timestamp_owner": "database",
            "update_policy": "database-trigger-required-in-later-slice",
        },
    )


class ExternalIdentityMapping(Base):
    """Exact Auth0 issuer/subject binding to one DRIP-owned user."""

    __tablename__ = "external_identities"
    __table_args__ = (
        PrimaryKeyConstraint("issuer", "subject", name="pk_identity_external_identity"),
        UniqueConstraint("user_id", name="uq_identity_external_identity_user_id"),
        CheckConstraint(
            "octet_length(issuer) BETWEEN 1 AND 260 "
            "AND issuer ~ '^https://([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?[.])+"
            "[a-z]{2,63}/$'",
            name="ck_identity_external_issuer_format",
        ),
        CheckConstraint(
            "octet_length(subject) BETWEEN 1 AND 1024 "
            "AND subject ~ '[^[:space:]]'",
            name="ck_identity_external_subject_bytes",
        ),
        CheckConstraint(
            "provider = 'auth0'",
            name="ck_identity_external_provider",
        ),
        CheckConstraint(
            "updated_at = created_at",
            name="ck_identity_external_timestamps_equal",
        ),
        {"schema": IDENTITY_SCHEMA},
    )

    issuer: Mapped[str] = mapped_column(
        Text(collation="C"),
        nullable=False,
        info={"immutable": True},
    )
    subject: Mapped[str] = mapped_column(
        Text(collation="C"),
        nullable=False,
        info={"immutable": True},
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            f"{IDENTITY_SCHEMA}.users.id",
            name="fk_identity_external_identity_user_id",
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        nullable=False,
        info={"immutable": True},
    )
    provider: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        info={"immutable": True},
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        info={"immutable": True, "timestamp_owner": "database"},
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        info={"immutable": True, "timestamp_owner": "database"},
    )
