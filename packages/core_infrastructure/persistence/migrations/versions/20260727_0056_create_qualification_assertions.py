"""Criar SourceArtifact e EstablishmentQualificationAssertion (ADR-0045).

Revision ID: 20260727_0056
Revises: 20260727_0055
Create Date: 2026-07-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260727_0056"
down_revision: str | Sequence[str] | None = "20260727_0055"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

SCHEMA = "core_audit"
ARTIFACTS_TABLE = "qualification_source_artifacts"
ASSERTIONS_TABLE = "establishment_qualification_assertions"


def _enable_rls(table: str) -> None:
    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{table} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{table} FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            f"""
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
            """
        )
    )


def upgrade() -> None:
    op.create_table(
        ARTIFACTS_TABLE,
        sa.Column("artifact_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source", sa.String(length=120), nullable=False),
        sa.Column("source_version", sa.String(length=120), nullable=False),
        sa.Column("content_hash", sa.String(length=120), nullable=False),
        sa.Column("snapshot_semantics", sa.String(length=40), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_qualification_source_artifacts_organization",
        ),
        sa.UniqueConstraint(
            "record_owner_organization_id",
            "source",
            "source_version",
            name="uq_qualification_source_artifacts_identity",
        ),
        comment="titan.classification=PROTECTED;titan.module_owner=livestock",
        schema=SCHEMA,
    )
    _enable_rls(ARTIFACTS_TABLE)

    op.create_table(
        ASSERTIONS_TABLE,
        sa.Column("assertion_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("establishment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("qualification_type", sa.String(length=120), nullable=False),
        sa.Column("asserted_status", sa.String(length=40), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("effective_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_artifact_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("confidence_tier", sa.String(length=40), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_establishment_qualification_assertions_organization",
        ),
        sa.ForeignKeyConstraint(
            ["establishment_id"],
            [f"{SCHEMA}.external_counterparties.counterparty_id"],
            name="fk_establishment_qualification_assertions_establishment",
        ),
        sa.ForeignKeyConstraint(
            ["source_artifact_id"],
            [f"{SCHEMA}.{ARTIFACTS_TABLE}.artifact_id"],
            name="fk_establishment_qualification_assertions_artifact",
        ),
        comment="titan.classification=PROTECTED;titan.module_owner=livestock",
        schema=SCHEMA,
    )
    _enable_rls(ASSERTIONS_TABLE)

    op.create_index(
        "ix_establishment_qualification_assertions_lookup",
        ASSERTIONS_TABLE,
        ["record_owner_organization_id", "establishment_id", "qualification_type"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_establishment_qualification_assertions_lookup",
        table_name=ASSERTIONS_TABLE,
        schema=SCHEMA,
    )
    op.execute(
        sa.text(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {SCHEMA}.{ASSERTIONS_TABLE}")
    )
    op.drop_table(ASSERTIONS_TABLE, schema=SCHEMA)
    op.execute(
        sa.text(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {SCHEMA}.{ARTIFACTS_TABLE}")
    )
    op.drop_table(ARTIFACTS_TABLE, schema=SCHEMA)
