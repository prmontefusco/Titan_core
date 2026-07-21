"""Persistência de Role, Permission e atribuições."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    Column,
    Connection,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    Table,
    UniqueConstraint,
    exists,
    insert,
    or_,
    select,
)
from sqlalchemy.dialects.postgresql import UUID

from packages.core_domain import (
    MembershipRoleAssignment,
    MembershipRoleRevocation,
    Permission,
    Role,
)
from packages.core_infrastructure.persistence.organizations import (
    CORE_IDENTITY_SCHEMA,
    organization_metadata,
)
from packages.shared_kernel import TypedId

permissions_table = Table(
    "permissions",
    organization_metadata,
    Column("permission_id", UUID(as_uuid=True), primary_key=True),
    Column(
        "record_owner_organization_id",
        UUID(as_uuid=True),
        ForeignKey("core_identity.organizations.organization_id", name="fk_permissions_owner"),
        nullable=False,
    ),
    Column("code", String(100), nullable=False, unique=True),
    schema=CORE_IDENTITY_SCHEMA,
    comment="titan.classification=REFERENCE_CATALOG;titan.module_owner=core_identity",
)

roles_table = Table(
    "roles",
    organization_metadata,
    Column("role_id", UUID(as_uuid=True), primary_key=True),
    Column("organization_id", UUID(as_uuid=True), nullable=False),
    Column("record_owner_organization_id", UUID(as_uuid=True), nullable=False),
    Column("name", String(100), nullable=False),
    ForeignKeyConstraint(
        ["organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_roles_organization",
    ),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_roles_owner",
    ),
    CheckConstraint("record_owner_organization_id = organization_id", name="ck_roles_owner"),
    UniqueConstraint("role_id", "organization_id", name="uq_roles_id_organization"),
    UniqueConstraint("organization_id", "name", name="uq_roles_organization_name"),
    schema=CORE_IDENTITY_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=core_identity",
)

role_permissions_table = Table(
    "role_permissions",
    organization_metadata,
    Column("role_id", UUID(as_uuid=True), nullable=False),
    Column(
        "permission_id",
        UUID(as_uuid=True),
        ForeignKey(
            "core_identity.permissions.permission_id", name="fk_role_permissions_permission"
        ),
        nullable=False,
    ),
    Column("organization_id", UUID(as_uuid=True), nullable=False),
    Column("record_owner_organization_id", UUID(as_uuid=True), nullable=False),
    ForeignKeyConstraint(
        ["role_id", "organization_id"],
        ["core_identity.roles.role_id", "core_identity.roles.organization_id"],
        name="fk_role_permissions_role_organization",
    ),
    CheckConstraint(
        "record_owner_organization_id = organization_id", name="ck_role_permissions_owner"
    ),
    UniqueConstraint("role_id", "permission_id", name="uq_role_permissions"),
    schema=CORE_IDENTITY_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=core_identity",
)

assignments_table = Table(
    "membership_role_assignments",
    organization_metadata,
    Column("assignment_id", UUID(as_uuid=True), primary_key=True),
    Column("membership_id", UUID(as_uuid=True), nullable=False),
    Column("role_id", UUID(as_uuid=True), nullable=False),
    Column("organization_id", UUID(as_uuid=True), nullable=False),
    Column("record_owner_organization_id", UUID(as_uuid=True), nullable=False),
    Column("valid_from", DateTime(timezone=True), nullable=False),
    Column("valid_until", DateTime(timezone=True), nullable=True),
    Column("granted_by_actor_id", UUID(as_uuid=True), nullable=False),
    ForeignKeyConstraint(
        ["membership_id", "organization_id"],
        ["core_identity.memberships.membership_id", "core_identity.memberships.organization_id"],
        name="fk_assignments_membership_organization",
    ),
    ForeignKeyConstraint(
        ["role_id", "organization_id"],
        ["core_identity.roles.role_id", "core_identity.roles.organization_id"],
        name="fk_assignments_role_organization",
    ),
    CheckConstraint("record_owner_organization_id = organization_id", name="ck_assignments_owner"),
    CheckConstraint(
        "valid_until IS NULL OR valid_until > valid_from", name="ck_assignments_interval"
    ),
    UniqueConstraint("assignment_id", "organization_id", name="uq_assignments_id_organization"),
    schema=CORE_IDENTITY_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=core_identity",
)

revocations_table = Table(
    "membership_role_revocations",
    organization_metadata,
    Column("revocation_id", UUID(as_uuid=True), primary_key=True),
    Column("assignment_id", UUID(as_uuid=True), nullable=False),
    Column("organization_id", UUID(as_uuid=True), nullable=False),
    Column("record_owner_organization_id", UUID(as_uuid=True), nullable=False),
    Column("revoked_at", DateTime(timezone=True), nullable=False),
    Column("revoked_by_actor_id", UUID(as_uuid=True), nullable=False),
    ForeignKeyConstraint(
        ["assignment_id", "organization_id"],
        [
            "core_identity.membership_role_assignments.assignment_id",
            "core_identity.membership_role_assignments.organization_id",
        ],
        name="fk_revocations_assignment_organization",
    ),
    CheckConstraint("record_owner_organization_id = organization_id", name="ck_revocations_owner"),
    UniqueConstraint("assignment_id", name="uq_revocations_assignment"),
    schema=CORE_IDENTITY_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=core_identity",
)


@dataclass(frozen=True, slots=True)
class AuthorizationRepository:
    connection: Connection

    def __post_init__(self) -> None:
        if not isinstance(self.connection, Connection) or not self.connection.in_transaction():
            raise RuntimeError("AuthorizationRepository exige Connection com transação ativa.")

    def add_permission(self, permission: Permission) -> None:
        self.connection.execute(
            insert(permissions_table).values(
                permission_id=permission.permission_id.value,
                record_owner_organization_id=permission.record_owner_organization_id.value,
                code=permission.code,
            )
        )

    def add_role(self, role: Role) -> None:
        self.connection.execute(
            insert(roles_table).values(
                role_id=role.role_id.value,
                organization_id=role.organization_id.value,
                record_owner_organization_id=role.record_owner_organization_id.value,
                name=role.name,
            )
        )
        for permission_id in role.permission_ids:
            self.connection.execute(
                insert(role_permissions_table).values(
                    role_id=role.role_id.value,
                    permission_id=permission_id.value,
                    organization_id=role.organization_id.value,
                    record_owner_organization_id=role.record_owner_organization_id.value,
                )
            )

    def assign_role(self, assignment: MembershipRoleAssignment) -> None:
        self.connection.execute(
            insert(assignments_table).values(
                assignment_id=assignment.assignment_id.value,
                membership_id=assignment.membership_id.value,
                role_id=assignment.role_id.value,
                organization_id=assignment.organization_id.value,
                record_owner_organization_id=assignment.record_owner_organization_id.value,
                valid_from=assignment.valid_from,
                valid_until=assignment.valid_until,
                granted_by_actor_id=assignment.granted_by_actor_id.value,
            )
        )

    def revoke_role(self, revocation: MembershipRoleRevocation) -> None:
        self.connection.execute(
            insert(revocations_table).values(
                revocation_id=revocation.revocation_id.value,
                assignment_id=revocation.assignment_id.value,
                organization_id=revocation.organization_id.value,
                record_owner_organization_id=revocation.record_owner_organization_id.value,
                revoked_at=revocation.revoked_at,
                revoked_by_actor_id=revocation.revoked_by_actor_id.value,
            )
        )

    def effective_permission_codes(
        self,
        membership_id: TypedId,
        instant: datetime,
    ) -> frozenset[str]:
        revoked = exists(
            select(revocations_table.c.revocation_id).where(
                revocations_table.c.assignment_id == assignments_table.c.assignment_id,
                revocations_table.c.revoked_at <= instant,
            )
        )
        rows = self.connection.execute(
            select(permissions_table.c.code)
            .select_from(
                assignments_table.join(roles_table)
                .join(role_permissions_table)
                .join(permissions_table)
            )
            .where(
                assignments_table.c.membership_id == membership_id.value,
                assignments_table.c.valid_from <= instant,
                or_(
                    assignments_table.c.valid_until.is_(None),
                    assignments_table.c.valid_until > instant,
                ),
                ~revoked,
            )
        ).scalars()
        return frozenset(rows)

    def effective_role_ids(self, membership_id: TypedId, instant: datetime) -> tuple[TypedId, ...]:
        revoked = exists(
            select(revocations_table.c.revocation_id).where(
                revocations_table.c.assignment_id == assignments_table.c.assignment_id,
                revocations_table.c.revoked_at <= instant,
            )
        )
        rows = self.connection.execute(
            select(assignments_table.c.role_id)
            .where(
                assignments_table.c.membership_id == membership_id.value,
                assignments_table.c.valid_from <= instant,
                or_(
                    assignments_table.c.valid_until.is_(None),
                    assignments_table.c.valid_until > instant,
                ),
                ~revoked,
            )
            .order_by(assignments_table.c.role_id)
        ).scalars()
        return tuple(TypedId(entity_type="role", value=value) for value in rows)
