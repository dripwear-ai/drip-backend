import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Authoritative base class for all DRIP 2.0 database entities.

    ENGINEERING RULES:
    1. PostgreSQL is the single source of truth. Redis is strictly ephemeral.
    2. Primary keys use UUID (with PostgreSQL 18 native uuidv7() where available).
    3. Monetary values MUST be modeled as integer minor units (BIGINT paise/cents) or Numeric.
       Binary floating-point arithmetic (Float) is strictly forbidden.
    4. Every entity lifecycle requires audit timestamps (created_at, updated_at).
    """

    pass


class TimestampMixin:
    """Mixin providing standardized UTC creation and update timestamps."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=text("CURRENT_TIMESTAMP"),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )


class UUIDPrimaryKeyMixin:
    """Mixin providing standardized UUID primary key.

    PostgreSQL 18 generates UUIDv7 for both ORM and direct SQL inserts.
    """

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuidv7()"),
    )
