"""Criar stock_positions/stock_reservations/stock_transfers e projeção com RLS (A3).

Revision ID: 20260911_0007
Revises: 20260911_0006
Create Date: 2026-09-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260911_0007"
down_revision: str | None = "20260911_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "core_audit"
MODULE_OWNER_COMMENT = "titan.classification=PROTECTED;titan.module_owner=asset"
TABLES_IN_CREATION_ORDER = (
    "stock_positions",
    "stock_transfers",
    "stock_position_reservations",
    "stock_reservations",
)


def upgrade() -> None:
    op.create_table(
        "stock_positions",
        sa.Column("stock_position_id", sa.UUID(), nullable=False),
        sa.Column("record_owner_organization_id", sa.UUID(), nullable=False),
        sa.Column("part_id", sa.UUID(), nullable=False),
        sa.Column("location_id", sa.UUID(), nullable=False),
        sa.Column("purpose", sa.String(length=30), nullable=False),
        sa.Column("ownership", sa.String(length=30), nullable=False),
        sa.Column("on_hand", sa.Numeric(), nullable=False),
        sa.Column("in_transit", sa.Numeric(), nullable=False),
        sa.Column("quarantine", sa.Numeric(), nullable=False),
        sa.Column("inspection", sa.Numeric(), nullable=False),
        sa.Column("damaged", sa.Numeric(), nullable=False),
        sa.Column("lot", sa.String(length=100), nullable=True),
        sa.Column("serial", sa.String(length=100), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["location_id"],
            ["core_audit.stock_locations.location_id"],
            name="fk_stock_positions_location",
        ),
        sa.ForeignKeyConstraint(
            ["part_id"], ["core_audit.parts.part_id"], name="fk_stock_positions_part"
        ),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_stock_positions_organization",
        ),
        sa.PrimaryKeyConstraint("stock_position_id"),
        schema=SCHEMA,
        comment=MODULE_OWNER_COMMENT,
    )
    op.create_table(
        "stock_transfers",
        sa.Column("transfer_id", sa.UUID(), nullable=False),
        sa.Column("record_owner_organization_id", sa.UUID(), nullable=False),
        sa.Column("part_id", sa.UUID(), nullable=False),
        sa.Column("from_location_id", sa.UUID(), nullable=False),
        sa.Column("to_location_id", sa.UUID(), nullable=False),
        sa.Column("qty", sa.Numeric(), nullable=False),
        sa.Column("state", sa.String(length=30), nullable=False),
        sa.Column("qty_received", sa.Numeric(), nullable=False),
        sa.Column("linked_reservation_id", sa.UUID(), nullable=True),
        sa.Column("linked_reservation_entity_type", sa.String(length=100), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["from_location_id"],
            ["core_audit.stock_locations.location_id"],
            name="fk_stock_transfers_from_location",
        ),
        sa.ForeignKeyConstraint(
            ["part_id"], ["core_audit.parts.part_id"], name="fk_stock_transfers_part"
        ),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_stock_transfers_organization",
        ),
        sa.ForeignKeyConstraint(
            ["to_location_id"],
            ["core_audit.stock_locations.location_id"],
            name="fk_stock_transfers_to_location",
        ),
        sa.PrimaryKeyConstraint("transfer_id"),
        schema=SCHEMA,
        comment=MODULE_OWNER_COMMENT,
    )
    op.create_table(
        "stock_position_reservations",
        sa.Column("stock_position_id", sa.UUID(), nullable=False),
        sa.Column("reservation_id", sa.UUID(), nullable=False),
        sa.Column("record_owner_organization_id", sa.UUID(), nullable=False),
        sa.Column("demand_ref_id", sa.UUID(), nullable=False),
        sa.Column("demand_ref_entity_type", sa.String(length=100), nullable=False),
        sa.Column("qty", sa.Numeric(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("purpose_lock", sa.String(length=30), nullable=False),
        sa.ForeignKeyConstraint(
            ["stock_position_id"],
            ["core_audit.stock_positions.stock_position_id"],
            name="fk_stock_position_reservations_position",
        ),
        sa.PrimaryKeyConstraint("stock_position_id", "reservation_id"),
        schema=SCHEMA,
        comment=MODULE_OWNER_COMMENT,
    )
    op.create_table(
        "stock_reservations",
        sa.Column("reservation_id", sa.UUID(), nullable=False),
        sa.Column("record_owner_organization_id", sa.UUID(), nullable=False),
        sa.Column("stock_position_id", sa.UUID(), nullable=False),
        sa.Column("demand_kind", sa.String(length=30), nullable=False),
        sa.Column("demand_ref_id", sa.UUID(), nullable=False),
        sa.Column("demand_ref_entity_type", sa.String(length=100), nullable=False),
        sa.Column("qty", sa.Numeric(), nullable=False),
        sa.Column("purpose", sa.String(length=30), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("decision_id", sa.UUID(), nullable=True),
        sa.Column("decision_entity_type", sa.String(length=100), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_stock_reservations_organization",
        ),
        sa.ForeignKeyConstraint(
            ["stock_position_id"],
            ["core_audit.stock_positions.stock_position_id"],
            name="fk_stock_reservations_position",
        ),
        sa.PrimaryKeyConstraint("reservation_id"),
        schema=SCHEMA,
        comment=MODULE_OWNER_COMMENT,
    )

    for table in TABLES_IN_CREATION_ORDER:
        op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{table} ENABLE ROW LEVEL SECURITY"))
        op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{table} FORCE ROW LEVEL SECURITY"))
        op.execute(
            sa.text(f"""
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
            """)
        )


def downgrade() -> None:
    for table in reversed(TABLES_IN_CREATION_ORDER):
        op.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {SCHEMA}.{table}"))

    for table in reversed(TABLES_IN_CREATION_ORDER):
        op.drop_table(table, schema=SCHEMA)
