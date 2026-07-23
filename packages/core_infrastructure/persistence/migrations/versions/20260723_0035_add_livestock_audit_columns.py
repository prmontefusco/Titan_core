"""Adicionar colunas status, version, issuer_source, evidence_reference, verification_status e valid_from/until em rural_properties, animals e animal_identifiers (Passo 8.0 - 8.2).

Revision ID: 20260723_0035
Revises: 20260723_0034
Create Date: 2026-07-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260723_0035"
down_revision: str | None = "20260723_0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "core_audit"


def upgrade() -> None:
    # 1. Add status e version em rural_properties
    op.add_column(
        "rural_properties",
        sa.Column(
            "status",
            sa.String(length=50),
            nullable=False,
            server_default="ACTIVE",
        ),
        schema=SCHEMA,
    )
    op.add_column(
        "rural_properties",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        schema=SCHEMA,
    )

    # 2. Add version em animals
    op.add_column(
        "animals",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        schema=SCHEMA,
    )

    # 3. Add audit columns em animal_identifiers
    op.add_column(
        "animal_identifiers",
        sa.Column("issuer_source", sa.String(length=100), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "animal_identifiers",
        sa.Column("evidence_reference", sa.String(length=255), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "animal_identifiers",
        sa.Column(
            "verification_status",
            sa.String(length=50),
            nullable=False,
            server_default="DECLARADO",
        ),
        schema=SCHEMA,
    )
    op.add_column(
        "animal_identifiers",
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "animal_identifiers",
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_column("animal_identifiers", "valid_until", schema=SCHEMA)
    op.drop_column("animal_identifiers", "valid_from", schema=SCHEMA)
    op.drop_column("animal_identifiers", "verification_status", schema=SCHEMA)
    op.drop_column("animal_identifiers", "evidence_reference", schema=SCHEMA)
    op.drop_column("animal_identifiers", "issuer_source", schema=SCHEMA)

    op.drop_column("animals", "version", schema=SCHEMA)

    op.drop_column("rural_properties", "version", schema=SCHEMA)
    op.drop_column("rural_properties", "status", schema=SCHEMA)
