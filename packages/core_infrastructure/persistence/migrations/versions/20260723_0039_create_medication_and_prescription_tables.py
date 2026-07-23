"""Criar tabelas core_audit.medications, core_audit.prescriptions e core_audit.prescription_targets com RLS (Passo 9.1 - Titan Livestock).

Revision ID: 20260723_0039
Revises: 20260723_0038
Create Date: 2026-07-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260723_0039"
down_revision: str | None = "20260723_0038"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "core_audit"
MEDICATIONS_TABLE = "medications"
PRESCRIPTIONS_TABLE = "prescriptions"
TARGETS_TABLE = "prescription_targets"


def upgrade() -> None:
    # 1. Tabela medications
    op.create_table(
        MEDICATIONS_TABLE,
        sa.Column("medication_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("trade_name", sa.String(length=255), nullable=False),
        sa.Column("active_ingredient", sa.String(length=255), nullable=False),
        sa.Column("manufacturer", sa.String(length=255), nullable=False),
        sa.Column("withdrawal_period_days", sa.Integer(), nullable=False),
        sa.Column("dosage_instruction", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "record_owner_organization_id",
            "trade_name",
            name="uq_medications_org_trade_name",
        ),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_medications_organization",
        ),
        comment="titan.classification=PROTECTED;titan.module_owner=titan_livestock",
        schema=SCHEMA,
    )

    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{MEDICATIONS_TABLE} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{MEDICATIONS_TABLE} FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            f"""
            CREATE POLICY tenant_isolation_policy ON {SCHEMA}.{MEDICATIONS_TABLE}
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

    # 2. Tabela prescriptions
    op.create_table(
        PRESCRIPTIONS_TABLE,
        sa.Column("prescription_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("veterinarian_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("medication_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("property_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("prescribed_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("dosage", sa.String(length=255), nullable=False),
        sa.Column("administration_route", sa.String(length=100), nullable=False),
        sa.Column("target_type", sa.String(length=50), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_prescriptions_organization",
        ),
        sa.ForeignKeyConstraint(
            ["veterinarian_id"],
            ["core_audit.veterinarians.veterinarian_id"],
            name="fk_prescriptions_veterinarian",
        ),
        sa.ForeignKeyConstraint(
            ["medication_id"],
            ["core_audit.medications.medication_id"],
            name="fk_prescriptions_medication",
        ),
        sa.ForeignKeyConstraint(
            ["property_id"],
            ["core_audit.rural_properties.property_id"],
            name="fk_prescriptions_property",
        ),
        comment="titan.classification=PROTECTED;titan.module_owner=titan_livestock",
        schema=SCHEMA,
    )

    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{PRESCRIPTIONS_TABLE} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{PRESCRIPTIONS_TABLE} FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            f"""
            CREATE POLICY tenant_isolation_policy ON {SCHEMA}.{PRESCRIPTIONS_TABLE}
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

    # 3. Tabela prescription_targets
    op.create_table(
        TARGETS_TABLE,
        sa.Column("prescription_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_prescription_targets_organization",
        ),
        sa.ForeignKeyConstraint(
            ["prescription_id"],
            ["core_audit.prescriptions.prescription_id"],
            name="fk_prescription_targets_prescription",
        ),
        comment="titan.classification=PROTECTED;titan.module_owner=titan_livestock",
        schema=SCHEMA,
    )

    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{TARGETS_TABLE} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{TARGETS_TABLE} FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            f"""
            CREATE POLICY tenant_isolation_policy ON {SCHEMA}.{TARGETS_TABLE}
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
        sa.text(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {SCHEMA}.{TARGETS_TABLE}")
    )
    op.drop_table(TARGETS_TABLE, schema=SCHEMA)

    op.execute(
        sa.text(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {SCHEMA}.{PRESCRIPTIONS_TABLE}")
    )
    op.drop_table(PRESCRIPTIONS_TABLE, schema=SCHEMA)

    op.execute(
        sa.text(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {SCHEMA}.{MEDICATIONS_TABLE}")
    )
    op.drop_table(MEDICATIONS_TABLE, schema=SCHEMA)
