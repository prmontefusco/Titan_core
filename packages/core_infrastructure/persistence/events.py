"""Event store PostgreSQL append-only do Titan Core."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Column,
    Connection,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Table,
    UniqueConstraint,
    func,
    insert,
    select,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.engine import Row

from packages.core_domain import DomainEvent
from packages.core_infrastructure.persistence.organizations import organization_metadata
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference

CORE_AUDIT_SCHEMA = "core_audit"

domain_events_table = Table(
    "domain_events",
    organization_metadata,
    Column("event_id", UUID(as_uuid=True), primary_key=True),
    Column(
        "record_owner_organization_id",
        UUID(as_uuid=True),
        ForeignKey(
            "core_identity.organizations.organization_id",
            name="fk_domain_events_owner",
        ),
        nullable=False,
    ),
    Column("aggregate_type", String(100), nullable=False),
    Column("aggregate_id", UUID(as_uuid=True), nullable=False),
    Column("aggregate_contract_version", Integer, nullable=False),
    Column("aggregate_version", Integer, nullable=False),
    Column("event_type", String(100), nullable=False),
    Column("event_version", Integer, nullable=False),
    Column("occurred_at", DateTime(timezone=True), nullable=False),
    Column("recorded_at", DateTime(timezone=True), nullable=False),
    Column("actor_type", String(100), nullable=False),
    Column("actor_id", UUID(as_uuid=True), nullable=False),
    Column("actor_organization_id", UUID(as_uuid=True), nullable=True),
    Column("actor_contract_version", Integer, nullable=False),
    Column("source_type", String(100), nullable=False),
    Column("source_id", UUID(as_uuid=True), nullable=False),
    Column("source_organization_id", UUID(as_uuid=True), nullable=True),
    Column("source_contract_version", Integer, nullable=False),
    Column("correlation_id", UUID(as_uuid=True), nullable=False),
    Column("causation_id", UUID(as_uuid=True), nullable=True),
    Column("payload_schema", String(100), nullable=False),
    Column("payload_version", Integer, nullable=False),
    Column("payload_canonical_bytes", LargeBinary, nullable=False),
    CheckConstraint("aggregate_contract_version > 0", name="ck_events_aggregate_contract"),
    CheckConstraint("aggregate_version > 0", name="ck_events_aggregate_version"),
    CheckConstraint("event_version > 0", name="ck_events_event_version"),
    CheckConstraint("actor_contract_version > 0", name="ck_events_actor_contract"),
    CheckConstraint("source_contract_version > 0", name="ck_events_source_contract"),
    CheckConstraint("payload_version > 0", name="ck_events_payload_version"),
    UniqueConstraint(
        "record_owner_organization_id",
        "aggregate_type",
        "aggregate_id",
        "aggregate_version",
        name="uq_domain_events_aggregate_version",
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=core_audit",
)


class EventAppendConflict(RuntimeError):
    """Indica versão inesperada sem revelar dados de outro contexto."""


@dataclass(frozen=True, slots=True)
class StoredDomainEvent:
    """Visão persistida mínima para consulta ordenada sem desserialização arbitrária."""

    event_id: TypedId
    organization_id: OrganizationId
    aggregate_reference: UniversalReference
    aggregate_version: int
    event_type: str
    event_version: int
    occurred_at: datetime
    recorded_at: datetime
    actor_reference: UniversalReference
    source_reference: UniversalReference
    correlation_id: TypedId
    causation_id: TypedId | None
    payload_schema: str
    payload_version: int
    payload_canonical_bytes: bytes


@dataclass(frozen=True, slots=True)
class DomainEventRepository:
    connection: Connection

    def __post_init__(self) -> None:
        if not isinstance(self.connection, Connection) or not self.connection.in_transaction():
            raise RuntimeError("DomainEventRepository exige Connection com transação ativa.")

    def append(self, event: DomainEvent) -> None:
        if not isinstance(event, DomainEvent):
            raise TypeError("event deve ser um DomainEvent.")
        aggregate = event.aggregate_reference
        lock_key = (
            f"{event.organization_id}:{aggregate.target_id.entity_type}:{aggregate.target_id.value}"
        )
        self.connection.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:aggregate_key, 0))"),
            {"aggregate_key": lock_key},
        )
        current_version = self.connection.execute(
            select(func.max(domain_events_table.c.aggregate_version)).where(
                domain_events_table.c.record_owner_organization_id == event.organization_id.value,
                domain_events_table.c.aggregate_type == aggregate.target_id.entity_type,
                domain_events_table.c.aggregate_id == aggregate.target_id.value,
            )
        ).scalar_one()
        expected_version = 1 if current_version is None else current_version + 1
        if event.aggregate_version != expected_version:
            raise EventAppendConflict("VERSAO_DE_AGREGADO_CONFLITANTE")

        self.connection.execute(
            insert(domain_events_table).values(
                event_id=event.event_id.value,
                record_owner_organization_id=event.organization_id.value,
                aggregate_type=aggregate.target_id.entity_type,
                aggregate_id=aggregate.target_id.value,
                aggregate_contract_version=aggregate.contract_version,
                aggregate_version=event.aggregate_version,
                event_type=event.event_type,
                event_version=event.event_version,
                occurred_at=event.timestamps.occurred_at,
                recorded_at=event.timestamps.recorded_at,
                actor_type=event.actor_reference.target_id.entity_type,
                actor_id=event.actor_reference.target_id.value,
                actor_organization_id=_organization_value(event.actor_reference),
                actor_contract_version=event.actor_reference.contract_version,
                source_type=event.source_reference.target_id.entity_type,
                source_id=event.source_reference.target_id.value,
                source_organization_id=_organization_value(event.source_reference),
                source_contract_version=event.source_reference.contract_version,
                correlation_id=event.correlation_id.value,
                causation_id=None if event.causation_id is None else event.causation_id.value,
                payload_schema=event.payload.schema,
                payload_version=event.payload.version,
                payload_canonical_bytes=event.payload.canonical_bytes,
            )
        )

    def list_for_aggregate(
        self, aggregate_reference: UniversalReference
    ) -> tuple[StoredDomainEvent, ...]:
        if not isinstance(aggregate_reference, UniversalReference):
            raise TypeError("aggregate_reference deve ser UniversalReference.")
        if aggregate_reference.organization_id is None:
            raise ValueError("O agregado persistido deve possuir Organization.")
        rows = self.connection.execute(
            select(domain_events_table)
            .where(
                domain_events_table.c.record_owner_organization_id
                == aggregate_reference.organization_id.value,
                domain_events_table.c.aggregate_type == aggregate_reference.target_id.entity_type,
                domain_events_table.c.aggregate_id == aggregate_reference.target_id.value,
            )
            .order_by(domain_events_table.c.aggregate_version)
        ).all()
        return tuple(_from_row(row) for row in rows)

    def list_versions(self, aggregate_reference: UniversalReference) -> tuple[int, ...]:
        return tuple(
            event.aggregate_version for event in self.list_for_aggregate(aggregate_reference)
        )


def _organization_value(reference: UniversalReference) -> Any:
    return None if reference.organization_id is None else reference.organization_id.value


def _reference(
    *, entity_type: str, identifier: Any, organization_id: Any, contract_version: int
) -> UniversalReference:
    return UniversalReference(
        target_id=TypedId(entity_type=entity_type, value=identifier),
        organization_id=(None if organization_id is None else OrganizationId(organization_id)),
        contract_version=contract_version,
    )


def _from_row(row: Row[Any]) -> StoredDomainEvent:
    organization_id = OrganizationId(row.record_owner_organization_id)
    return StoredDomainEvent(
        event_id=TypedId(entity_type="domain_event", value=row.event_id),
        organization_id=organization_id,
        aggregate_reference=_reference(
            entity_type=row.aggregate_type,
            identifier=row.aggregate_id,
            organization_id=organization_id.value,
            contract_version=row.aggregate_contract_version,
        ),
        aggregate_version=row.aggregate_version,
        event_type=row.event_type,
        event_version=row.event_version,
        occurred_at=row.occurred_at,
        recorded_at=row.recorded_at,
        actor_reference=_reference(
            entity_type=row.actor_type,
            identifier=row.actor_id,
            organization_id=row.actor_organization_id,
            contract_version=row.actor_contract_version,
        ),
        source_reference=_reference(
            entity_type=row.source_type,
            identifier=row.source_id,
            organization_id=row.source_organization_id,
            contract_version=row.source_contract_version,
        ),
        correlation_id=TypedId(entity_type="correlation", value=row.correlation_id),
        causation_id=(
            None
            if row.causation_id is None
            else TypedId(entity_type="domain_event", value=row.causation_id)
        ),
        payload_schema=row.payload_schema,
        payload_version=row.payload_version,
        payload_canonical_bytes=bytes(row.payload_canonical_bytes),
    )
