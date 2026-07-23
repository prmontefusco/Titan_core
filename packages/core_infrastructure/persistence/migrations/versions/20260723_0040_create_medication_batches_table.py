"""Criar tabela core_audit.medication_batches com RLS (Passo 9.1/9.3 - Titan Livestock).

Revision ID: 20260723_0040
Revises: 20260723_0039
Create Date: 2026-07-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260723_0040"
down_revision: str | None = "20260723_0039"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "core_audit"
BATCHES_TABLE = "medication_batches"


def upgrade() -> None:
    op.create_table(
        BATCHES_TABLE,
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("medication_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("batch_number", sa.String(length=100), nullable=False),
        sa.Column("expiry_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("manufacturing_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "record_owner_organization_id",
            "medication_id",
            "batch_number",
            name="uq_medication_batches_org_med_number",
        ),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_medication_batches_organization",
        ),
        sa.ForeignKeyConstraint(
            ["medication_id"],
            ["core_audit.medications.medication_id"],
            name="fk_medication_batches_medication",
        ),
        comment="titan.classification=PROTECTED;titan.module_owner=titan_livestock",
        schema=SCHEMA,
    )

    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{BATCHES_TABLE} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{BATCHES_TABLE} FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            f"""
            CREATE POLICY tenant_isolation_policy ON {SCHEMA}.{BATCHES_TABLE}
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
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {SCHEMA}.{BATCHES_TABLE}")
    )
    op.drop_table(BATCHES_TABLE, schema=SCHEMA)
