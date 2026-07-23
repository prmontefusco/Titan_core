"""Criar tabelas core_audit.animal_movements, core_audit.animal_movement_items e core_audit.property_stays com RLS (Passo 8.3 - Titan Livestock).

Revision ID: 20260723_0036
Revises: 20260723_0035
Create Date: 2026-07-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260723_0036"
down_revision: str | None = "20260723_0035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "core_audit"
MOVEMENTS_TABLE = "animal_movements"
MOVEMENT_ITEMS_TABLE = "animal_movement_items"
STAYS_TABLE = "property_stays"


def upgrade() -> None:
    # 1. Tabela animal_movements
    op.create_table(
        MOVEMENTS_TABLE,
        sa.Column("movement_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("origin_property_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("destination_property_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("movement_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("evidence_reference", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_animal_movements_organization",
        ),
        sa.ForeignKeyConstraint(
            ["origin_property_id"],
            ["core_audit.rural_properties.property_id"],
            name="fk_animal_movements_origin_property",
        ),
        sa.ForeignKeyConstraint(
            ["destination_property_id"],
            ["core_audit.rural_properties.property_id"],
            name="fk_animal_movements_destination_property",
        ),
        comment="titan.classification=PROTECTED;titan.module_owner=titan_livestock",
        schema=SCHEMA,
    )

    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{MOVEMENTS_TABLE} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{MOVEMENTS_TABLE} FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            f"""
            CREATE POLICY tenant_isolation_policy ON {SCHEMA}.{MOVEMENTS_TABLE}
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

    # 2. Tabela animal_movement_items
    op.create_table(
        MOVEMENT_ITEMS_TABLE,
        sa.Column("movement_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("animal_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["movement_id"],
            ["core_audit.animal_movements.movement_id"],
            name="fk_animal_movement_items_movement",
        ),
        sa.ForeignKeyConstraint(
            ["animal_id"],
            ["core_audit.animals.animal_id"],
            name="fk_animal_movement_items_animal",
        ),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_animal_movement_items_organization",
        ),
        comment="titan.classification=PROTECTED;titan.module_owner=titan_livestock",
        schema=SCHEMA,
    )

    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{MOVEMENT_ITEMS_TABLE} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{MOVEMENT_ITEMS_TABLE} FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            f"""
            CREATE POLICY tenant_isolation_policy ON {SCHEMA}.{MOVEMENT_ITEMS_TABLE}
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

    # 3. Tabela property_stays
    op.create_table(
        STAYS_TABLE,
        sa.Column("stay_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("animal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("property_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("source_movement_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_property_stays_organization",
        ),
        sa.ForeignKeyConstraint(
            ["animal_id"],
            ["core_audit.animals.animal_id"],
            name="fk_property_stays_animal",
        ),
        sa.ForeignKeyConstraint(
            ["property_id"],
            ["core_audit.rural_properties.property_id"],
            name="fk_property_stays_property",
        ),
        sa.ForeignKeyConstraint(
            ["source_movement_id"],
            ["core_audit.animal_movements.movement_id"],
            name="fk_property_stays_source_movement",
        ),
        comment="titan.classification=PROTECTED;titan.module_owner=titan_livestock",
        schema=SCHEMA,
    )

    op.create_index(
        "ix_property_stays_animal_status",
        STAYS_TABLE,
        ["record_owner_organization_id", "animal_id", "status"],
        schema=SCHEMA,
    )

    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{STAYS_TABLE} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{STAYS_TABLE} FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            f"""
            CREATE POLICY tenant_isolation_policy ON {SCHEMA}.{STAYS_TABLE}
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
    op.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {SCHEMA}.{STAYS_TABLE}"))
    op.drop_index("ix_property_stays_animal_status", table_name=STAYS_TABLE, schema=SCHEMA)
    op.drop_table(STAYS_TABLE, schema=SCHEMA)

    op.execute(
        sa.text(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {SCHEMA}.{MOVEMENT_ITEMS_TABLE}")
    )
    op.drop_table(MOVEMENT_ITEMS_TABLE, schema=SCHEMA)

    op.execute(
        sa.text(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {SCHEMA}.{MOVEMENTS_TABLE}")
    )
    op.drop_table(MOVEMENTS_TABLE, schema=SCHEMA)
