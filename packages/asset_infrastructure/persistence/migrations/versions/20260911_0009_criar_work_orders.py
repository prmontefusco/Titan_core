"""Criar work_orders e tabelas filhas com RLS (A3), fecha A3.

Revision ID: 20260911_0009
Revises: 20260911_0008
Create Date: 2026-09-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260911_0009"
down_revision: str | None = "20260911_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "core_audit"
MODULE_OWNER_COMMENT = "titan.classification=PROTECTED;titan.module_owner=asset"
TABLES_IN_CREATION_ORDER = (
    "work_orders",
    "work_order_removed_components",
    "work_order_tasks",
    "work_order_material_demands",
)


def upgrade() -> None:
    op.create_table(
        "work_orders",
        sa.Column("work_order_id", sa.UUID(), nullable=False),
        sa.Column("record_owner_organization_id", sa.UUID(), nullable=False),
        sa.Column("vehicle_id", sa.UUID(), nullable=False),
        sa.Column("site_id", sa.UUID(), nullable=False),
        sa.Column("contract_ref_id", sa.UUID(), nullable=False),
        sa.Column("contract_version_no", sa.Integer(), nullable=False),
        sa.Column("contract_resolved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("failure_mode", sa.String(length=200), nullable=False),
        sa.Column("failure_reported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("failure_affected_position", sa.String(length=100), nullable=True),
        sa.Column("workshop_id", sa.UUID(), nullable=True),
        sa.Column("workshop_entity_type", sa.String(length=100), nullable=True),
        sa.Column("material_reservations", postgresql.ARRAY(sa.UUID()), nullable=False),
        sa.Column("state", sa.String(length=30), nullable=False),
        sa.Column("pre_wait_authorization_state", sa.String(length=30), nullable=True),
        sa.Column("priority_score", sa.Integer(), nullable=True),
        sa.Column("priority_breakdown", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("priority_evaluation_id", sa.UUID(), nullable=True),
        sa.Column("priority_evaluation_entity_type", sa.String(length=100), nullable=True),
        sa.Column("diagnosis", sa.String(length=2000), nullable=True),
        sa.Column("root_cause", sa.String(length=2000), nullable=True),
        sa.Column("resolution", sa.String(length=2000), nullable=True),
        sa.Column("validation_validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("validation_validator_id", sa.UUID(), nullable=True),
        sa.Column("validation_validator_entity_type", sa.String(length=100), nullable=True),
        sa.Column("validation_result", sa.String(length=20), nullable=True),
        sa.Column("validation_notes", sa.String(length=2000), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["contract_ref_id"],
            ["core_audit.sli_contracts.contract_id"],
            name="fk_work_orders_contract",
        ),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_work_orders_organization",
        ),
        sa.ForeignKeyConstraint(
            ["site_id"], ["core_audit.customer_sites.site_id"], name="fk_work_orders_site"
        ),
        sa.ForeignKeyConstraint(
            ["vehicle_id"], ["core_audit.vehicles.vehicle_id"], name="fk_work_orders_vehicle"
        ),
        sa.PrimaryKeyConstraint("work_order_id"),
        schema=SCHEMA,
        comment=MODULE_OWNER_COMMENT,
    )
    op.create_table(
        "work_order_removed_components",
        sa.Column("work_order_id", sa.UUID(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("record_owner_organization_id", sa.UUID(), nullable=False),
        sa.Column("part_id", sa.UUID(), nullable=False),
        sa.Column("disposition", sa.String(length=200), nullable=False),
        sa.Column("serial", sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(
            ["part_id"],
            ["core_audit.parts.part_id"],
            name="fk_work_order_removed_components_part",
        ),
        sa.ForeignKeyConstraint(
            ["work_order_id"],
            ["core_audit.work_orders.work_order_id"],
            name="fk_work_order_removed_components_work_order",
        ),
        sa.PrimaryKeyConstraint("work_order_id", "ordinal"),
        schema=SCHEMA,
        comment=MODULE_OWNER_COMMENT,
    )
    op.create_table(
        "work_order_tasks",
        sa.Column("task_id", sa.UUID(), nullable=False),
        sa.Column("work_order_id", sa.UUID(), nullable=False),
        sa.Column("record_owner_organization_id", sa.UUID(), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("mandatory", sa.Boolean(), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("labor_entries", postgresql.ARRAY(sa.String()), nullable=False),
        sa.ForeignKeyConstraint(
            ["work_order_id"],
            ["core_audit.work_orders.work_order_id"],
            name="fk_work_order_tasks_work_order",
        ),
        sa.PrimaryKeyConstraint("task_id"),
        schema=SCHEMA,
        comment=MODULE_OWNER_COMMENT,
    )
    op.create_table(
        "work_order_material_demands",
        sa.Column("work_order_id", sa.UUID(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("record_owner_organization_id", sa.UUID(), nullable=False),
        sa.Column("part_id", sa.UUID(), nullable=False),
        sa.Column("qty", sa.Numeric(), nullable=False),
        sa.Column("task_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["part_id"], ["core_audit.parts.part_id"], name="fk_work_order_material_demands_part"
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["core_audit.work_order_tasks.task_id"],
            name="fk_work_order_material_demands_task",
        ),
        sa.ForeignKeyConstraint(
            ["work_order_id"],
            ["core_audit.work_orders.work_order_id"],
            name="fk_work_order_material_demands_work_order",
        ),
        sa.PrimaryKeyConstraint("work_order_id", "ordinal"),
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
