"""Criar tabelas de governanca e timeline de regras.

Revision ID: 20260726_0049
Revises: 20260726_0048
Create Date: 2026-07-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260726_0049"
down_revision: str | None = "20260726_0048"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "core_audit"
RULE_IDENTITIES_TABLE = "rule_identities"
RULE_TIMELINE_EVENTS_TABLE = "rule_timeline_events"


def upgrade() -> None:
    op.create_table(
        RULE_IDENTITIES_TABLE,
        sa.Column("rule_identity_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("purpose", sa.String(length=120), nullable=False),
        sa.Column("scope", sa.String(length=160), nullable=False),
        sa.Column("source_type", sa.String(length=40), nullable=False),
        sa.Column("created_by_target_type", sa.String(length=100), nullable=False),
        sa.Column("created_by_target_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_organization_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by_contract_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("vertical", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.UniqueConstraint(
            "record_owner_organization_id",
            "code",
            name="uq_rule_identities_organization_code",
        ),
        sa.CheckConstraint("created_by_contract_version >= 1", name="ck_rule_identities_actor_cv"),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_rule_identities_organization",
        ),
        comment="titan.classification=PROTECTED;titan.module_owner=core_audit",
        schema=SCHEMA,
    )

    op.create_table(
        RULE_TIMELINE_EVENTS_TABLE,
        sa.Column("event_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rule_identity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("actor_target_type", sa.String(length=100), nullable=False),
        sa.Column("actor_target_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_organization_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_contract_version", sa.Integer(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rule_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "evidence_references",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint("actor_contract_version >= 1", name="ck_rule_timeline_actor_cv"),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_rule_timeline_organization",
        ),
        sa.ForeignKeyConstraint(
            ["rule_identity_id"],
            ["core_audit.rule_identities.rule_identity_id"],
            name="fk_rule_timeline_identity",
        ),
        sa.ForeignKeyConstraint(
            ["rule_version_id"],
            ["core_audit.rules.rule_id"],
            name="fk_rule_timeline_rule_version",
        ),
        comment="titan.classification=PROTECTED;titan.module_owner=core_audit",
        schema=SCHEMA,
    )

    for table_name in (RULE_IDENTITIES_TABLE, RULE_TIMELINE_EVENTS_TABLE):
        op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{table_name} ENABLE ROW LEVEL SECURITY"))
        op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{table_name} FORCE ROW LEVEL SECURITY"))
        op.execute(
            sa.text(
                f"""
                CREATE POLICY tenant_isolation_policy ON {SCHEMA}.{table_name}
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
    for table_name in (RULE_TIMELINE_EVENTS_TABLE, RULE_IDENTITIES_TABLE):
        op.execute(
            sa.text(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {SCHEMA}.{table_name}")
        )
    op.drop_table(RULE_TIMELINE_EVENTS_TABLE, schema=SCHEMA)
    op.drop_table(RULE_IDENTITIES_TABLE, schema=SCHEMA)
