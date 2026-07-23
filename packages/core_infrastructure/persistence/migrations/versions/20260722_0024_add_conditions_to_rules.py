"""Adicionar coluna de condições normativas declarativas em core_audit.rules.

Revision ID: 20260722_0024
Revises: 20260722_0023
Create Date: 2026-07-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260722_0024"
down_revision: str | None = "20260722_0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "core_audit"
RULES_TABLE = "rules"


def upgrade() -> None:
    op.add_column(
        RULES_TABLE,
        sa.Column(
            "conditions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_column(RULES_TABLE, "conditions", schema=SCHEMA)
