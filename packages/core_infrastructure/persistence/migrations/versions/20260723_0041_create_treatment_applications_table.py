"""Criar tabela core_audit.treatment_applications com RLS (Passo 9.3 - Titan Livestock).

Revision ID: 20260723_0041
Revises: 20260723_0040
Create Date: 2026-07-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260723_0041"
down_revision: str | None = "20260723_0040"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "core_audit"
APPLICATIONS_TABLE = "treatment_applications"


def upgrade() -> None:
    op.create_table(
        APPLICATIONS_TABLE,
        sa.Column("application_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("animal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("medication_batch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("dose", sa.String(length=255), nullable=True),
        sa.Column(
            "evidence_references",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("prescription_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("corrects_application_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_treatment_applications_organization",
        ),
        sa.ForeignKeyConstraint(
            ["animal_id"],
            ["core_audit.animals.animal_id"],
            name="fk_treatment_applications_animal",
        ),
        sa.ForeignKeyConstraint(
            ["medication_batch_id"],
            ["core_audit.medication_batches.batch_id"],
            name="fk_treatment_applications_batch",
        ),
        sa.ForeignKeyConstraint(
            ["prescription_id"],
            ["core_audit.prescriptions.prescription_id"],
            name="fk_treatment_applications_prescription",
        ),
        sa.ForeignKeyConstraint(
            ["corrects_application_id"],
            ["core_audit.treatment_applications.application_id"],
            name="fk_treatment_applications_corrects",
        ),
        comment="titan.classification=PROTECTED;titan.module_owner=titan_livestock",
        schema=SCHEMA,
    )

    op.create_index(
        "ix_treatment_applications_animal",
        APPLICATIONS_TABLE,
        ["record_owner_organization_id", "animal_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_treatment_applications_batch",
        APPLICATIONS_TABLE,
        ["record_owner_organization_id", "medication_batch_id"],
        schema=SCHEMA,
    )

    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{APPLICATIONS_TABLE} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{APPLICATIONS_TABLE} FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            f"""
            CREATE POLICY tenant_isolation_policy ON {SCHEMA}.{APPLICATIONS_TABLE}
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
        sa.text(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {SCHEMA}.{APPLICATIONS_TABLE}")
    )
    op.drop_index("ix_treatment_applications_batch", table_name=APPLICATIONS_TABLE, schema=SCHEMA)
    op.drop_index("ix_treatment_applications_animal", table_name=APPLICATIONS_TABLE, schema=SCHEMA)
    op.drop_table(APPLICATIONS_TABLE, schema=SCHEMA)
