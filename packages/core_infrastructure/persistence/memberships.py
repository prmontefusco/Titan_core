"""Persistência PostgreSQL de Membership temporal."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Column,
    Connection,
    DateTime,
    ForeignKey,
    String,
    Table,
    insert,
    or_,
    select,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.engine import Row

from packages.core_domain import Membership, MembershipStatus
from packages.core_infrastructure.persistence.organizations import (
    CORE_IDENTITY_SCHEMA,
    organization_metadata,
)
from packages.shared_kernel import OrganizationId, TypedId

memberships_table = Table(
    "memberships",
    organization_metadata,
    Column("membership_id", UUID(as_uuid=True), primary_key=True),
    Column(
        "user_id",
        UUID(as_uuid=True),
        ForeignKey("core_identity.users.user_id", name="fk_memberships_user"),
        nullable=False,
    ),
    Column(
        "organization_id",
        UUID(as_uuid=True),
        ForeignKey(
            "core_identity.organizations.organization_id",
            name="fk_memberships_organization",
        ),
        nullable=False,
    ),
    Column(
        "record_owner_organization_id",
        UUID(as_uuid=True),
        ForeignKey(
            "core_identity.organizations.organization_id",
            name="fk_memberships_record_owner_organization",
        ),
        nullable=False,
    ),
    Column("valid_from", DateTime(timezone=True), nullable=False),
    Column("valid_until", DateTime(timezone=True), nullable=True),
    Column("status", String(20), nullable=False),
    Column("origin_reference_type", String(100), nullable=False),
    Column("origin_reference_id", UUID(as_uuid=True), nullable=False),
    Column("granted_by_actor_id", UUID(as_uuid=True), nullable=False),
    CheckConstraint(
        "record_owner_organization_id = organization_id",
        name="ck_memberships_owner_is_linked_organization",
    ),
    CheckConstraint(
        "valid_until IS NULL OR valid_until > valid_from",
        name="ck_memberships_valid_interval",
    ),
    CheckConstraint(
        "status IN ('ATIVA', 'SUSPENSA', 'ENCERRADA', 'SUBSTITUIDA')",
        name="ck_memberships_status",
    ),
    schema=CORE_IDENTITY_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=core_identity",
)


def _from_row(row: Row[Any]) -> Membership:
    return Membership(
        membership_id=TypedId(entity_type="membership", value=row.membership_id),
        user_id=TypedId(entity_type="user", value=row.user_id),
        organization_id=OrganizationId(row.organization_id),
        record_owner_organization_id=OrganizationId(row.record_owner_organization_id),
        valid_from=row.valid_from,
        valid_until=row.valid_until,
        status=MembershipStatus(row.status),
        origin_reference=TypedId(
            entity_type=row.origin_reference_type,
            value=row.origin_reference_id,
        ),
        granted_by_actor_id=TypedId(entity_type="actor", value=row.granted_by_actor_id),
    )


@dataclass(frozen=True, slots=True)
class MembershipRepository:
    """Consulta vínculos somente sob RLS da Organization atuante."""

    connection: Connection

    def __post_init__(self) -> None:
        if not isinstance(self.connection, Connection):
            raise TypeError("connection deve ser uma Connection SQLAlchemy.")
        if not self.connection.in_transaction():
            raise RuntimeError("MembershipRepository exige transação ativa.")

    def add(self, membership: Membership) -> None:
        if not isinstance(membership, Membership):
            raise TypeError("membership deve ser um Membership.")
        self.connection.execute(
            insert(memberships_table).values(
                membership_id=membership.membership_id.value,
                user_id=membership.user_id.value,
                organization_id=membership.organization_id.value,
                record_owner_organization_id=membership.record_owner_organization_id.value,
                valid_from=membership.valid_from,
                valid_until=membership.valid_until,
                status=membership.status.value,
                origin_reference_type=membership.origin_reference.entity_type,
                origin_reference_id=membership.origin_reference.value,
                granted_by_actor_id=membership.granted_by_actor_id.value,
            )
        )

    def get(self, membership_id: TypedId) -> Membership | None:
        if not isinstance(membership_id, TypedId):
            raise TypeError("membership_id deve ser um TypedId.")
        if membership_id.entity_type != "membership":
            raise ValueError("membership_id deve possuir tipo lógico 'membership'.")
        row = self.connection.execute(
            select(memberships_table).where(
                memberships_table.c.membership_id == membership_id.value
            )
        ).one_or_none()
        return None if row is None else _from_row(row)

    def list_valid_for_user(self, user_id: TypedId, instant: datetime) -> tuple[Membership, ...]:
        if not isinstance(user_id, TypedId):
            raise TypeError("user_id deve ser um TypedId.")
        if user_id.entity_type != "user":
            raise ValueError("user_id deve possuir tipo lógico 'user'.")
        if not isinstance(instant, datetime):
            raise TypeError("instant deve ser datetime.")
        offset = instant.utcoffset()
        if offset is None or offset.total_seconds() != 0:
            raise ValueError("instant deve possuir timezone UTC.")
        rows = self.connection.execute(
            select(memberships_table)
            .where(
                memberships_table.c.user_id == user_id.value,
                memberships_table.c.status == MembershipStatus.ATIVA.value,
                memberships_table.c.valid_from <= instant,
                or_(
                    memberships_table.c.valid_until.is_(None),
                    memberships_table.c.valid_until > instant,
                ),
            )
            .order_by(memberships_table.c.membership_id)
        ).all()
        return tuple(_from_row(row) for row in rows)
