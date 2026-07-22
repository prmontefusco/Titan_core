"""Contrato técnico da Transactional Outbox, independente do broker."""

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from packages.core_domain import CanonicalPayload, DomainEvent
from packages.shared_kernel import OrganizationId, RecordTimestamps, TypedId, UniversalReference

_TYPE_PATTERN = re.compile(r"^[a-z][a-z0-9_.]{1,99}$")


class MessageKind(StrEnum):
    DOMAIN_EVENT = "DOMAIN_EVENT"
    INTEGRATION_EVENT = "INTEGRATION_EVENT"
    COMMAND = "COMMAND"
    JOB = "JOB"


@dataclass(frozen=True, slots=True)
class OutboxMessage:
    message_id: TypedId
    organization_id: OrganizationId
    kind: MessageKind
    contract_type: str
    contract_version: int
    actor_reference: UniversalReference
    producer_reference: UniversalReference
    timestamps: RecordTimestamps
    correlation_id: TypedId
    causation_id: TypedId
    idempotency_key: str | None
    payload: CanonicalPayload
    classification: str

    def __post_init__(self) -> None:
        if self.message_id.entity_type != "outbox_message":
            raise ValueError("message_id deve possuir tipo outbox_message.")
        if not isinstance(self.kind, MessageKind):
            raise TypeError("kind deve ser MessageKind.")
        if not _TYPE_PATTERN.fullmatch(self.contract_type):
            raise ValueError("contract_type deve possuir nome canônico.")
        if isinstance(self.contract_version, bool) or self.contract_version < 1:
            raise ValueError("contract_version deve ser positivo.")
        if self.correlation_id.entity_type != "correlation":
            raise ValueError("correlation_id deve possuir tipo correlation.")
        if self.causation_id.entity_type != "domain_event":
            raise ValueError("causation_id deve referenciar domain_event.")
        if self.actor_reference.organization_id != self.organization_id:
            raise ValueError("Actor deve pertencer à Organization da mensagem.")
        if not isinstance(self.payload, CanonicalPayload):
            raise TypeError("payload deve ser CanonicalPayload.")
        if self.classification not in {"PUBLIC", "INTERNAL", "PROTECTED", "RESTRICTED"}:
            raise ValueError("classification não pertence ao perfil aprovado.")


class EventAndOutboxWriter(Protocol):
    def append(self, event: DomainEvent, message: OutboxMessage) -> None: ...


@dataclass(frozen=True, slots=True)
class EventOutboxService:
    writer: EventAndOutboxWriter

    def append(self, event: DomainEvent, message: OutboxMessage) -> None:
        if message.organization_id != event.organization_id:
            raise ValueError("Event e OutboxMessage devem possuir a mesma Organization.")
        if message.causation_id != event.event_id:
            raise ValueError("OutboxMessage deve ser causada pelo Event da transação.")
        self.writer.append(event, message)
