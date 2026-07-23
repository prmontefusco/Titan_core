"""Criar tabela core_audit.evaluations com suporte a RLS.

Revision ID: 20260722_0025
Revises: 20260722_0024
Create Date: 2026-07-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260722_0025"
down_revision: str | None = "20260722_0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "core_audit"
EVALUATIONS_TABLE = "evaluations"


def upgrade() -> None:
    op.create_table(
        EVALUATIONS_TABLE,
        sa.Column("evaluation_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policy_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policy_version", sa.Integer(), nullable=False),
        sa.Column("subject_entity_type", sa.String(length=100), nullable=False),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("purpose", sa.String(length=255), nullable=False),
        sa.Column("outcome", sa.String(length=50), nullable=False),
        sa.Column("engine_version", sa.Integer(), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("evaluation_hash", sa.String(length=64), nullable=False),
        sa.Column("fact_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("rule_results", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "rule_versions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("executor_reference", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.CheckConstraint("policy_version >= 1", name="ck_evaluations_policy_version"),
        sa.CheckConstraint("engine_version >= 1", name="ck_evaluations_engine_version"),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_evaluations_organization",
        ),
        sa.ForeignKeyConstraint(
            ["policy_id"],
            ["core_audit.policies.policy_id"],
            name="fk_evaluations_policy",
        ),
        comment="titan.classification=PROTECTED;titan.module_owner=core_audit",
        schema=SCHEMA,
    )

    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{EVALUATIONS_TABLE} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{EVALUATIONS_TABLE} FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            f"""
            CREATE POLICY tenant_isolation_policy ON {SCHEMA}.{EVALUATIONS_TABLE}
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
        sa.text(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {SCHEMA}.{EVALUATIONS_TABLE}")
    )
    op.drop_table(EVALUATIONS_TABLE, schema=SCHEMA)
