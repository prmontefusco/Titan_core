"""Criar Membership temporal protegida.

Revision ID: 20260721_0004
Revises: 20260721_0003
Create Date: 2026-07-21

Classificação: PROTECTED
Módulo owner: core_identity
Decisões: ADRs 0002, 0003 e 0005
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260721_0004"
down_revision: str | None = "20260721_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "core_identity"
TABLE = "memberships"


def upgrade() -> None:
    """Cria o vínculo humano sem antecipar Role ou Permission."""
    op.create_table(
        TABLE,
        sa.Column("membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("origin_reference_type", sa.String(length=100), nullable=False),
        sa.Column("origin_reference_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("granted_by_actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.CheckConstraint(
            "record_owner_organization_id = organization_id",
            name="ck_memberships_owner_is_linked_organization",
        ),
        sa.CheckConstraint(
            "valid_until IS NULL OR valid_until > valid_from",
            name="ck_memberships_valid_interval",
        ),
        sa.CheckConstraint(
            "status IN ('ATIVA', 'SUSPENSA', 'ENCERRADA', 'SUBSTITUIDA')",
            name="ck_memberships_status",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["core_identity.users.user_id"], name="fk_memberships_user"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_memberships_organization",
        ),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_memberships_record_owner_organization",
        ),
        sa.PrimaryKeyConstraint("membership_id", name="pk_memberships"),
        schema=SCHEMA,
    )
    op.execute(
        sa.text(
            "COMMENT ON TABLE core_identity.memberships IS "
            "'titan.classification=PROTECTED;titan.module_owner=core_identity'"
        )
    )
    op.execute(sa.text("ALTER TABLE core_identity.memberships ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text("ALTER TABLE core_identity.memberships FORCE ROW LEVEL SECURITY"))
    context_expression = (
        "record_owner_organization_id = "
        "NULLIF(current_setting('titan.organization_id', true), '')::uuid"
    )
    op.execute(
        sa.text(
            "CREATE POLICY memberships_select_by_owner ON core_identity.memberships "
            f"FOR SELECT USING ({context_expression})"
        )
    )
    op.execute(
        sa.text(
            "CREATE POLICY memberships_insert_by_owner ON core_identity.memberships "
            f"FOR INSERT WITH CHECK ({context_expression})"
        )
    )
    op.execute(sa.text("REVOKE ALL ON core_identity.memberships FROM PUBLIC"))


def downgrade() -> None:
    """Remove somente os objetos introduzidos nesta revisão."""
    op.execute(sa.text("DROP POLICY memberships_insert_by_owner ON core_identity.memberships"))
    op.execute(sa.text("DROP POLICY memberships_select_by_owner ON core_identity.memberships"))
    op.drop_table(TABLE, schema=SCHEMA)
