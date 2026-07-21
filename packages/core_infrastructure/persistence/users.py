"""Persistência PostgreSQL do User global owned pela Organization operadora."""

from dataclasses import dataclass

from sqlalchemy import Column, Connection, ForeignKey, Table, insert, select
from sqlalchemy.dialects.postgresql import UUID

from packages.core_domain import User
from packages.core_infrastructure.persistence.organizations import (
    CORE_IDENTITY_SCHEMA,
    organization_metadata,
)
from packages.shared_kernel import OrganizationId, TypedId

users_table = Table(
    "users",
    organization_metadata,
    Column("user_id", UUID(as_uuid=True), primary_key=True),
    Column(
        "record_owner_organization_id",
        UUID(as_uuid=True),
        ForeignKey(
            "core_identity.organizations.organization_id",
            name="fk_users_record_owner_organization",
        ),
        nullable=False,
    ),
    schema=CORE_IDENTITY_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=core_identity",
)


@dataclass(frozen=True, slots=True)
class UserRepository:
    """Acesso a User dentro do contexto da Organization operadora."""

    connection: Connection

    def __post_init__(self) -> None:
        if not isinstance(self.connection, Connection):
            raise TypeError("connection deve ser uma Connection SQLAlchemy.")
        if not self.connection.in_transaction():
            raise RuntimeError("UserRepository exige transação ativa.")

    def add(self, user: User) -> None:
        if not isinstance(user, User):
            raise TypeError("user deve ser um User.")
        self.connection.execute(
            insert(users_table).values(
                user_id=user.user_id.value,
                record_owner_organization_id=user.record_owner_organization_id.value,
            )
        )

    def get(self, user_id: TypedId) -> User | None:
        if not isinstance(user_id, TypedId):
            raise TypeError("user_id deve ser um TypedId.")
        if user_id.entity_type != "user":
            raise ValueError("user_id deve possuir tipo lógico 'user'.")
        row = self.connection.execute(
            select(
                users_table.c.user_id,
                users_table.c.record_owner_organization_id,
            ).where(users_table.c.user_id == user_id.value)
        ).one_or_none()
        if row is None:
            return None
        return User(
            user_id=TypedId(entity_type="user", value=row.user_id),
            record_owner_organization_id=OrganizationId(row.record_owner_organization_id),
        )
