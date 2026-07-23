"""Criar projeção reconstruível core_audit.reference_projection com suporte a RLS.

Revision ID: 20260722_0028
Revises: 20260722_0027
Create Date: 2026-07-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260722_0028"
down_revision: str | None = "20260722_0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "core_audit"
PROJECTION_TABLE = "reference_projection"


def upgrade() -> None:
    # A chave primária é o próprio conteúdo derivado, sem identificador sorteado:
    # reconstruir produz linhas idênticas e a comparação entre reconstruções é exata.
    op.create_table(
        PROJECTION_TABLE,
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("referenced_entity_type", sa.String(length=100), nullable=False),
        sa.Column("referenced_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("referenced_contract_version", sa.Integer(), nullable=False),
        sa.Column("referencing_kind", sa.String(length=30), nullable=False),
        sa.Column("referencing_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=30), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint(
            "record_owner_organization_id",
            "referenced_id",
            "referencing_kind",
            "referencing_id",
            "role",
            name="pk_reference_projection",
        ),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_reference_projection_organization",
        ),
        comment="titan.classification=PROTECTED;titan.module_owner=core_audit",
        schema=SCHEMA,
    )

    op.create_index(
        "ix_reference_projection_referenced",
        PROJECTION_TABLE,
        ["record_owner_organization_id", "referenced_id"],
        schema=SCHEMA,
    )

    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{PROJECTION_TABLE} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{PROJECTION_TABLE} FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            f"""
            CREATE POLICY tenant_isolation_policy ON {SCHEMA}.{PROJECTION_TABLE}
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
        sa.text(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {SCHEMA}.{PROJECTION_TABLE}")
    )
    op.drop_index("ix_reference_projection_referenced", table_name=PROJECTION_TABLE, schema=SCHEMA)
    op.drop_table(PROJECTION_TABLE, schema=SCHEMA)
