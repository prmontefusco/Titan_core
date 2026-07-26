"""Criar contraparte externa e referencia na saida.

Revision ID: 20260726_0051
Revises: 20260726_0050
Create Date: 2026-07-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260726_0051"
down_revision: str | None = "20260726_0050"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "core_audit"
COUNTERPARTIES = "external_counterparties"
EXITS = "animal_exits"


def upgrade() -> None:
    op.create_table(
        COUNTERPARTIES,
        sa.Column("counterparty_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("counterparty_type", sa.String(length=40), nullable=False),
        sa.Column("identifiers", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("evidence_references", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_external_counterparties_organization",
        ),
        comment="titan.classification=PROTECTED;titan.module_owner=livestock",
        schema=SCHEMA,
    )
    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{COUNTERPARTIES} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{COUNTERPARTIES} FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            f"""
            CREATE POLICY tenant_isolation_policy ON {SCHEMA}.{COUNTERPARTIES}
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

    op.add_column(
        EXITS,
        sa.Column("destination_counterparty_id", postgresql.UUID(as_uuid=True), nullable=True),
        schema=SCHEMA,
    )
    op.create_foreign_key(
        "fk_animal_exits_destination_counterparty",
        EXITS,
        COUNTERPARTIES,
        ["destination_counterparty_id"],
        ["counterparty_id"],
        source_schema=SCHEMA,
        referent_schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_animal_exits_destination_counterparty", EXITS, schema=SCHEMA, type_="foreignkey"
    )
    op.drop_column(EXITS, "destination_counterparty_id", schema=SCHEMA)
    op.execute(
        sa.text(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {SCHEMA}.{COUNTERPARTIES}")
    )
    op.drop_table(COUNTERPARTIES, schema=SCHEMA)
