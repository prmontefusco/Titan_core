"""Criar User owned pela Organization operadora.

Revision ID: 20260721_0003
Revises: 20260721_0002
Create Date: 2026-07-21

Classificação: PROTECTED
Módulo owner: core_identity
Decisão: ADR 0030
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260721_0003"
down_revision: str | None = "20260721_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "core_identity"
TABLE = "users"


def upgrade() -> None:
    """Cria User sem senha, credencial, Role, Permission ou Membership."""
    op.create_table(
        TABLE,
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_users_record_owner_organization",
        ),
        sa.PrimaryKeyConstraint("user_id", name="pk_users"),
        schema=SCHEMA,
    )
    op.execute(
        sa.text(
            "COMMENT ON TABLE core_identity.users IS "
            "'titan.classification=PROTECTED;titan.module_owner=core_identity'"
        )
    )
    op.execute(sa.text("ALTER TABLE core_identity.users ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text("ALTER TABLE core_identity.users FORCE ROW LEVEL SECURITY"))
    context_expression = (
        "record_owner_organization_id = "
        "NULLIF(current_setting('titan.organization_id', true), '')::uuid"
    )
    op.execute(
        sa.text(
            "CREATE POLICY users_select_by_owner ON core_identity.users FOR SELECT "
            f"USING ({context_expression})"
        )
    )
    op.execute(
        sa.text(
            "CREATE POLICY users_insert_by_owner ON core_identity.users FOR INSERT "
            f"WITH CHECK ({context_expression})"
        )
    )
    op.execute(sa.text("REVOKE ALL ON core_identity.users FROM PUBLIC"))


def downgrade() -> None:
    """Remove somente os objetos de User introduzidos nesta revisão."""
    op.execute(sa.text("DROP POLICY users_insert_by_owner ON core_identity.users"))
    op.execute(sa.text("DROP POLICY users_select_by_owner ON core_identity.users"))
    op.drop_table(TABLE, schema=SCHEMA)
