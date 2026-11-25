"""Require native PostgreSQL 18 UUIDv7 without changing existing data.

Revision ID: 0002_require_pg18_uuidv7
Revises: 0001_initial_baseline
"""

from alembic import op

revision = "0002_require_pg18_uuidv7"
down_revision = "0001_initial_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF current_setting('server_version_num')::integer < 180000 THEN
                RAISE EXCEPTION 'DRIP requires PostgreSQL 18 or later';
            END IF;
            IF pg_catalog.uuid_extract_version(pg_catalog.uuidv7()) <> 7 THEN
                RAISE EXCEPTION 'Native UUIDv7 generation is required';
            END IF;
        END $$;
    """)


def downgrade() -> None:
    # This revision is a capability assertion, with no schema/data to undo.
    pass
