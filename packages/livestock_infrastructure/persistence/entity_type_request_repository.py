"""Persistencia do pedido de tipo de entidade (EntityTypeRequest)."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    Column,
    Connection,
    DateTime,
    ForeignKeyConstraint,
    Index,
    String,
    Table,
    Text,
    insert,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.engine import Row

from packages.core_infrastructure.persistence.events import CORE_AUDIT_SCHEMA
from packages.livestock_application.entity_type_request_service import (
    EntityTypeRequestRepositoryPort,
)
from packages.livestock_domain.entity_type_request import (
    EntityKind,
    EntityTypeRequest,
    EntityTypeRequestStatus,
)
from packages.livestock_infrastructure.persistence.metadata import livestock_metadata
from packages.shared_kernel import OrganizationId, TypedId

entity_type_requests_table = Table(
    "entity_type_requests",
    livestock_metadata,
    Column("request_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("requested_kind", String(40), nullable=False),
    Column("requested_by_user_id", PG_UUID(as_uuid=True), nullable=False),
    Column("status", String(20), nullable=False),
    Column("requested_at", DateTime(timezone=True), nullable=False),
    Column("decided_at", DateTime(timezone=True), nullable=True),
    Column("decided_by_actor_id", PG_UUID(as_uuid=True), nullable=True),
    Column("decision_reason", Text(), nullable=True),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_entity_type_requests_organization",
    ),
    ForeignKeyConstraint(
        ["requested_by_user_id"],
        ["core_identity.users.user_id"],
        name="fk_entity_type_requests_user",
    ),
    Index(
        "ix_entity_type_requests_lookup",
        "record_owner_organization_id",
        "requested_by_user_id",
        "status",
    ),
    comment="titan.classification=PROTECTED;titan.module_owner=livestock",
    schema=CORE_AUDIT_SCHEMA,
)
Index(
    "uq_entity_type_requests_pending_per_user",
    entity_type_requests_table.c.record_owner_organization_id,
    entity_type_requests_table.c.requested_by_user_id,
    unique=True,
    postgresql_where=entity_type_requests_table.c.status == "PENDENTE",
)


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def _map(row: Row[Any]) -> EntityTypeRequest:
    return EntityTypeRequest(
        request_id=TypedId(entity_type="entity_type_request", value=row.request_id),
        organization_id=OrganizationId(row.record_owner_organization_id),
        requested_kind=EntityKind(row.requested_kind),
        requested_by_user_id=TypedId(entity_type="user", value=row.requested_by_user_id),
        status=EntityTypeRequestStatus(row.status),
        requested_at=_aware(row.requested_at),
        decided_at=None if row.decided_at is None else _aware(row.decided_at),
        decided_by_actor_id=(
            None
            if row.decided_by_actor_id is None
            else TypedId(entity_type="actor", value=row.decided_by_actor_id)
        ),
        decision_reason=row.decision_reason,
    )


@dataclass(frozen=True, slots=True)
class TransactionalEntityTypeRequestRepository(EntityTypeRequestRepositoryPort):
    connection: Connection

    def add(self, request: EntityTypeRequest) -> None:
        self.connection.execute(
            insert(entity_type_requests_table).values(
                request_id=request.request_id.value,
                record_owner_organization_id=request.organization_id.value,
                requested_kind=request.requested_kind.value,
                requested_by_user_id=request.requested_by_user_id.value,
                status=request.status.value,
                requested_at=request.requested_at,
                decided_at=request.decided_at,
                decided_by_actor_id=(
                    None
                    if request.decided_by_actor_id is None
                    else request.decided_by_actor_id.value
                ),
                decision_reason=request.decision_reason,
            )
        )

    def get(self, request_id: TypedId) -> EntityTypeRequest | None:
        row = self.connection.execute(
            select(entity_type_requests_table).where(
                entity_type_requests_table.c.request_id == request_id.value
            )
        ).one_or_none()
        return None if row is None else _map(row)

    def get_pending_for_user(
        self, organization_id: OrganizationId, requested_by_user_id: TypedId
    ) -> EntityTypeRequest | None:
        row = self.connection.execute(
            select(entity_type_requests_table).where(
                entity_type_requests_table.c.record_owner_organization_id == organization_id.value,
                entity_type_requests_table.c.requested_by_user_id == requested_by_user_id.value,
                entity_type_requests_table.c.status == EntityTypeRequestStatus.PENDENTE.value,
            )
        ).one_or_none()
        return None if row is None else _map(row)

    def list_pending(self, organization_id: OrganizationId) -> tuple[EntityTypeRequest, ...]:
        rows = self.connection.execute(
            select(entity_type_requests_table)
            .where(
                entity_type_requests_table.c.record_owner_organization_id == organization_id.value,
                entity_type_requests_table.c.status == EntityTypeRequestStatus.PENDENTE.value,
            )
            .order_by(entity_type_requests_table.c.requested_at)
        ).all()
        return tuple(_map(row) for row in rows)

    def list_for_user(
        self, organization_id: OrganizationId, requested_by_user_id: TypedId
    ) -> tuple[EntityTypeRequest, ...]:
        rows = self.connection.execute(
            select(entity_type_requests_table)
            .where(
                entity_type_requests_table.c.record_owner_organization_id == organization_id.value,
                entity_type_requests_table.c.requested_by_user_id == requested_by_user_id.value,
            )
            .order_by(entity_type_requests_table.c.requested_at.desc())
        ).all()
        return tuple(_map(row) for row in rows)

    def record_decision(self, request: EntityTypeRequest) -> None:
        if request.decided_by_actor_id is None or request.decided_at is None:
            raise ValueError("record_decision exige um pedido ja decidido.")
        self.connection.execute(
            update(entity_type_requests_table)
            .where(entity_type_requests_table.c.request_id == request.request_id.value)
            .values(
                status=request.status.value,
                decided_at=request.decided_at,
                decided_by_actor_id=request.decided_by_actor_id.value,
                decision_reason=request.decision_reason,
            )
        )
