"""Criar tabela de adocao de regras governadas.

Revision ID: 20260726_0050
Revises: 20260726_0049
Create Date: 2026-07-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260726_0050"
down_revision: str | None = "20260726_0049"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "core_audit"
TABLE = "rule_adoptions"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("adoption_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rule_identity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rule_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("purpose", sa.String(length=120), nullable=False),
        sa.Column("scope", sa.String(length=160), nullable=False),
        sa.Column("adopted_by_target_type", sa.String(length=100), nullable=False),
        sa.Column("adopted_by_target_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("adopted_by_organization_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("adopted_by_contract_version", sa.Integer(), nullable=False),
        sa.Column("adopted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.CheckConstraint("adopted_by_contract_version >= 1", name="ck_rule_adoptions_actor_cv"),
        sa.UniqueConstraint(
            "record_owner_organization_id",
            "rule_identity_id",
            "purpose",
            "scope",
            "status",
            name="uq_rule_adoptions_active_scope",
        ),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_rule_adoptions_organization",
        ),
        sa.ForeignKeyConstraint(
            ["rule_identity_id"],
            ["core_audit.rule_identities.rule_identity_id"],
            name="fk_rule_adoptions_identity",
        ),
        sa.ForeignKeyConstraint(
            ["rule_version_id"],
            ["core_audit.rules.rule_id"],
            name="fk_rule_adoptions_rule_version",
        ),
        comment="titan.classification=PROTECTED;titan.module_owner=core_audit",
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
