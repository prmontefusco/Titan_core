"""Cria contribuições dimensionais source-neutral de coverage."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from packages.core_infrastructure.persistence.events import CORE_AUDIT_SCHEMA

revision = "20260812_0064"
down_revision = "20260731_0063"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "coverage_contributions",
        sa.Column("contribution_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dimension", sa.String(120), nullable=False),
        sa.Column("covered_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("covered_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("validation", sa.String(40), nullable=False),
        sa.Column("admissibility", sa.String(40), nullable=False),
        sa.Column("source_entity_type", sa.String(80), nullable=True),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("accessible", sa.Boolean(), nullable=False),
        sa.Column("conflicting", sa.Boolean(), nullable=False),
        sa.Column("recorded_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"], ["core_identity.organizations.organization_id"]
        ),
        sa.ForeignKeyConstraint(["subject_id"], ["core_audit.animals.animal_id"]),
        schema=CORE_AUDIT_SCHEMA,
        comment="titan.classification=PROTECTED;titan.module_owner=livestock",
    )
    op.execute(sa.text("ALTER TABLE core_audit.coverage_contributions ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text("ALTER TABLE core_audit.coverage_contributions FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text("""
        CREATE POLICY tenant_isolation_policy ON core_audit.coverage_contributions
        USING (record_owner_organization_id = NULLIF(current_setting('titan.organization_id', true), '')::uuid)
        WITH CHECK (record_owner_organization_id = NULLIF(current_setting('titan.organization_id', true), '')::uuid)
    """)
    )
    op.create_index(
        "ix_coverage_contributions_subject_dimension",
        "coverage_contributions",
        ["record_owner_organization_id", "subject_id", "dimension", "covered_from"],
        schema=CORE_AUDIT_SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_coverage_contributions_subject_dimension",
        table_name="coverage_contributions",
        schema=CORE_AUDIT_SCHEMA,
    )
    op.drop_table("coverage_contributions", schema=CORE_AUDIT_SCHEMA)
