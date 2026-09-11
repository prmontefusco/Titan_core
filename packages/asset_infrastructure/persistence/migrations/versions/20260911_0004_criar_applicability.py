"""Criar applicability com RLS (A3).

Revision ID: 20260911_0004
Revises: 20260911_0003
Create Date: 2026-09-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260911_0004"
down_revision: str | None = "20260911_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "core_audit"
TABLE = "applicability"
MODULE_OWNER_COMMENT = "titan.classification=PROTECTED;titan.module_owner=asset"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("applicability_id", sa.UUID(), nullable=False),
        sa.Column("record_owner_organization_id", sa.UUID(), nullable=False),
        sa.Column("part_id", sa.UUID(), nullable=False),
        sa.Column("part_revision_id", sa.UUID(), nullable=False),
        sa.Column("target_model_id", sa.UUID(), nullable=False),
        sa.Column("target_variant_id", sa.UUID(), nullable=True),
        sa.Column("target_serial_from", sa.String(length=100), nullable=True),
        sa.Column("target_serial_to", sa.String(length=100), nullable=True),
        sa.Column("target_valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("target_valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("evidence_id", sa.UUID(), nullable=False),
        sa.Column("asserted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("asserted_by_id", sa.UUID(), nullable=False),
        sa.Column("asserted_by_entity_type", sa.String(length=100), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("withdrawal_reason", sa.String(length=500), nullable=True),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["part_id"], ["core_audit.parts.part_id"], name="fk_applicability_part"
        ),
        sa.ForeignKeyConstraint(
            ["part_revision_id"],
            ["core_audit.part_revisions.revision_id"],
            name="fk_applicability_part_revision",
        ),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_applicability_organization",
        ),
        sa.PrimaryKeyConstraint("applicability_id"),
        schema=SCHEMA,
        comment=MODULE_OWNER_COMMENT,
    )

    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{TABLE} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{TABLE} FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(f"""
        CREATE POLICY tenant_isolation_policy ON {SCHEMA}.{TABLE}
        FOR ALL
        USING (
            record_owner_organization_id = NULLIF(
                current_setting('titan.organization_id', true),
                ''
            )::uuid
        )
        WITH CHECK (
            record_owner_organization_id = NULLIF(
                current_setting('titan.organization_id', true),
                ''
            )::uuid
        )
        """)
    )


def downgrade() -> None:
    op.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {SCHEMA}.{TABLE}"))
    op.drop_table(TABLE, schema=SCHEMA)
