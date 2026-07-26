"""Criar fatos importados da vertical Livestock.

Revision ID: 20260726_0053
Revises: 20260726_0052
Create Date: 2026-07-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260726_0053"
down_revision: str | None = "20260726_0052"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "core_audit"
TABLE = "imported_livestock_facts"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("imported_fact_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("animal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_artifact_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fact_type", sa.String(length=120), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("asserted_by", sa.String(length=255), nullable=False),
        sa.Column("received_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("origin", sa.String(length=40), nullable=False),
        sa.Column("confidence_tier", sa.String(length=40), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_imported_livestock_facts_organization",
        ),
        sa.ForeignKeyConstraint(
            ["animal_id"],
            ["core_audit.animals.animal_id"],
            name="fk_imported_livestock_facts_animal",
        ),
        sa.ForeignKeyConstraint(
            ["source_artifact_id"],
            ["core_audit.received_transfer_artifacts.artifact_id"],
            name="fk_imported_livestock_facts_artifact",
        ),
        comment="titan.classification=PROTECTED;titan.module_owner=livestock",
        schema=SCHEMA,
    )
    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{TABLE} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{TABLE} FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            f"""
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
            """
        )
    )


def downgrade() -> None:
    op.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {SCHEMA}.{TABLE}"))
    op.drop_table(TABLE, schema=SCHEMA)
