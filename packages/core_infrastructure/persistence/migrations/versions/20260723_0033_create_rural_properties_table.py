"""Criar tabela core_audit.rural_properties com suporte a RLS (Passo 8.1 - Titan Livestock).

Revision ID: 20260723_0033
Revises: 20260722_0032
Create Date: 2026-07-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260723_0033"
down_revision: str | None = "20260722_0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "core_audit"
PROPERTIES_TABLE = "rural_properties"


def upgrade() -> None:
    op.create_table(
        PROPERTIES_TABLE,
        sa.Column("property_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("municipality", sa.String(length=255), nullable=False),
        sa.Column("state_code", sa.String(length=2), nullable=False),
        sa.Column("registration_number", sa.String(length=255), nullable=True),
        sa.Column("total_area_hectares", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "record_owner_organization_id",
            "code",
            name="uq_rural_properties_org_code",
        ),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_rural_properties_organization",
        ),
        comment="titan.classification=PROTECTED;titan.module_owner=titan_livestock",
        schema=SCHEMA,
    )

    op.create_index(
        "ix_rural_properties_org_code",
        PROPERTIES_TABLE,
        ["record_owner_organization_id", "code"],
        schema=SCHEMA,
    )

    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{PROPERTIES_TABLE} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{PROPERTIES_TABLE} FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            f"""
            CREATE POLICY tenant_isolation_policy ON {SCHEMA}.{PROPERTIES_TABLE}
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
        sa.text(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {SCHEMA}.{PROPERTIES_TABLE}")
    )
    op.drop_index("ix_rural_properties_org_code", table_name=PROPERTIES_TABLE, schema=SCHEMA)
    op.drop_table(PROPERTIES_TABLE, schema=SCHEMA)
