"""Criar tabela core_audit.recalls com suporte a RLS.

Revision ID: 20260722_0030
Revises: 20260722_0029
Create Date: 2026-07-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260722_0030"
down_revision: str | None = "20260722_0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "core_audit"
RECALLS_TABLE = "recalls"


def upgrade() -> None:
    op.create_table(
        RECALLS_TABLE,
        sa.Column("recall_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subject_entity_type", sa.String(length=100), nullable=False),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("direction", sa.String(length=30), nullable=False),
        sa.Column("mode", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("visited_nodes", sa.Integer(), nullable=False),
        sa.Column("result_document", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.CheckConstraint("visited_nodes >= 0", name="ck_recalls_visited_nodes"),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_recalls_organization",
        ),
        comment="titan.classification=PROTECTED;titan.module_owner=core_audit",
        schema=SCHEMA,
    )

    op.create_index(
        "ix_recalls_subject",
        RECALLS_TABLE,
        ["record_owner_organization_id", "subject_id"],
        schema=SCHEMA,
    )

    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{RECALLS_TABLE} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{RECALLS_TABLE} FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            f"""
            CREATE POLICY tenant_isolation_policy ON {SCHEMA}.{RECALLS_TABLE}
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
        sa.text(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {SCHEMA}.{RECALLS_TABLE}")
    )
    op.drop_index("ix_recalls_subject", table_name=RECALLS_TABLE, schema=SCHEMA)
    op.drop_table(RECALLS_TABLE, schema=SCHEMA)
