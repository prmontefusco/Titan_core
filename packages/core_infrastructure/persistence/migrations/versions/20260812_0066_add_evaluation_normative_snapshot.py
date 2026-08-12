"""Preservar fotografia normativa tipada em evaluations (NEXT-02/Corte 3).

Revision ID: 20260812_0066
Revises: 20260812_0065
Create Date: 2026-08-12
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260812_0066"
down_revision = "20260812_0065"
branch_labels = None
depends_on = None

SCHEMA = "core_audit"
TABLE = "evaluations"


def upgrade() -> None:
    # Nullable de propósito: Evaluation histórica não recebe fundamento inferido.
    op.add_column(
        TABLE,
        sa.Column("normative_basis_snapshot", postgresql.JSONB(), nullable=True),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_column(TABLE, "normative_basis_snapshot", schema=SCHEMA)
