"""Authoritative catalog metadata. No catalog rows are seeded by this module."""

from __future__ import annotations

from datetime import datetime
from typing import Any
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
from sqlalchemy.dialects.postgresql import ARRAY, CHAR, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from drip.core.identifiers import new_uuid7
from drip.models.base import Base

CATALOG_SCHEMA = "drip_catalog"


class CatalogTimestamps:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), onupdate=text("CURRENT_TIMESTAMP"), nullable=False)


class Brand(CatalogTimestamps, Base):
    __tablename__ = "brands"
    __table_args__ = (
        CheckConstraint("status IN ('active','archived')", name="ck_catalog_brand_status"),
        CheckConstraint("revision > 0", name="ck_catalog_brand_revision"),
        {"schema": CATALOG_SCHEMA},
    )
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=new_uuid7)
    slug: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'active'"))
    source_ref: Mapped[str] = mapped_column(String(200), nullable=False)
    reviewer_ref: Mapped[str] = mapped_column(String(80), nullable=False)
    revision: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("1"))
    products: Mapped[list[CanonicalProduct]] = relationship(back_populates="brand")


class Merchant(CatalogTimestamps, Base):
    __tablename__ = "merchants"
    __table_args__ = (
        CheckConstraint("status IN ('active','suspended')", name="ck_catalog_merchant_status"),
        CheckConstraint("purchase_mode = 'external_redirect'", name="ck_catalog_merchant_purchase_mode"),
        CheckConstraint("cardinality(allowed_destination_hosts) BETWEEN 1 AND 20", name="ck_catalog_merchant_destination_hosts"),
        CheckConstraint("cardinality(allowed_image_hosts) BETWEEN 1 AND 20", name="ck_catalog_merchant_image_hosts"),
        CheckConstraint("revision > 0", name="ck_catalog_merchant_revision"),
        {"schema": CATALOG_SCHEMA},
    )
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=new_uuid7)
    slug: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'active'"))
    purchase_mode: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'external_redirect'"))
    allowed_destination_hosts: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    allowed_image_hosts: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    source_ref: Mapped[str] = mapped_column(String(200), nullable=False)
    reviewer_ref: Mapped[str] = mapped_column(String(80), nullable=False)
    revision: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("1"))
    listings: Mapped[list[MerchantListing]] = relationship(back_populates="merchant")


class CatalogPublication(CatalogTimestamps, Base):
    __tablename__ = "publications"
    __table_args__ = (
        CheckConstraint("status IN ('applied','revoked')", name="ck_catalog_publication_status"),
        CheckConstraint("manifest_sha256 ~ '^[0-9a-f]{64}$'", name="ck_catalog_publication_digest"),
        CheckConstraint("(status = 'applied' AND revoked_at IS NULL) OR (status = 'revoked' AND revoked_at IS NOT NULL)", name="ck_catalog_publication_revocation"),
        Index("ix_catalog_publication_merchant_applied", "merchant_id", "applied_at"),
        {"schema": CATALOG_SCHEMA},
    )
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=new_uuid7)
    merchant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey(f"{CATALOG_SCHEMA}.merchants.id", ondelete="RESTRICT"), nullable=False)
    request_key: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, unique=True)
    manifest_sha256: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    schema_version: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    reviewer_ref: Mapped[str] = mapped_column(String(80), nullable=False)
    approval_ref: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'applied'"))
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revocation_audit: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    change_summary: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    supersedes_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey(f"{CATALOG_SCHEMA}.publications.id", ondelete="RESTRICT"))


class CanonicalProduct(CatalogTimestamps, Base):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("brand_id", "canonical_key", name="uq_catalog_product_brand_key"),
        CheckConstraint("status IN ('draft','published','withdrawn','archived')", name="ck_catalog_product_status"),
        CheckConstraint("revision > 0", name="ck_catalog_product_revision"),
        CheckConstraint("length(description) <= 5000", name="ck_catalog_product_description_length"),
        Index("ix_catalog_product_status_category", "status", "category_code", "id"),
        Index("ix_catalog_product_brand_status", "brand_id", "status", "id"),
        {"schema": CATALOG_SCHEMA},
    )
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=new_uuid7)
    brand_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey(f"{CATALOG_SCHEMA}.brands.id", ondelete="RESTRICT"), nullable=False)
    canonical_key: Mapped[str] = mapped_column(String(120), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    category_code: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'draft'"))
    last_publication_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            f"{CATALOG_SCHEMA}.publications.id",
            ondelete="RESTRICT",
            use_alter=True,
            name="fk_catalog_product_last_publication",
        ),
    )
    revision: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("1"))
    brand: Mapped[Brand] = relationship(back_populates="products")
    listings: Mapped[list[MerchantListing]] = relationship(back_populates="product")


class MerchantListing(CatalogTimestamps, Base):
    __tablename__ = "listings"
    __table_args__ = (
        UniqueConstraint("merchant_id", "source_listing_key", name="uq_catalog_listing_source_key"),
        CheckConstraint("status IN ('draft','published','withdrawn')", name="ck_catalog_listing_status"),
        CheckConstraint("length(destination_url) <= 2048", name="ck_catalog_listing_destination_length"),
        CheckConstraint("revision > 0", name="ck_catalog_listing_revision"),
        Index("ix_catalog_listing_product_status", "product_id", "status", "merchant_id"),
        Index("ix_catalog_listing_merchant_status", "merchant_id", "status", "id"),
        {"schema": CATALOG_SCHEMA},
    )
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=new_uuid7)
    product_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey(f"{CATALOG_SCHEMA}.products.id", ondelete="RESTRICT"), nullable=False)
    merchant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey(f"{CATALOG_SCHEMA}.merchants.id", ondelete="RESTRICT"), nullable=False)
    source_listing_key: Mapped[str] = mapped_column(String(160), nullable=False)
    destination_url: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'draft'"))
    last_publication_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey(f"{CATALOG_SCHEMA}.publications.id", ondelete="RESTRICT"))
    revision: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("1"))
    product: Mapped[CanonicalProduct] = relationship(back_populates="listings")
    merchant: Mapped[Merchant] = relationship(back_populates="listings")
    variants: Mapped[list[ListingVariant]] = relationship(back_populates="listing")


class ListingVariant(CatalogTimestamps, Base):
    __tablename__ = "variants"
    __table_args__ = (
        UniqueConstraint("listing_id", "source_variant_key", name="uq_catalog_variant_source_key"),
        CheckConstraint("status IN ('active','withdrawn')", name="ck_catalog_variant_status"),
        CheckConstraint("length(image_url) <= 2048", name="ck_catalog_variant_image_url_length"),
        CheckConstraint("revision > 0", name="ck_catalog_variant_revision"),
        Index("ix_catalog_variant_listing_status", "listing_id", "status", "id"),
        {"schema": CATALOG_SCHEMA},
    )
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=new_uuid7)
    listing_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey(f"{CATALOG_SCHEMA}.listings.id", ondelete="RESTRICT"), nullable=False)
    source_variant_key: Mapped[str] = mapped_column(String(160), nullable=False)
    size_label: Mapped[str | None] = mapped_column(String(80))
    color_label: Mapped[str | None] = mapped_column(String(80))
    color_family: Mapped[str | None] = mapped_column(String(40))
    image_url: Mapped[str] = mapped_column(Text, nullable=False)
    image_alt: Mapped[str] = mapped_column(String(240), nullable=False)
    image_rights_ref: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'active'"))
    last_publication_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey(f"{CATALOG_SCHEMA}.publications.id", ondelete="RESTRICT"))
    revision: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("1"))
    listing: Mapped[MerchantListing] = relationship(back_populates="variants")
    prices: Mapped[list[PriceRecord]] = relationship(back_populates="variant")


class PriceRecord(Base):
    __tablename__ = "prices"
    __table_args__ = (
        UniqueConstraint("publication_id", "variant_id", name="uq_catalog_price_publication_variant"),
        CheckConstraint("amount_minor > 0", name="ck_catalog_price_positive"),
        CheckConstraint("currency = 'INR'", name="ck_catalog_price_inr"),
        CheckConstraint("valid_until > observed_at", name="ck_catalog_price_interval"),
        Index("ix_catalog_price_variant_latest", "variant_id", text("recorded_at DESC"), text("id DESC")),
        {"schema": CATALOG_SCHEMA},
    )
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=new_uuid7)
    variant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey(f"{CATALOG_SCHEMA}.variants.id", ondelete="RESTRICT"), nullable=False)
    publication_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey(f"{CATALOG_SCHEMA}.publications.id", ondelete="RESTRICT"), nullable=False)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(CHAR(3), nullable=False, server_default=text("'INR'"))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False)
    variant: Mapped[ListingVariant] = relationship(back_populates="prices")
