"""Cria Assertions sanitárias de medicamento."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260812_0065"
down_revision = "20260812_0064"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "medication_classification_assertions",
        sa.Column("assertion_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("medication_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category", sa.String(60), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True)),
        sa.Column("valid_to", sa.DateTime(timezone=True)),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_entity_type", sa.String(80), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("confidence_tier", sa.String(50), nullable=False),
        sa.Column("validation_status", sa.String(50), nullable=False),
        sa.Column("limitations", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"], ["core_identity.organizations.organization_id"]
        ),
        sa.ForeignKeyConstraint(["medication_id"], ["core_audit.medications.medication_id"]),
        schema="core_audit",
        comment="titan.classification=PROTECTED;titan.module_owner=livestock",
    )
    op.execute(
        "ALTER TABLE core_audit.medication_classification_assertions ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE core_audit.medication_classification_assertions FORCE ROW LEVEL SECURITY"
    )
    op.execute(
        "CREATE POLICY tenant_isolation_policy ON core_audit.medication_classification_assertions USING (record_owner_organization_id = NULLIF(current_setting('titan.organization_id', true), '')::uuid) WITH CHECK (record_owner_organization_id = NULLIF(current_setting('titan.organization_id', true), '')::uuid)"
    )


def downgrade() -> None:
    op.drop_table("medication_classification_assertions", schema="core_audit")
