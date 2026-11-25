"""Curated editorial outfits over the authoritative DRIP catalog."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from drip.core.identifiers import new_uuid7
from drip.models.base import Base
from drip.models.catalog import Brand

CATALOG_SCHEMA = "drip_catalog"


class Outfit(Base):
    __tablename__ = "outfits"
    __table_args__ = (
        CheckConstraint("length(title) BETWEEN 1 AND 160", name="ck_catalog_outfit_title_length"),
        CheckConstraint("length(caption) <= 2000", name="ck_catalog_outfit_caption_length"),
        CheckConstraint("length(image_url) <= 2048 AND image_url LIKE 'https://%'", name="ck_catalog_outfit_https_image"),
        CheckConstraint("length(image_alt) BETWEEN 1 AND 240", name="ck_catalog_outfit_image_alt"),
        CheckConstraint("length(rights_ref) BETWEEN 1 AND 200", name="ck_catalog_outfit_rights_ref"),
        CheckConstraint("length(approval_ref) BETWEEN 1 AND 200", name="ck_catalog_outfit_approval_ref"),
        CheckConstraint("status IN ('draft','published','archived')", name="ck_catalog_outfit_status"),
        CheckConstraint("revision > 0", name="ck_catalog_outfit_revision"),
        CheckConstraint("(status = 'published' AND published_at IS NOT NULL) OR status <> 'published'", name="ck_catalog_outfit_published_at"),
        Index("ix_catalog_outfit_brand", "brand_id"),
        Index("ix_catalog_outfit_feed", "status", text("published_at DESC"), text("id DESC")),
        {"schema": CATALOG_SCHEMA},
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=new_uuid7)
    brand_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey(f"{CATALOG_SCHEMA}.brands.id", ondelete="RESTRICT"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    caption: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    image_url: Mapped[str] = mapped_column(Text, nullable=False)
    image_alt: Mapped[str] = mapped_column(String(240), nullable=False)
    rights_ref: Mapped[str] = mapped_column(String(200), nullable=False)
    approval_ref: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'draft'"))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revision: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    items: Mapped[list[OutfitItem]] = relationship(
        back_populates="outfit",
        order_by="OutfitItem.position",
        cascade="all, delete-orphan",
    )
    brand: Mapped[Brand] = relationship()


class OutfitItem(Base):
    __tablename__ = "outfit_items"
    __table_args__ = (
        CheckConstraint("position BETWEEN 1 AND 8", name="ck_catalog_outfit_item_position"),
        UniqueConstraint("outfit_id", "product_id", name="uq_catalog_outfit_item_product"),
        Index("ix_catalog_outfit_item_product", "product_id"),
        {"schema": CATALOG_SCHEMA},
    )

    outfit_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey(f"{CATALOG_SCHEMA}.outfits.id", ondelete="RESTRICT"), primary_key=True
    )
    position: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    product_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey(f"{CATALOG_SCHEMA}.products.id", ondelete="RESTRICT"), nullable=False
    )

    outfit: Mapped[Outfit] = relationship(back_populates="items")


class OutfitPublication(Base):
    __tablename__ = "outfit_publications"
    __table_args__ = (
        CheckConstraint("manifest_sha256 ~ '^[0-9a-f]{64}$'", name="ck_catalog_outfit_publication_digest"),
        CheckConstraint("action IN ('publish','update','archive')", name="ck_catalog_outfit_publication_action"),
        CheckConstraint("next_revision > 0 AND (prior_revision IS NULL OR prior_revision > 0)", name="ck_catalog_outfit_publication_revision"),
        Index("ix_catalog_outfit_publication_history", "outfit_id", "recorded_at"),
        {"schema": CATALOG_SCHEMA},
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=new_uuid7)
    outfit_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey(f"{CATALOG_SCHEMA}.outfits.id", ondelete="RESTRICT"), nullable=False
    )
    request_key: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, unique=True)
    manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_ref: Mapped[str] = mapped_column(String(80), nullable=False)
    approval_ref: Mapped[str] = mapped_column(String(200), nullable=False)
    prior_revision: Mapped[int | None] = mapped_column(BigInteger)
    next_revision: Mapped[int] = mapped_column(BigInteger, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
