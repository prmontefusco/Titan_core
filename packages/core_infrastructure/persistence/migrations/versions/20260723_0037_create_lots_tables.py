"""Criar tabelas core_audit.livestock_lots e core_audit.lot_memberships com RLS (Passo 8.4 - Titan Livestock).

Revision ID: 20260723_0037
Revises: 20260723_0036
Create Date: 2026-07-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260723_0037"
down_revision: str | None = "20260723_0036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "core_audit"
LOTS_TABLE = "livestock_lots"
MEMBERSHIPS_TABLE = "lot_memberships"


def upgrade() -> None:
    # 1. Tabela livestock_lots
    op.create_table(
        LOTS_TABLE,
        sa.Column("lot_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("property_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("lot_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "record_owner_organization_id",
            "code",
            name="uq_livestock_lots_org_code",
        ),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_livestock_lots_organization",
        ),
        sa.ForeignKeyConstraint(
            ["property_id"],
            ["core_audit.rural_properties.property_id"],
            name="fk_livestock_lots_property",
        ),
        comment="titan.classification=PROTECTED;titan.module_owner=titan_livestock",
        schema=SCHEMA,
    )

    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{LOTS_TABLE} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{LOTS_TABLE} FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            f"""
            CREATE POLICY tenant_isolation_policy ON {SCHEMA}.{LOTS_TABLE}
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

    # 2. Tabela lot_memberships
    op.create_table(
        MEMBERSHIPS_TABLE,
        sa.Column("membership_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("lot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("animal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_lot_memberships_organization",
        ),
        sa.ForeignKeyConstraint(
            ["lot_id"],
            ["core_audit.livestock_lots.lot_id"],
            name="fk_lot_memberships_lot",
        ),
        sa.ForeignKeyConstraint(
            ["animal_id"],
            ["core_audit.animals.animal_id"],
            name="fk_lot_memberships_animal",
        ),
        comment="titan.classification=PROTECTED;titan.module_owner=titan_livestock",
        schema=SCHEMA,
    )

    op.create_index(
        "ix_lot_memberships_animal_active",
        MEMBERSHIPS_TABLE,
        ["record_owner_organization_id", "animal_id", "valid_until"],
        schema=SCHEMA,
    )

    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{MEMBERSHIPS_TABLE} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{MEMBERSHIPS_TABLE} FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            f"""
            CREATE POLICY tenant_isolation_policy ON {SCHEMA}.{MEMBERSHIPS_TABLE}
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
        sa.text(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {SCHEMA}.{MEMBERSHIPS_TABLE}")
    )
    op.drop_index("ix_lot_memberships_animal_active", table_name=MEMBERSHIPS_TABLE, schema=SCHEMA)
    op.drop_table(MEMBERSHIPS_TABLE, schema=SCHEMA)

    op.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {SCHEMA}.{LOTS_TABLE}"))
    op.drop_table(LOTS_TABLE, schema=SCHEMA)
