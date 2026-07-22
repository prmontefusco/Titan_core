"""Persistência atômica de DomainEvent e OutboxMessage."""

from dataclasses import dataclass

from sqlalchemy import (
    CheckConstraint,
    Column,
    Connection,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    LargeBinary,
    String,
    Table,
    insert,
)
from sqlalchemy.dialects.postgresql import UUID

from packages.core_application import OutboxMessage
from packages.core_domain import DomainEvent
from packages.core_infrastructure.persistence.events import CORE_AUDIT_SCHEMA, DomainEventRepository
from packages.core_infrastructure.persistence.organizations import organization_metadata

outbox_messages_table = Table(
    "outbox_messages",
    organization_metadata,
    Column("message_id", UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", UUID(as_uuid=True), nullable=False),
    Column("kind", String(30), nullable=False),
    Column("contract_type", String(100), nullable=False),
    Column("contract_version", Integer, nullable=False),
    Column("actor_type", String(100), nullable=False),
    Column("actor_id", UUID(as_uuid=True), nullable=False),
    Column("producer_type", String(100), nullable=False),
    Column("producer_id", UUID(as_uuid=True), nullable=False),
    Column("occurred_at", DateTime(timezone=True), nullable=False),
    Column("recorded_at", DateTime(timezone=True), nullable=False),
    Column("correlation_id", UUID(as_uuid=True), nullable=False),
    Column("causation_id", UUID(as_uuid=True), nullable=False),
    Column("idempotency_key", String(200), nullable=True),
    Column("payload_schema", String(100), nullable=False),
    Column("payload_version", Integer, nullable=False),
    Column("payload_canonical_bytes", LargeBinary, nullable=False),
    Column("classification", String(20), nullable=False),
    Column("status", String(20), nullable=False),
    CheckConstraint("contract_version > 0", name="ck_outbox_contract_version"),
    CheckConstraint("payload_version > 0", name="ck_outbox_payload_version"),
    CheckConstraint("status = 'PENDENTE'", name="ck_outbox_initial_status"),
    ForeignKeyConstraint(
        ["causation_id", "record_owner_organization_id"],
        [
            "core_audit.domain_events.event_id",
            "core_audit.domain_events.record_owner_organization_id",
        ],
        name="fk_outbox_causation_event_owner",
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=core_audit",
)


@dataclass(frozen=True, slots=True)
class TransactionalEventOutboxRepository:
    connection: Connection

    def __post_init__(self) -> None:
        if not isinstance(self.connection, Connection) or not self.connection.in_transaction():
            raise RuntimeError("TransactionalEventOutboxRepository exige transação ativa.")

    def append(self, event: DomainEvent, message: OutboxMessage) -> None:
        if (
            event.organization_id != message.organization_id
            or event.event_id != message.causation_id
        ):
            raise ValueError("EVENT_OUTBOX_DIVERGENTE")
        DomainEventRepository(self.connection).append(event)
        self.connection.execute(
            insert(outbox_messages_table).values(
                message_id=message.message_id.value,
                record_owner_organization_id=message.organization_id.value,
                kind=message.kind.value,
                contract_type=message.contract_type,
                contract_version=message.contract_version,
                actor_type=message.actor_reference.target_id.entity_type,
                actor_id=message.actor_reference.target_id.value,
                producer_type=message.producer_reference.target_id.entity_type,
                producer_id=message.producer_reference.target_id.value,
                occurred_at=message.timestamps.occurred_at,
                recorded_at=message.timestamps.recorded_at,
                correlation_id=message.correlation_id.value,
                causation_id=message.causation_id.value,
                idempotency_key=message.idempotency_key,
                payload_schema=message.payload.schema,
                payload_version=message.payload.version,
                payload_canonical_bytes=message.payload.canonical_bytes,
                classification=message.classification,
                status="PENDENTE",
            )
        )
