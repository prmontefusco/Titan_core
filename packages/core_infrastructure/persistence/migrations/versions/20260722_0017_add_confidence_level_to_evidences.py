"""Adicionar colunas confidence_tier e confidence_reason em core_audit.evidences.

Revision ID: 20260722_0017
Revises: 20260722_0016
Create Date: 2026-07-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260722_0017"
down_revision: str | None = "20260722_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "core_audit"
EVIDENCES_TABLE = "evidences"


def upgrade() -> None:
    op.add_column(
        EVIDENCES_TABLE,
        sa.Column(
            "confidence_tier", sa.String(length=50), nullable=False, server_default="INFORMED"
        ),
        schema=SCHEMA,
    )
    op.add_column(
        EVIDENCES_TABLE,
        sa.Column(
            "confidence_reason",
            sa.Text(),
            nullable=False,
            server_default="Declaração informada sem verificação adicional.",
        ),
        schema=SCHEMA,
    )
    # Remove os server_default para exigir inserção explícita no código de aplicação
    op.alter_column(EVIDENCES_TABLE, "confidence_tier", server_default=None, schema=SCHEMA)
    op.alter_column(EVIDENCES_TABLE, "confidence_reason", server_default=None, schema=SCHEMA)


def downgrade() -> None:
    op.drop_column(EVIDENCES_TABLE, "confidence_reason", schema=SCHEMA)
    op.drop_column(EVIDENCES_TABLE, "confidence_tier", schema=SCHEMA)
