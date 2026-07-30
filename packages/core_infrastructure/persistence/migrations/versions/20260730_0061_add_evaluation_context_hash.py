"""Adicionar context_hash em evaluations (ADR-0051).

Revision ID: 20260730_0061
Revises: 20260730_0060
Create Date: 2026-07-30
"""

import sqlalchemy as sa
from alembic import op

revision = "20260730_0061"
down_revision = "20260730_0060"
branch_labels = None
depends_on = None

SCHEMA = "core_audit"
TABLE = "evaluations"
# 64 zeros nunca ocorre como digest SHA-256 real: marca de propósito as linhas
# gravadas antes de context_hash existir, sem afirmar equivalência que não pode
# ser demonstrada (ADR-0051 secao 14).
LEGACY_CONTEXT_HASH = "0" * 64


def upgrade() -> None:
    op.add_column(
        TABLE,
        sa.Column("context_hash", sa.String(length=64), nullable=True),
        schema=SCHEMA,
    )
    op.execute(
        sa.text(
            f"""
            UPDATE {SCHEMA}.{TABLE}
               SET context_hash = :legacy_hash
             WHERE context_hash IS NULL
            """
        ).bindparams(legacy_hash=LEGACY_CONTEXT_HASH)
    )
    op.alter_column(
        TABLE,
        "context_hash",
        existing_type=sa.String(length=64),
        nullable=False,
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_column(TABLE, "context_hash", schema=SCHEMA)
