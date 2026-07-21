"""Criar catálogo de Permission, Roles e atribuições temporais.

Revision ID: 20260721_0005
Revises: 20260721_0004
Create Date: 2026-07-21

Classificações: REFERENCE_CATALOG e PROTECTED
Módulo owner: core_identity
Decisão: ADR 0031
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260721_0005"
down_revision: str | None = "20260721_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "core_identity"
PROTECTED_TABLES = (
    "roles",
    "role_permissions",
    "membership_role_assignments",
    "membership_role_revocations",
)


def _protect(table: str) -> None:
    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{table} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{table} FORCE ROW LEVEL SECURITY"))
    context = (
        "record_owner_organization_id = "
        "NULLIF(current_setting('titan.organization_id', true), '')::uuid"
    )
    op.execute(
        sa.text(
            f"CREATE POLICY {table}_select_by_owner ON {SCHEMA}.{table} "
            f"FOR SELECT USING ({context})"
        )
    )
    op.execute(
        sa.text(
            f"CREATE POLICY {table}_insert_by_owner ON {SCHEMA}.{table} "
            f"FOR INSERT WITH CHECK ({context})"
        )
    )
    op.execute(sa.text(f"REVOKE ALL ON {SCHEMA}.{table} FROM PUBLIC"))


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_memberships_id_organization",
        "memberships",
        ["membership_id", "organization_id"],
        schema=SCHEMA,
    )
    op.create_table(
        "permissions",
        sa.Column("permission_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_permissions_owner",
        ),
        sa.PrimaryKeyConstraint("permission_id"),
        sa.UniqueConstraint("code"),
        schema=SCHEMA,
    )
    op.create_table(
        "roles",
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.CheckConstraint("record_owner_organization_id = organization_id", name="ck_roles_owner"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_roles_organization",
        ),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_roles_owner",
        ),
        sa.PrimaryKeyConstraint("role_id"),
        sa.UniqueConstraint("role_id", "organization_id", name="uq_roles_id_organization"),
        sa.UniqueConstraint("organization_id", "name", name="uq_roles_organization_name"),
        schema=SCHEMA,
    )
    op.create_table(
        "role_permissions",
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("permission_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.CheckConstraint(
            "record_owner_organization_id = organization_id", name="ck_role_permissions_owner"
        ),
        sa.ForeignKeyConstraint(
            ["permission_id"],
            ["core_identity.permissions.permission_id"],
            name="fk_role_permissions_permission",
        ),
        sa.ForeignKeyConstraint(
            ["role_id", "organization_id"],
            ["core_identity.roles.role_id", "core_identity.roles.organization_id"],
            name="fk_role_permissions_role_organization",
        ),
        sa.UniqueConstraint("role_id", "permission_id", name="uq_role_permissions"),
        schema=SCHEMA,
    )
    op.create_table(
        "membership_role_assignments",
        sa.Column("assignment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("granted_by_actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.CheckConstraint(
            "record_owner_organization_id = organization_id", name="ck_assignments_owner"
        ),
        sa.CheckConstraint(
            "valid_until IS NULL OR valid_until > valid_from", name="ck_assignments_interval"
        ),
        sa.ForeignKeyConstraint(
            ["membership_id", "organization_id"],
            [
                "core_identity.memberships.membership_id",
                "core_identity.memberships.organization_id",
            ],
            name="fk_assignments_membership_organization",
        ),
        sa.ForeignKeyConstraint(
            ["role_id", "organization_id"],
            ["core_identity.roles.role_id", "core_identity.roles.organization_id"],
            name="fk_assignments_role_organization",
        ),
        sa.PrimaryKeyConstraint("assignment_id"),
        sa.UniqueConstraint(
            "assignment_id", "organization_id", name="uq_assignments_id_organization"
        ),
        schema=SCHEMA,
    )
    op.create_table(
        "membership_role_revocations",
        sa.Column("revocation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assignment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_by_actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.CheckConstraint(
            "record_owner_organization_id = organization_id", name="ck_revocations_owner"
        ),
        sa.ForeignKeyConstraint(
            ["assignment_id", "organization_id"],
            [
                "core_identity.membership_role_assignments.assignment_id",
                "core_identity.membership_role_assignments.organization_id",
            ],
            name="fk_revocations_assignment_organization",
        ),
        sa.PrimaryKeyConstraint("revocation_id"),
        sa.UniqueConstraint("assignment_id", name="uq_revocations_assignment"),
        schema=SCHEMA,
    )
    op.execute(
        sa.text(
            "COMMENT ON TABLE core_identity.permissions IS "
            "'titan.classification=REFERENCE_CATALOG;titan.module_owner=core_identity'"
        )
    )
    op.execute(sa.text("REVOKE ALL ON core_identity.permissions FROM PUBLIC"))
    for table in PROTECTED_TABLES:
        op.execute(
            sa.text(
                f"COMMENT ON TABLE {SCHEMA}.{table} IS "
                "'titan.classification=PROTECTED;titan.module_owner=core_identity'"
            )
        )
        _protect(table)


def downgrade() -> None:
    for table in reversed(PROTECTED_TABLES):
        op.execute(sa.text(f"DROP POLICY {table}_insert_by_owner ON {SCHEMA}.{table}"))
        op.execute(sa.text(f"DROP POLICY {table}_select_by_owner ON {SCHEMA}.{table}"))
        op.drop_table(table, schema=SCHEMA)
    op.drop_table("permissions", schema=SCHEMA)
    op.drop_constraint("uq_memberships_id_organization", "memberships", schema=SCHEMA)
