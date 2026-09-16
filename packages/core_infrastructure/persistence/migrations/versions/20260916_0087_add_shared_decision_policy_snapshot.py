"""Add policy snapshot to shared decisions.

Revision ID: 20260916_0087
Revises: 20260909_0086
Create Date: 2026-09-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260916_0087"
down_revision: str | None = "20260909_0086"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "core_audit"
TABLE = "shared_decisions"
COLUMN = "policy_snapshot_json"


def upgrade() -> None:
    op.add_column(
        TABLE,
        sa.Column(COLUMN, postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_column(TABLE, COLUMN, schema=SCHEMA)
