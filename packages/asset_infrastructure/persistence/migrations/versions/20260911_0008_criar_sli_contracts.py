"""Criar sli_contracts/contract_versions/contract_version_coverage_lines com RLS (A3).

Revision ID: 20260911_0008
Revises: 20260911_0007
Create Date: 2026-09-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260911_0008"
down_revision: str | None = "20260911_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "core_audit"
MODULE_OWNER_COMMENT = "titan.classification=PROTECTED;titan.module_owner=asset"
TABLES_IN_CREATION_ORDER = (
    "sli_contracts",
    "contract_versions",
    "contract_version_coverage_lines",
)


def upgrade() -> None:
    op.create_table(
        "sli_contracts",
        sa.Column("contract_id", sa.UUID(), nullable=False),
        sa.Column("record_owner_organization_id", sa.UUID(), nullable=False),
        sa.Column("customer_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_sli_contracts_organization",
        ),
        sa.PrimaryKeyConstraint("contract_id"),
        schema=SCHEMA,
        comment=MODULE_OWNER_COMMENT,
    )
    op.create_table(
        "contract_versions",
        sa.Column("contract_id", sa.UUID(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("record_owner_organization_id", sa.UUID(), nullable=False),
        sa.Column("effective_valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_known_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("response_sla_duration", sa.Interval(), nullable=True),
        sa.Column("response_sla_clock_start_event", sa.String(length=100), nullable=True),
        sa.Column("response_sla_clock_stop_event", sa.String(length=100), nullable=True),
        sa.Column("response_sla_pause_conditions", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("repair_sla_duration", sa.Interval(), nullable=True),
        sa.Column("repair_sla_clock_start_event", sa.String(length=100), nullable=True),
        sa.Column("repair_sla_clock_stop_event", sa.String(length=100), nullable=True),
        sa.Column("repair_sla_pause_conditions", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("availability_target_percentage", sa.Numeric(), nullable=True),
        sa.Column("service_limits_max_services_per_period", sa.Integer(), nullable=True),
        sa.Column("service_limits_period_days", sa.Integer(), nullable=True),
        sa.Column("amendment_id", sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(
            ["contract_id"],
            ["core_audit.sli_contracts.contract_id"],
            name="fk_contract_versions_contract",
        ),
        sa.PrimaryKeyConstraint("contract_id", "version_no"),
        schema=SCHEMA,
        comment=MODULE_OWNER_COMMENT,
    )
    op.create_table(
        "contract_version_coverage_lines",
        sa.Column("contract_id", sa.UUID(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("record_owner_organization_id", sa.UUID(), nullable=False),
        sa.Column("scope", sa.String(length=20), nullable=False),
        sa.Column("scope_value", sa.String(length=200), nullable=False),
        sa.Column("covered_services", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("covered_parts", postgresql.ARRAY(sa.UUID()), nullable=False),
        sa.Column("excluded_parts", postgresql.ARRAY(sa.UUID()), nullable=False),
        sa.Column("labor_rules", sa.String(length=500), nullable=True),
        sa.Column("travel_rules", sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(
            ["contract_id", "version_no"],
            [
                "core_audit.contract_versions.contract_id",
                "core_audit.contract_versions.version_no",
            ],
            name="fk_contract_version_coverage_lines_version",
        ),
        sa.PrimaryKeyConstraint("contract_id", "version_no", "ordinal"),
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
