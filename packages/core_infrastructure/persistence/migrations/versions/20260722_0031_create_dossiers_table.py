"""Criar tabela core_audit.dossiers com suporte a RLS.

Revision ID: 20260722_0031
Revises: 20260722_0030
Create Date: 2026-07-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260722_0031"
down_revision: str | None = "20260722_0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "core_audit"
DOSSIERS_TABLE = "dossiers"


def upgrade() -> None:
    op.create_table(
        DOSSIERS_TABLE,
        sa.Column("dossier_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subject_entity_type", sa.String(length=100), nullable=False),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subject_contract_version", sa.Integer(), nullable=False),
        sa.Column("purpose", sa.String(length=255), nullable=False),
        sa.Column("decision_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evaluation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("serialization_version", sa.String(length=50), nullable=False),
        sa.Column("document_version", sa.Integer(), nullable=False),
        sa.Column("dossier_hash", sa.String(length=64), nullable=False),
        sa.Column("document", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_dossiers_organization",
        ),
        sa.ForeignKeyConstraint(
            ["decision_id"],
            ["core_audit.decisions.decision_id"],
            name="fk_dossiers_decision",
        ),
        comment="titan.classification=PROTECTED;titan.module_owner=core_audit",
        schema=SCHEMA,
    )

    op.create_index(
        "ix_dossiers_subject",
        DOSSIERS_TABLE,
        ["record_owner_organization_id", "subject_id"],
        schema=SCHEMA,
    )

    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{DOSSIERS_TABLE} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{DOSSIERS_TABLE} FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            f"""
            CREATE POLICY tenant_isolation_policy ON {SCHEMA}.{DOSSIERS_TABLE}
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
        sa.text(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {SCHEMA}.{DOSSIERS_TABLE}")
    )
    op.drop_index("ix_dossiers_subject", table_name=DOSSIERS_TABLE, schema=SCHEMA)
    op.drop_table(DOSSIERS_TABLE, schema=SCHEMA)
