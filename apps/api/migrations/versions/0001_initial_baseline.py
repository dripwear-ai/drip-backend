"""Initial foundation baseline

Revision ID: 0001_initial_baseline
Revises:
Create Date: 2026-10-11 22:45:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_initial_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Historical operation retained for existing databases. PostgreSQL 18's native
    # uuidv7() does not require this extension; do not remove shared extensions on downgrade.
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")


def downgrade() -> None:
    pass
