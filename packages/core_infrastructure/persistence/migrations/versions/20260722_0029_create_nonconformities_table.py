"""Criar tabela core_audit.nonconformities com suporte a RLS.

Revision ID: 20260722_0029
Revises: 20260722_0028
Create Date: 2026-07-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260722_0029"
down_revision: str | None = "20260722_0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "core_audit"
NONCONFORMITIES_TABLE = "nonconformities"


def upgrade() -> None:
    op.create_table(
        NONCONFORMITIES_TABLE,
        sa.Column("nonconformity_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subject_entity_type", sa.String(length=100), nullable=False),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subject_contract_version", sa.Integer(), nullable=False),
        sa.Column("origin", sa.String(length=50), nullable=False),
        sa.Column("severity", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("affected_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("affected_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("origin_reference", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("responsible_reference", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("corrective_action", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "correction_evidence_references",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("reevaluation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closure_note", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "transitions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        # Encerramento nunca remove histórico: encerrada exige instante e trilha.
        sa.CheckConstraint(
            "status <> 'encerrada' OR closed_at IS NOT NULL",
            name="ck_nonconformities_closed_at",
        ),
        sa.CheckConstraint(
            "jsonb_array_length(transitions) > 0", name="ck_nonconformities_has_history"
        ),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_nonconformities_organization",
        ),
        comment="titan.classification=PROTECTED;titan.module_owner=core_audit",
        schema=SCHEMA,
    )

    op.create_index(
        "ix_nonconformities_subject",
        NONCONFORMITIES_TABLE,
        ["record_owner_organization_id", "subject_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_nonconformities_status",
        NONCONFORMITIES_TABLE,
        ["record_owner_organization_id", "status"],
        schema=SCHEMA,
    )

    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{NONCONFORMITIES_TABLE} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{NONCONFORMITIES_TABLE} FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            f"""
            CREATE POLICY tenant_isolation_policy ON {SCHEMA}.{NONCONFORMITIES_TABLE}
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
        sa.text(
            f"DROP POLICY IF EXISTS tenant_isolation_policy ON {SCHEMA}.{NONCONFORMITIES_TABLE}"
        )
    )
    op.drop_index("ix_nonconformities_status", table_name=NONCONFORMITIES_TABLE, schema=SCHEMA)
    op.drop_index("ix_nonconformities_subject", table_name=NONCONFORMITIES_TABLE, schema=SCHEMA)
    op.drop_table(NONCONFORMITIES_TABLE, schema=SCHEMA)
