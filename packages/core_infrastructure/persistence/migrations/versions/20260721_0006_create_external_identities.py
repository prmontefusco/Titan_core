"""Criar vínculos canônicos de identidade externa.

Revision ID: 20260721_0006
Revises: 20260721_0005
Create Date: 2026-07-21

Classificação: PROTECTED
Módulo owner: core_identity
Decisões: ADRs 0002, 0003 e 0005
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260721_0006"
down_revision: str | None = "20260721_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "core_identity"
TABLE = "external_identities"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("external_identity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("issuer", sa.String(length=500), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("principal_type", sa.String(length=30), nullable=False),
        sa.Column("internal_principal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("linked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("linked_by_actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.CheckConstraint("principal_type = 'USER'", name="ck_external_identities_type"),
        sa.CheckConstraint("status IN ('ATIVA', 'SUSPENSA')", name="ck_external_identities_status"),
        sa.ForeignKeyConstraint(
            ["internal_principal_id"],
            ["core_identity.users.user_id"],
            name="fk_external_identities_user",
        ),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_external_identities_owner",
        ),
        sa.PrimaryKeyConstraint("external_identity_id", name="pk_external_identities"),
        sa.UniqueConstraint("issuer", "subject", name="uq_external_identities_issuer_subject"),
        schema=SCHEMA,
    )
    op.execute(
        sa.text(
            "COMMENT ON TABLE core_identity.external_identities IS "
            "'titan.classification=PROTECTED;titan.module_owner=core_identity'"
        )
    )
    op.execute(sa.text("ALTER TABLE core_identity.external_identities ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text("ALTER TABLE core_identity.external_identities FORCE ROW LEVEL SECURITY"))
    context = (
        "record_owner_organization_id = "
        "NULLIF(current_setting('titan.organization_id', true), '')::uuid"
    )
    op.execute(
        sa.text(
            "CREATE POLICY external_identities_select_by_owner ON "
            f"core_identity.external_identities FOR SELECT USING ({context})"
        )
    )
    op.execute(
        sa.text(
            "CREATE POLICY external_identities_insert_by_owner ON "
            f"core_identity.external_identities FOR INSERT WITH CHECK ({context})"
        )
    )
    op.execute(sa.text("REVOKE ALL ON core_identity.external_identities FROM PUBLIC"))


def downgrade() -> None:
    op.execute(
        sa.text(
            "DROP POLICY external_identities_insert_by_owner ON core_identity.external_identities"
        )
    )
    op.execute(
        sa.text(
            "DROP POLICY external_identities_select_by_owner ON core_identity.external_identities"
        )
    )
    op.drop_table(TABLE, schema=SCHEMA)
