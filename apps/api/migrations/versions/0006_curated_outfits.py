"""Add the curated outfit feed foundation without seeded content."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_curated_outfits"
down_revision: str | None = "0005_catalog_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "drip_catalog"
UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "outfits",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("brand_id", UUID, nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("caption", sa.Text(), nullable=False, server_default=""),
        sa.Column("image_url", sa.Text(), nullable=False),
        sa.Column("image_alt", sa.String(240), nullable=False),
        sa.Column("rights_ref", sa.String(200), nullable=False),
        sa.Column("approval_ref", sa.String(200), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="draft"),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("length(title) BETWEEN 1 AND 160", name="ck_catalog_outfit_title_length"),
        sa.CheckConstraint("length(caption) <= 2000", name="ck_catalog_outfit_caption_length"),
        sa.CheckConstraint("length(image_url) <= 2048 AND image_url LIKE 'https://%'", name="ck_catalog_outfit_https_image"),
        sa.CheckConstraint("length(image_alt) BETWEEN 1 AND 240", name="ck_catalog_outfit_image_alt"),
        sa.CheckConstraint("length(rights_ref) BETWEEN 1 AND 200", name="ck_catalog_outfit_rights_ref"),
        sa.CheckConstraint("length(approval_ref) BETWEEN 1 AND 200", name="ck_catalog_outfit_approval_ref"),
        sa.CheckConstraint("status IN ('draft','published','archived')", name="ck_catalog_outfit_status"),
        sa.CheckConstraint("revision > 0", name="ck_catalog_outfit_revision"),
        sa.CheckConstraint("(status = 'published' AND published_at IS NOT NULL) OR status <> 'published'", name="ck_catalog_outfit_published_at"),
        sa.ForeignKeyConstraint(["brand_id"], [f"{SCHEMA}.brands.id"], ondelete="RESTRICT"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_catalog_outfit_feed",
        "outfits",
        ["status", sa.text("published_at DESC"), sa.text("id DESC")],
        schema=SCHEMA,
    )
    op.create_index("ix_catalog_outfit_brand", "outfits", ["brand_id"], schema=SCHEMA)
    op.create_table(
        "outfit_items",
        sa.Column("outfit_id", UUID, nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.Column("product_id", UUID, nullable=False),
        sa.PrimaryKeyConstraint("outfit_id", "position", name="pk_catalog_outfit_items"),
        sa.UniqueConstraint("outfit_id", "product_id", name="uq_catalog_outfit_item_product"),
        sa.ForeignKeyConstraint(["outfit_id"], [f"{SCHEMA}.outfits.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["product_id"], [f"{SCHEMA}.products.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("position BETWEEN 1 AND 8", name="ck_catalog_outfit_item_position"),
        schema=SCHEMA,
    )
    op.create_index("ix_catalog_outfit_item_product", "outfit_items", ["product_id"], schema=SCHEMA)
    op.create_table(
        "outfit_publications",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("outfit_id", UUID, nullable=False),
        sa.Column("request_key", UUID, nullable=False, unique=True),
        sa.Column("manifest_sha256", sa.String(64), nullable=False),
        sa.Column("actor_ref", sa.String(80), nullable=False),
        sa.Column("approval_ref", sa.String(200), nullable=False),
        sa.Column("prior_revision", sa.BigInteger()),
        sa.Column("next_revision", sa.BigInteger(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["outfit_id"], [f"{SCHEMA}.outfits.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("manifest_sha256 ~ '^[0-9a-f]{64}$'", name="ck_catalog_outfit_publication_digest"),
        sa.CheckConstraint("action IN ('publish','update','archive')", name="ck_catalog_outfit_publication_action"),
        sa.CheckConstraint("next_revision > 0 AND (prior_revision IS NULL OR prior_revision > 0)", name="ck_catalog_outfit_publication_revision"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_catalog_outfit_publication_history",
        "outfit_publications",
        ["outfit_id", "recorded_at"],
        schema=SCHEMA,
    )
    op.execute("REVOKE ALL ON TABLE drip_catalog.outfits, drip_catalog.outfit_items, drip_catalog.outfit_publications FROM PUBLIC")
    op.execute(
        """DO $$
DECLARE role_name text;
BEGIN
    FOREACH role_name IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
        IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = role_name) THEN
            EXECUTE pg_catalog.format(
                'REVOKE ALL ON TABLE drip_catalog.outfits, drip_catalog.outfit_items, drip_catalog.outfit_publications FROM %I',
                role_name
            );
        END IF;
    END LOOP;
END
$$"""
    )
    op.execute(
        "GRANT SELECT ON TABLE drip_catalog.outfits, drip_catalog.outfit_items TO drip_identity_runtime"
    )


def downgrade() -> None:
    bind = op.get_bind()
    counts = bind.exec_driver_sql(
        "SELECT "
        + ", ".join(
            f"(SELECT count(*) = 0 FROM {SCHEMA}.{table})"
            for table in ("outfit_items", "outfit_publications", "outfits")
        )
    ).one()
    if not all(counts):
        raise RuntimeError("Outfit downgrade refuses to remove populated editorial records.")
    op.drop_index("ix_catalog_outfit_publication_history", table_name="outfit_publications", schema=SCHEMA)
    op.drop_table("outfit_publications", schema=SCHEMA)
    op.drop_index("ix_catalog_outfit_item_product", table_name="outfit_items", schema=SCHEMA)
    op.drop_table("outfit_items", schema=SCHEMA)
    op.drop_index("ix_catalog_outfit_brand", table_name="outfits", schema=SCHEMA)
    op.drop_index("ix_catalog_outfit_feed", table_name="outfits", schema=SCHEMA)
    op.drop_table("outfits", schema=SCHEMA)
