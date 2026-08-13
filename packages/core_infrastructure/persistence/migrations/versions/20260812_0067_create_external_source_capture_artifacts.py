"""Cria artefatos append-only de captura externa simulada (ADR-0058)."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from packages.core_infrastructure.persistence.events import CORE_AUDIT_SCHEMA

revision = "20260812_0067"
down_revision = "20260812_0066"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "external_source_capture_artifacts",
        sa.Column("artifact_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_profile_code", sa.String(120), nullable=False),
        sa.Column("source_environment", sa.String(40), nullable=False),
        sa.Column("contract_version", sa.String(120), nullable=False),
        sa.Column("resource_kind", sa.String(40), nullable=False),
        sa.Column("request_scope_digest", sa.String(64), nullable=False),
        sa.Column("transport_outcome", sa.String(40), nullable=False),
        sa.Column("response_status_code", sa.Integer(), nullable=True),
        sa.Column("response_digest", sa.String(64), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("parser_name", sa.String(120), nullable=False),
        sa.Column("parser_version", sa.String(40), nullable=False),
        sa.Column("parsing_diagnostic_code", sa.String(120), nullable=True),
        sa.Column("recorded_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"], ["core_identity.organizations.organization_id"]
        ),
        schema=CORE_AUDIT_SCHEMA,
        comment="titan.classification=PROTECTED;titan.module_owner=livestock",
    )
    op.execute(
        sa.text(
            "ALTER TABLE core_audit.external_source_capture_artifacts ENABLE ROW LEVEL SECURITY"
        )
    )
    op.execute(
        sa.text("ALTER TABLE core_audit.external_source_capture_artifacts FORCE ROW LEVEL SECURITY")
    )
    op.execute(
        sa.text("""CREATE POLICY tenant_isolation_policy ON core_audit.external_source_capture_artifacts
        USING (record_owner_organization_id = NULLIF(current_setting('titan.organization_id', true), '')::uuid)
        WITH CHECK (record_owner_organization_id = NULLIF(current_setting('titan.organization_id', true), '')::uuid)""")
    )
    op.create_index(
        "ix_external_source_capture_artifacts_organization_captured",
        "external_source_capture_artifacts",
        ["record_owner_organization_id", "captured_at"],
        schema=CORE_AUDIT_SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_external_source_capture_artifacts_organization_captured",
        table_name="external_source_capture_artifacts",
        schema=CORE_AUDIT_SCHEMA,
    )
    op.drop_table("external_source_capture_artifacts", schema=CORE_AUDIT_SCHEMA)
