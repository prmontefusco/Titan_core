"""Criar TransformationEvent e TraceableItem (ADR-0046, Passo 11.2).

Revision ID: 20260728_0057
Revises: 20260727_0056
Create Date: 2026-07-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260728_0057"
down_revision: str | Sequence[str] | None = "20260727_0056"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

SCHEMA = "core_audit"
EVENTS_TABLE = "transformation_events"
ITEMS_TABLE = "traceable_items"


def _enable_rls(table: str) -> None:
    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{table} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{table} FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            f"""
            CREATE POLICY tenant_isolation_policy ON {SCHEMA}.{table}
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


def upgrade() -> None:
    op.create_table(
        EVENTS_TABLE,
        sa.Column("event_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("process_type", sa.String(length=40), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("facility_reference", postgresql.JSONB(), nullable=False),
        sa.Column("operator_reference", postgresql.JSONB(), nullable=True),
        sa.Column(
            "source_artifact_references", postgresql.JSONB(), nullable=False, server_default="[]"
        ),
        sa.Column("inputs", postgresql.JSONB(), nullable=False),
        sa.Column("outputs", postgresql.JSONB(), nullable=False),
        sa.Column("balance", postgresql.JSONB(), nullable=True),
        sa.Column("evidence_references", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_transformation_events_organization",
        ),
        comment="titan.classification=PROTECTED;titan.module_owner=livestock",
        schema=SCHEMA,
    )
    _enable_rls(EVENTS_TABLE)

    op.create_table(
        ITEMS_TABLE,
        sa.Column("item_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("item_type", sa.String(length=40), nullable=False),
        sa.Column("created_by_transformation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("label", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_traceable_items_organization",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_transformation_id"],
            [f"{SCHEMA}.{EVENTS_TABLE}.event_id"],
            name="fk_traceable_items_transformation",
        ),
        comment="titan.classification=PROTECTED;titan.module_owner=livestock",
        schema=SCHEMA,
    )
    _enable_rls(ITEMS_TABLE)

    op.create_index(
        "ix_traceable_items_transformation",
        ITEMS_TABLE,
        ["record_owner_organization_id", "created_by_transformation_id"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_traceable_items_transformation",
        table_name=ITEMS_TABLE,
        schema=SCHEMA,
    )
    op.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {SCHEMA}.{ITEMS_TABLE}"))
    op.drop_table(ITEMS_TABLE, schema=SCHEMA)
    op.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {SCHEMA}.{EVENTS_TABLE}"))
    op.drop_table(EVENTS_TABLE, schema=SCHEMA)
