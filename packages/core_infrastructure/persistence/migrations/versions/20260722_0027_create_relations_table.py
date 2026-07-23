"""Criar tabela core_audit.relations com suporte a RLS.

Revision ID: 20260722_0027
Revises: 20260722_0026
Create Date: 2026-07-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260722_0027"
down_revision: str | None = "20260722_0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "core_audit"
RELATIONS_TABLE = "relations"


def upgrade() -> None:
    op.create_table(
        RELATIONS_TABLE,
        sa.Column("relation_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_entity_type", sa.String(length=100), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_contract_version", sa.Integer(), nullable=False),
        sa.Column("target_entity_type", sa.String(length=100), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_contract_version", sa.Integer(), nullable=False),
        sa.Column("relation_type", sa.String(length=100), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confidence_tier", sa.String(length=30), nullable=False),
        sa.Column("confidence_reason", sa.String(length=255), nullable=False),
        sa.Column("created_by_event", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "evidence_references",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("quantity", sa.Numeric(), nullable=True),
        sa.Column("unit", sa.String(length=50), nullable=False, server_default=""),
        sa.Column(
            "relation_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("metadata_version", sa.Integer(), nullable=False, server_default="1"),
        sa.CheckConstraint("metadata_version >= 1", name="ck_relations_metadata_version"),
        sa.CheckConstraint("quantity IS NULL OR quantity >= 0", name="ck_relations_quantity"),
        sa.CheckConstraint(
            "valid_from IS NULL OR valid_until IS NULL OR valid_until >= valid_from",
            name="ck_relations_period",
        ),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_relations_organization",
        ),
        comment="titan.classification=PROTECTED;titan.module_owner=core_audit",
        schema=SCHEMA,
    )

    op.create_index(
        "ix_relations_source",
        RELATIONS_TABLE,
        ["record_owner_organization_id", "source_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_relations_target",
        RELATIONS_TABLE,
        ["record_owner_organization_id", "target_id"],
        schema=SCHEMA,
    )

    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{RELATIONS_TABLE} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{RELATIONS_TABLE} FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            f"""
            CREATE POLICY tenant_isolation_policy ON {SCHEMA}.{RELATIONS_TABLE}
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
        sa.text(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {SCHEMA}.{RELATIONS_TABLE}")
    )
    op.drop_index("ix_relations_target", table_name=RELATIONS_TABLE, schema=SCHEMA)
    op.drop_index("ix_relations_source", table_name=RELATIONS_TABLE, schema=SCHEMA)
    op.drop_table(RELATIONS_TABLE, schema=SCHEMA)
