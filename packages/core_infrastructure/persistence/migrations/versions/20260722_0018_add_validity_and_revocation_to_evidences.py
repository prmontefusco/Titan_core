"""Adicionar campos de validade, revogação e tabela de verificações em core_audit.

Revision ID: 20260722_0018
Revises: 20260722_0017
Create Date: 2026-07-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260722_0018"
down_revision: str | None = "20260722_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "core_audit"
EVIDENCES_TABLE = "evidences"
VERIFICATIONS_TABLE = "evidence_verifications"


def upgrade() -> None:
    # 1. Adicionar colunas de validade e revogação em core_audit.evidences
    op.add_column(
        EVIDENCES_TABLE,
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        EVIDENCES_TABLE,
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        EVIDENCES_TABLE,
        sa.Column("is_revoked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        schema=SCHEMA,
    )
    op.add_column(
        EVIDENCES_TABLE,
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        EVIDENCES_TABLE,
        sa.Column("revoking_actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        EVIDENCES_TABLE,
        sa.Column("revoking_actor_org_id", postgresql.UUID(as_uuid=True), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        EVIDENCES_TABLE,
        sa.Column("revoking_actor_contract_version", sa.Integer(), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        EVIDENCES_TABLE,
        sa.Column("revocation_reason", sa.Text(), nullable=True),
        schema=SCHEMA,
    )

    # 2. Criar tabela core_audit.evidence_verifications
    op.create_table(
        VERIFICATIONS_TABLE,
        sa.Column("verification_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("evidence_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verifier_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("verifier_org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("verifier_contract_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("outcome", sa.String(length=50), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["evidence_id"],
            [f"{SCHEMA}.{EVIDENCES_TABLE}.evidence_id"],
            name="fk_evidence_verifications_evidence",
        ),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_evidence_verifications_organization",
        ),
        comment="titan.classification=PROTECTED;titan.module_owner=core_audit",
        schema=SCHEMA,
    )

    # 3. Habilitar RLS em core_audit.evidence_verifications
    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{VERIFICATIONS_TABLE} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{VERIFICATIONS_TABLE} FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            f"""
            CREATE POLICY tenant_isolation_policy ON {SCHEMA}.{VERIFICATIONS_TABLE}
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
        sa.text(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {SCHEMA}.{VERIFICATIONS_TABLE}")
    )
    op.drop_table(VERIFICATIONS_TABLE, schema=SCHEMA)

    op.drop_column(EVIDENCES_TABLE, "revocation_reason", schema=SCHEMA)
    op.drop_column(EVIDENCES_TABLE, "revoking_actor_contract_version", schema=SCHEMA)
    op.drop_column(EVIDENCES_TABLE, "revoking_actor_org_id", schema=SCHEMA)
    op.drop_column(EVIDENCES_TABLE, "revoking_actor_id", schema=SCHEMA)
    op.drop_column(EVIDENCES_TABLE, "revoked_at", schema=SCHEMA)
    op.drop_column(EVIDENCES_TABLE, "is_revoked", schema=SCHEMA)
    op.drop_column(EVIDENCES_TABLE, "valid_until", schema=SCHEMA)
    op.drop_column(EVIDENCES_TABLE, "valid_from", schema=SCHEMA)
