"""Adiciona projeção revisável e reviews de captura simulada."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from packages.core_infrastructure.persistence.events import CORE_AUDIT_SCHEMA

revision = "20260812_0068"
down_revision = "20260812_0067"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "external_source_capture_artifacts",
        sa.Column("review_projection", postgresql.JSONB(), nullable=True),
        schema=CORE_AUDIT_SCHEMA,
    )
    op.create_table(
        "external_source_capture_association_reviews",
        sa.Column("review_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("capture_artifact_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("candidate_animal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("basis_code", sa.String(120), nullable=False),
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"], ["core_identity.organizations.organization_id"]
        ),
        sa.ForeignKeyConstraint(
            ["capture_artifact_id"], ["core_audit.external_source_capture_artifacts.artifact_id"]
        ),
        sa.ForeignKeyConstraint(["candidate_animal_id"], ["core_audit.animals.animal_id"]),
        schema=CORE_AUDIT_SCHEMA,
        comment="titan.classification=PROTECTED;titan.module_owner=livestock",
    )
    op.execute(
        sa.text(
            "ALTER TABLE core_audit.external_source_capture_association_reviews ENABLE ROW LEVEL SECURITY"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE core_audit.external_source_capture_association_reviews FORCE ROW LEVEL SECURITY"
        )
    )
    op.execute(
        sa.text("""CREATE POLICY tenant_isolation_policy ON core_audit.external_source_capture_association_reviews
        USING (record_owner_organization_id = NULLIF(current_setting('titan.organization_id', true), '')::uuid)
        WITH CHECK (record_owner_organization_id = NULLIF(current_setting('titan.organization_id', true), '')::uuid)""")
    )


def downgrade() -> None:
    op.drop_table("external_source_capture_association_reviews", schema=CORE_AUDIT_SCHEMA)
    op.drop_column(
        "external_source_capture_artifacts", "review_projection", schema=CORE_AUDIT_SCHEMA
    )
