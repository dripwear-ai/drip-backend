"""Create the private catalog foundation; no data is seeded."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_catalog_foundation"
down_revision: str | None = "0004_identity_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "drip_catalog"
UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.execute("CREATE SCHEMA drip_catalog")
    op.execute("REVOKE ALL ON SCHEMA drip_catalog FROM PUBLIC")
    op.execute("""DO $$
DECLARE role_name text;
BEGIN
    FOREACH role_name IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
        IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = role_name) THEN
            EXECUTE pg_catalog.format('REVOKE ALL ON SCHEMA drip_catalog FROM %I', role_name);
        END IF;
    END LOOP;
END
$$""")
    op.create_table(
        "brands",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("slug", sa.String(80), nullable=False, unique=True),
        sa.Column("display_name", sa.String(160), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("source_ref", sa.String(200), nullable=False),
        sa.Column("reviewer_ref", sa.String(80), nullable=False),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("status IN ('active','archived')", name="ck_catalog_brand_status"),
        sa.CheckConstraint("revision > 0", name="ck_catalog_brand_revision"),
        schema=SCHEMA,
    )
    op.create_table(
        "merchants",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("slug", sa.String(80), nullable=False, unique=True),
        sa.Column("display_name", sa.String(160), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("purchase_mode", sa.Text(), nullable=False, server_default="external_redirect"),
        sa.Column("allowed_destination_hosts", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("allowed_image_hosts", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("source_ref", sa.String(200), nullable=False),
        sa.Column("reviewer_ref", sa.String(80), nullable=False),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("status IN ('active','suspended')", name="ck_catalog_merchant_status"),
        sa.CheckConstraint("purchase_mode = 'external_redirect'", name="ck_catalog_merchant_purchase_mode"),
        sa.CheckConstraint("cardinality(allowed_destination_hosts) BETWEEN 1 AND 20", name="ck_catalog_merchant_destination_hosts"),
        sa.CheckConstraint("cardinality(allowed_image_hosts) BETWEEN 1 AND 20", name="ck_catalog_merchant_image_hosts"),
        sa.CheckConstraint("revision > 0", name="ck_catalog_merchant_revision"),
        schema=SCHEMA,
    )
    op.create_table(
        "publications",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("merchant_id", UUID, sa.ForeignKey(f"{SCHEMA}.merchants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("request_key", UUID, nullable=False, unique=True),
        sa.Column("manifest_sha256", sa.CHAR(64), nullable=False),
        sa.Column("schema_version", sa.SmallInteger(), nullable=False),
        sa.Column("reviewer_ref", sa.String(80), nullable=False),
        sa.Column("approval_ref", sa.String(200), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="applied"),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("revocation_audit", postgresql.JSONB()),
        sa.Column("change_summary", postgresql.JSONB(), nullable=False),
        sa.Column("supersedes_id", UUID, sa.ForeignKey(f"{SCHEMA}.publications.id", ondelete="RESTRICT")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("status IN ('applied','revoked')", name="ck_catalog_publication_status"),
        sa.CheckConstraint("manifest_sha256 ~ '^[0-9a-f]{64}$'", name="ck_catalog_publication_digest"),
        sa.CheckConstraint("(status = 'applied' AND revoked_at IS NULL) OR (status = 'revoked' AND revoked_at IS NOT NULL)", name="ck_catalog_publication_revocation"),
        sa.Index("ix_catalog_publication_merchant_applied", "merchant_id", "applied_at"),
        schema=SCHEMA,
    )
    op.create_table(
        "products",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("brand_id", UUID, sa.ForeignKey(f"{SCHEMA}.brands.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("canonical_key", sa.String(120), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("category_code", sa.String(40), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="draft"),
        sa.Column("last_publication_id", UUID),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.UniqueConstraint("brand_id", "canonical_key", name="uq_catalog_product_brand_key"),
        sa.CheckConstraint("status IN ('draft','published','withdrawn','archived')", name="ck_catalog_product_status"),
        sa.CheckConstraint("revision > 0", name="ck_catalog_product_revision"),
        sa.CheckConstraint("length(description) <= 5000", name="ck_catalog_product_description_length"),
        sa.Index("ix_catalog_product_status_category", "status", "category_code", "id"),
        sa.Index("ix_catalog_product_brand_status", "brand_id", "status", "id"),
        schema=SCHEMA,
    )
    op.create_table(
        "listings",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("product_id", UUID, sa.ForeignKey(f"{SCHEMA}.products.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("merchant_id", UUID, sa.ForeignKey(f"{SCHEMA}.merchants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("source_listing_key", sa.String(160), nullable=False),
        sa.Column("destination_url", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="draft"),
        sa.Column("last_publication_id", UUID, sa.ForeignKey(f"{SCHEMA}.publications.id", ondelete="RESTRICT")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.UniqueConstraint("merchant_id", "source_listing_key", name="uq_catalog_listing_source_key"),
        sa.CheckConstraint("status IN ('draft','published','withdrawn')", name="ck_catalog_listing_status"),
        sa.CheckConstraint("length(destination_url) <= 2048", name="ck_catalog_listing_destination_length"),
        sa.CheckConstraint("revision > 0", name="ck_catalog_listing_revision"),
        sa.Index("ix_catalog_listing_product_status", "product_id", "status", "merchant_id"),
        sa.Index("ix_catalog_listing_merchant_status", "merchant_id", "status", "id"),
        schema=SCHEMA,
    )
    op.create_table(
        "variants",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("listing_id", UUID, sa.ForeignKey(f"{SCHEMA}.listings.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("source_variant_key", sa.String(160), nullable=False),
        sa.Column("size_label", sa.String(80)),
        sa.Column("color_label", sa.String(80)),
        sa.Column("color_family", sa.String(40)),
        sa.Column("image_url", sa.Text(), nullable=False),
        sa.Column("image_alt", sa.String(240), nullable=False),
        sa.Column("image_rights_ref", sa.String(200), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("last_publication_id", UUID, sa.ForeignKey(f"{SCHEMA}.publications.id", ondelete="RESTRICT")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.UniqueConstraint("listing_id", "source_variant_key", name="uq_catalog_variant_source_key"),
        sa.CheckConstraint("status IN ('active','withdrawn')", name="ck_catalog_variant_status"),
        sa.CheckConstraint("length(image_url) <= 2048", name="ck_catalog_variant_image_url_length"),
        sa.CheckConstraint("revision > 0", name="ck_catalog_variant_revision"),
        sa.Index("ix_catalog_variant_listing_status", "listing_id", "status", "id"),
        schema=SCHEMA,
    )
    op.create_table(
        "prices",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("variant_id", UUID, sa.ForeignKey(f"{SCHEMA}.variants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("publication_id", UUID, sa.ForeignKey(f"{SCHEMA}.publications.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.CHAR(3), nullable=False, server_default="INR"),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("publication_id", "variant_id", name="uq_catalog_price_publication_variant"),
        sa.CheckConstraint("amount_minor > 0", name="ck_catalog_price_positive"),
        sa.CheckConstraint("currency = 'INR'", name="ck_catalog_price_inr"),
        sa.CheckConstraint("valid_until > observed_at", name="ck_catalog_price_interval"),
        sa.Index("ix_catalog_price_variant_latest", "variant_id", sa.text("recorded_at DESC"), sa.text("id DESC")),
        schema=SCHEMA,
    )
    op.create_foreign_key("fk_catalog_product_last_publication", "products", "publications", ["last_publication_id"], ["id"], source_schema=SCHEMA, referent_schema=SCHEMA, ondelete="RESTRICT")
    op.execute("GRANT USAGE ON SCHEMA drip_catalog TO drip_identity_runtime")
    op.execute("GRANT SELECT ON ALL TABLES IN SCHEMA drip_catalog TO drip_identity_runtime")


def downgrade() -> None:
    bind = op.get_bind()
    counts = bind.exec_driver_sql(
        "SELECT " + ", ".join(f"(SELECT count(*) = 0 FROM {SCHEMA}.{table})" for table in ("prices", "variants", "listings", "products", "publications", "merchants", "brands"))
    ).one()
    if not all(counts):
        raise RuntimeError("Catalog downgrade refuses to remove populated catalog records.")
    op.drop_constraint("fk_catalog_product_last_publication", "products", schema=SCHEMA, type_="foreignkey")
    for table in ("prices", "variants", "listings", "products", "publications", "merchants", "brands"):
        op.drop_table(table, schema=SCHEMA)
    op.execute("DROP SCHEMA drip_catalog")
