"""Criar Organization protegida por RLS.

Revision ID: 20260721_0002
Revises: 20260721_0001
Create Date: 2026-07-21

Classificação: PROTECTED
Módulo owner: core_identity
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260721_0002"
down_revision: str | None = "20260721_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "core_identity"
TABLE = "organizations"


def upgrade() -> None:
    """Cria a tabela PROTECTED e nega acesso sem Organization contextualizada."""
    op.execute(sa.text(f"CREATE SCHEMA {SCHEMA}"))
    op.execute(sa.text(f"REVOKE ALL ON SCHEMA {SCHEMA} FROM PUBLIC"))
    op.create_table(
        TABLE,
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.CheckConstraint(
            "record_owner_organization_id = organization_id",
            name="ck_organizations_self_owned",
        ),
        sa.PrimaryKeyConstraint("organization_id", name="pk_organizations"),
        schema=SCHEMA,
    )
    op.execute(
        sa.text(
            "COMMENT ON TABLE core_identity.organizations IS "
            "'titan.classification=PROTECTED;titan.module_owner=core_identity'"
        )
    )
    op.execute(sa.text("ALTER TABLE core_identity.organizations ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text("ALTER TABLE core_identity.organizations FORCE ROW LEVEL SECURITY"))
    context_expression = (
        "record_owner_organization_id = "
        "NULLIF(current_setting('titan.organization_id', true), '')::uuid"
    )
    op.execute(
        sa.text(
            "CREATE POLICY organizations_select_by_owner "
            "ON core_identity.organizations FOR SELECT "
            f"USING ({context_expression})"
        )
    )
    op.execute(
        sa.text(
            "CREATE POLICY organizations_insert_by_owner "
            "ON core_identity.organizations FOR INSERT "
            f"WITH CHECK ({context_expression})"
        )
    )
    op.execute(sa.text("REVOKE ALL ON core_identity.organizations FROM PUBLIC"))


def downgrade() -> None:
    """Remove somente os objetos introduzidos por esta revisão."""
    op.execute(sa.text("DROP POLICY organizations_insert_by_owner ON core_identity.organizations"))
    op.execute(sa.text("DROP POLICY organizations_select_by_owner ON core_identity.organizations"))
    op.drop_table(TABLE, schema=SCHEMA)
    op.execute(sa.text(f"DROP SCHEMA {SCHEMA}"))
