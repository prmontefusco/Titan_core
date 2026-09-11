"""Criar vehicles/vehicle_meter_readings/vehicle_meter_corrections com RLS (A3).

Revision ID: 20260911_0006
Revises: 20260911_0005
Create Date: 2026-09-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260911_0006"
down_revision: str | None = "20260911_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "core_audit"
MODULE_OWNER_COMMENT = "titan.classification=PROTECTED;titan.module_owner=asset"
TABLES_IN_CREATION_ORDER = ("vehicles", "vehicle_meter_readings", "vehicle_meter_corrections")


def upgrade() -> None:
    op.create_table(
        "vehicles",
        sa.Column("vehicle_id", sa.UUID(), nullable=False),
        sa.Column("record_owner_organization_id", sa.UUID(), nullable=False),
        sa.Column("model_id", sa.UUID(), nullable=False),
        sa.Column("serial_number", sa.String(length=100), nullable=False),
        sa.Column("chassis", sa.String(length=100), nullable=True),
        sa.Column("fleet_number", sa.String(length=50), nullable=True),
        sa.Column("ownership", sa.String(length=20), nullable=False),
        sa.Column("variant_id", sa.UUID(), nullable=True),
        sa.Column("site_id", sa.UUID(), nullable=True),
        sa.Column("current_baseline_id", sa.UUID(), nullable=True),
        sa.Column("baseline_valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lifecycle_state", sa.String(length=30), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["current_baseline_id"],
            ["core_audit.configuration_baselines.baseline_id"],
            name="fk_vehicles_current_baseline",
        ),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_vehicles_organization",
        ),
        sa.ForeignKeyConstraint(
            ["site_id"], ["core_audit.customer_sites.site_id"], name="fk_vehicles_site"
        ),
        sa.PrimaryKeyConstraint("vehicle_id"),
        schema=SCHEMA,
        comment=MODULE_OWNER_COMMENT,
    )
    op.create_table(
        "vehicle_meter_readings",
        sa.Column("reading_id", sa.UUID(), nullable=False),
        sa.Column("vehicle_id", sa.UUID(), nullable=False),
        sa.Column("record_owner_organization_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("value", sa.Numeric(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.ForeignKeyConstraint(
            ["vehicle_id"],
            ["core_audit.vehicles.vehicle_id"],
            name="fk_vehicle_meter_readings_vehicle",
        ),
        sa.PrimaryKeyConstraint("reading_id"),
        schema=SCHEMA,
        comment=MODULE_OWNER_COMMENT,
    )
    op.create_table(
        "vehicle_meter_corrections",
        sa.Column("correction_id", sa.UUID(), nullable=False),
        sa.Column("vehicle_id", sa.UUID(), nullable=False),
        sa.Column("record_owner_organization_id", sa.UUID(), nullable=False),
        sa.Column("original_reading_id", sa.UUID(), nullable=False),
        sa.Column("corrected_value", sa.Numeric(), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("corrected_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["original_reading_id"],
            ["core_audit.vehicle_meter_readings.reading_id"],
            name="fk_vehicle_meter_corrections_reading",
        ),
        sa.ForeignKeyConstraint(
            ["vehicle_id"],
            ["core_audit.vehicles.vehicle_id"],
            name="fk_vehicle_meter_corrections_vehicle",
        ),
        sa.PrimaryKeyConstraint("correction_id"),
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
