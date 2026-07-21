"""Criar recibos imutáveis do bootstrap mínimo.

Revision ID: 20260721_0007
Revises: 20260721_0006
Create Date: 2026-07-21

Classificação: PROTECTED
Módulo owner: core_identity
Decisão: ADR 0032
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260721_0007"
down_revision: str | None = "20260721_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "core_identity"
TABLE = "bootstrap_receipts"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("bootstrap_receipt_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("profile_code", sa.String(length=100), nullable=False),
        sa.Column("profile_version", sa.String(length=30), nullable=False),
        sa.Column("environment", sa.String(length=30), nullable=False),
        sa.Column("origin", sa.String(length=100), nullable=False),
        sa.Column("authority_actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("result", sa.String(length=30), nullable=False),
        sa.CheckConstraint("result = 'APLICADO'", name="ck_bootstrap_receipts_result"),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_bootstrap_receipts_owner",
        ),
        sa.PrimaryKeyConstraint("bootstrap_receipt_id", name="pk_bootstrap_receipts"),
        sa.UniqueConstraint(
            "profile_code",
            "profile_version",
            "environment",
            name="uq_bootstrap_receipts_profile_environment",
        ),
        schema=SCHEMA,
    )
    op.execute(
        sa.text(
            "COMMENT ON TABLE core_identity.bootstrap_receipts IS "
            "'titan.classification=PROTECTED;titan.module_owner=core_identity'"
        )
    )
    op.execute(sa.text("ALTER TABLE core_identity.bootstrap_receipts ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text("ALTER TABLE core_identity.bootstrap_receipts FORCE ROW LEVEL SECURITY"))
    context = (
        "record_owner_organization_id = "
        "NULLIF(current_setting('titan.organization_id', true), '')::uuid"
    )
    op.execute(
        sa.text(
            "CREATE POLICY bootstrap_receipts_select_by_owner ON "
            f"core_identity.bootstrap_receipts FOR SELECT USING ({context})"
        )
    )
    op.execute(
        sa.text(
            "CREATE POLICY bootstrap_receipts_insert_by_owner ON "
            f"core_identity.bootstrap_receipts FOR INSERT WITH CHECK ({context})"
        )
    )
    op.execute(sa.text("REVOKE ALL ON core_identity.bootstrap_receipts FROM PUBLIC"))


def downgrade() -> None:
    op.execute(
        sa.text(
            "DROP POLICY bootstrap_receipts_insert_by_owner ON core_identity.bootstrap_receipts"
        )
    )
    op.execute(
        sa.text(
            "DROP POLICY bootstrap_receipts_select_by_owner ON core_identity.bootstrap_receipts"
        )
    )
    op.drop_table(TABLE, schema=SCHEMA)
