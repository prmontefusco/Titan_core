"""Contrato técnico da Transactional Outbox, independente do broker."""

import re
from dataclasses import dataclass
from datetime import UTC, datetime
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


class BrokerPublicationStatus(StrEnum):
    ACEITA_PELO_BROKER = "ACEITA_PELO_BROKER"
    RESULTADO_DESCONHECIDO = "RESULTADO_DESCONHECIDO"
    REJEITADA_PELO_BROKER = "REJEITADA_PELO_BROKER"


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
class ClaimedOutboxMessage:
    message: OutboxMessage
    claim_token: TypedId

    def __post_init__(self) -> None:
        if self.claim_token.entity_type != "outbox_publication_claim":
            raise ValueError("claim_token deve possuir tipo outbox_publication_claim.")


@dataclass(frozen=True, slots=True)
class BrokerPublicationResult:
    status: BrokerPublicationStatus
    reason: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, BrokerPublicationStatus):
            raise TypeError("status deve ser BrokerPublicationStatus.")
        if self.status is BrokerPublicationStatus.ACEITA_PELO_BROKER and self.reason:
            raise ValueError("Aceitacao pelo broker nao registra motivo de falha.")


class OutboxPublicationRepository(Protocol):
    def claim_next(self, *, publisher_id: str) -> ClaimedOutboxMessage | None: ...

    def mark_broker_accepted(
        self, claimed_message: ClaimedOutboxMessage, result: BrokerPublicationResult
    ) -> None: ...

    def mark_unknown(
        self, claimed_message: ClaimedOutboxMessage, result: BrokerPublicationResult
    ) -> None: ...

    def mark_rejected(
        self, claimed_message: ClaimedOutboxMessage, result: BrokerPublicationResult
    ) -> None: ...


class MessageBrokerPublisher(Protocol):
    def publish(self, claimed_message: ClaimedOutboxMessage) -> BrokerPublicationResult: ...


@dataclass(frozen=True, slots=True)
class EventOutboxService:
    writer: EventAndOutboxWriter

    def append(self, event: DomainEvent, message: OutboxMessage) -> None:
        if message.organization_id != event.organization_id:
            raise ValueError("Event e OutboxMessage devem possuir a mesma Organization.")
        if message.causation_id != event.event_id:
            raise ValueError("OutboxMessage deve ser causada pelo Event da transação.")
        self.writer.append(event, message)


@dataclass(frozen=True, slots=True)
class OutboxPublisherService:
    repository: OutboxPublicationRepository
    publisher: MessageBrokerPublisher
    publisher_id: str

    def publish_once(self) -> BrokerPublicationResult | None:
        claimed_message = self.repository.claim_next(publisher_id=self.publisher_id)
        if claimed_message is None:
            return None

        result = self.publisher.publish(claimed_message)
        if result.status is BrokerPublicationStatus.ACEITA_PELO_BROKER:
            self.repository.mark_broker_accepted(claimed_message, result)
        elif result.status is BrokerPublicationStatus.RESULTADO_DESCONHECIDO:
            self.repository.mark_unknown(claimed_message, result)
        else:
            self.repository.mark_rejected(claimed_message, result)
        return result


@dataclass(frozen=True, slots=True)
class OutboxHealthSummary:
    total_pending: int
    active_claims: int
    expired_claims: int
    accepted_by_broker: int
    unknown_results: int
    rejected_by_broker: int
    oldest_pending_age_seconds: float | None
    oldest_expired_claim_age_seconds: float | None
    read_at: datetime


@dataclass(frozen=True, slots=True)
class OutboxReconciliationReport:
    summary_before: OutboxHealthSummary
    released_claims_count: int
    summary_after: OutboxHealthSummary
    reconciled_at: datetime


class OutboxReconciliationRepositoryPort(Protocol):
    def get_health_summary(self) -> OutboxHealthSummary: ...

    def release_expired_claims(self) -> int: ...


@dataclass(frozen=True, slots=True)
class OutboxReconciliationService:
    repository: OutboxReconciliationRepositoryPort

    def run(self) -> OutboxReconciliationReport:
        summary_before = self.repository.get_health_summary()
        released_count = self.repository.release_expired_claims()
        summary_after = self.repository.get_health_summary()
        return OutboxReconciliationReport(
            summary_before=summary_before,
            released_claims_count=released_count,
            summary_after=summary_after,
            reconciled_at=datetime.now(UTC),
        )
