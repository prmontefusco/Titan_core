"""Adicionar colunas de assinatura criptográfica à tabela core_audit.evidences.

Revision ID: 20260722_0020
Revises: 20260722_0019
Create Date: 2026-07-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260722_0020"
down_revision: str | None = "20260722_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "core_audit"
EVIDENCES_TABLE = "evidences"


def upgrade() -> None:
    op.add_column(
        EVIDENCES_TABLE,
        sa.Column("signature_id", postgresql.UUID(as_uuid=True), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        EVIDENCES_TABLE,
        sa.Column("signature_profile", sa.String(length=50), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        EVIDENCES_TABLE,
        sa.Column("signature_algorithm", sa.String(length=50), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        EVIDENCES_TABLE,
        sa.Column("signature_raw_bytes", sa.LargeBinary(), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        EVIDENCES_TABLE,
        sa.Column("signature_key_id", postgresql.UUID(as_uuid=True), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        EVIDENCES_TABLE,
        sa.Column("signature_key_purpose", sa.String(length=100), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        EVIDENCES_TABLE,
        sa.Column("signature_signed_at", sa.DateTime(timezone=True), nullable=True),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_column(EVIDENCES_TABLE, "signature_signed_at", schema=SCHEMA)
    op.drop_column(EVIDENCES_TABLE, "signature_key_purpose", schema=SCHEMA)
    op.drop_column(EVIDENCES_TABLE, "signature_key_id", schema=SCHEMA)
    op.drop_column(EVIDENCES_TABLE, "signature_raw_bytes", schema=SCHEMA)
    op.drop_column(EVIDENCES_TABLE, "signature_algorithm", schema=SCHEMA)
    op.drop_column(EVIDENCES_TABLE, "signature_profile", schema=SCHEMA)
    op.drop_column(EVIDENCES_TABLE, "signature_id", schema=SCHEMA)
