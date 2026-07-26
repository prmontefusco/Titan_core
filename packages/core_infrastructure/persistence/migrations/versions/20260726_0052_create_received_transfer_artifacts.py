"""Criar artefatos recebidos de transferencia.

Revision ID: 20260726_0052
Revises: 20260726_0051
Create Date: 2026-07-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260726_0052"
down_revision: str | None = "20260726_0051"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "core_audit"
TABLE = "received_transfer_artifacts"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("artifact_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("animal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_counterparty_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bundle_digest", sa.String(length=128), nullable=False),
        sa.Column("bundle_issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("transfer_effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("coverage_known_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("coverage_known_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("coverage_gaps", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("issuer_name", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_received_transfer_artifacts_organization",
        ),
        sa.ForeignKeyConstraint(
            ["animal_id"],
            ["core_audit.animals.animal_id"],
            name="fk_received_transfer_artifacts_animal",
        ),
        sa.ForeignKeyConstraint(
            ["source_counterparty_id"],
            ["core_audit.external_counterparties.counterparty_id"],
            name="fk_received_transfer_artifacts_counterparty",
        ),
        comment="titan.classification=PROTECTED;titan.module_owner=livestock",
        schema=SCHEMA,
    )
    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{TABLE} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{TABLE} FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            f"""
            CREATE POLICY tenant_isolation_policy ON {SCHEMA}.{TABLE}
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
    op.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {SCHEMA}.{TABLE}"))
    op.drop_table(TABLE, schema=SCHEMA)
