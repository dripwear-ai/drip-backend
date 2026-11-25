"""Portable identity checkpoint following the historical PostgreSQL 18 assertion.

Revision ID: 0003_portable_identity_ckpt
Revises: 0002_require_pg18_uuidv7
"""

from collections.abc import Sequence

from alembic import context, op
from drip.core.migration_checkpoint import PARENT_REVISION_ID, T_REVISION_ID, verify_checkpoint
from sqlalchemy import text

revision: str = T_REVISION_ID
down_revision: str | None = PARENT_REVISION_ID
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Verify the portable baseline; T introduces no database objects."""
    if context.is_offline_mode():
        raise RuntimeError("Checkpoint T requires an online database preflight.")
    verify_checkpoint(op.get_bind(), expected_revision=PARENT_REVISION_ID)


def downgrade() -> None:
    """Keep PG17 at T; its guarded bootstrap route cannot replay historical 0002."""
    server_version_num = op.get_bind().scalar(
        text("SELECT current_setting('server_version_num')::integer")
    )
    if not isinstance(server_version_num, int) or server_version_num < 180000:
        raise RuntimeError("Downgrade below checkpoint T is prohibited on PostgreSQL 17.")
