"""Contrato da Inbox, consumidor de mensagens e maquina de estados (ADR-0038)."""

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from packages.core_application.outbox import MessageKind
from packages.core_domain import CanonicalPayload
from packages.shared_kernel import OrganizationId, RecordTimestamps, TypedId, UniversalReference
from packages.shared_kernel.serialization import CanonicalSerializer, CanonicalValue

_TYPE_PATTERN = re.compile(r"^[a-z][a-z0-9_.]{1,99}$")


class TransientConsumptionError(Exception):
    """Falha de infraestrutura ou concorrência que justifica rollback e retry."""


class PermanentConsumptionError(Exception):
    """Falha irrecuperável que exige quarentena sem retry automático."""


class InboxStatus(StrEnum):
    EM_PROCESSAMENTO = "EM_PROCESSAMENTO"
    AGUARDANDO_RETRY = "AGUARDANDO_RETRY"
    CONCLUIDA = "CONCLUIDA"
    EM_QUARENTENA = "EM_QUARENTENA"
    RECONCILIACAO_PENDENTE = "RECONCILIACAO_PENDENTE"


class ProcessingOutcome(StrEnum):
    SUCCESS = "SUCCESS"
    BUSINESS_REJECTION = "BUSINESS_REJECTION"
    NO_OP = "NO_OP"
    AUTHORIZATION_REJECTED = "AUTHORIZATION_REJECTED"


class DeliveryHandlingOutcome(StrEnum):
    PROCESSED = "PROCESSED"
    DUPLICATE_RECOVERED = "DUPLICATE_RECOVERED"
    RETRY_SCHEDULED = "RETRY_SCHEDULED"
    CONFLICT_DETECTED = "CONFLICT_DETECTED"
    QUARANTINED = "QUARANTINED"


class AuthorizationEvaluationMode(StrEnum):
    AT_ACCEPTANCE = "AT_ACCEPTANCE"
    AT_EXECUTION = "AT_EXECUTION"
    AT_ACCEPTANCE_AND_EXECUTION = "AT_ACCEPTANCE_AND_EXECUTION"
    SERVICE_AUTHORITY_ONLY = "SERVICE_AUTHORITY_ONLY"


@dataclass(frozen=True, slots=True)
class AuthorizationReference:
    decision_reference: str
    policy_version: int
    accepted_at: datetime
    accepting_service_identity: str
    context_digest: bytes

    def __post_init__(self) -> None:
        if not self.decision_reference:
            raise ValueError("decision_reference nao pode ser vazia.")
        if isinstance(self.policy_version, bool) or self.policy_version < 1:
            raise ValueError("policy_version deve ser positivo.")
        if not self.accepting_service_identity:
            raise ValueError("accepting_service_identity nao pode ser vazia.")
        if not self.context_digest:
            raise ValueError("context_digest nao pode ser vazio.")


@dataclass(frozen=True, slots=True)
class IncomingMessageEnvelope:
    message_id: TypedId
    organization_id: OrganizationId
    kind: MessageKind
    contract_type: str
    contract_version: int
    semantic_operation_id: TypedId
    actor_reference: UniversalReference
    producer_reference: UniversalReference
    timestamps: RecordTimestamps
    correlation_id: TypedId
    causation_id: TypedId
    auth_evaluation_mode: AuthorizationEvaluationMode
    purpose: str
    auth_reference: AuthorizationReference | None
    payload: CanonicalPayload
    classification: str

    def __post_init__(self) -> None:
        if self.message_id.entity_type not in {"outbox_message", "incoming_message"}:
            raise ValueError("message_id tipo invalido.")
        if not isinstance(self.kind, MessageKind):
            raise TypeError("kind deve ser MessageKind.")
        if not _TYPE_PATTERN.fullmatch(self.contract_type):
            raise ValueError("contract_type invalido.")
        if isinstance(self.contract_version, bool) or self.contract_version < 1:
            raise ValueError("contract_version invalido.")
        if self.semantic_operation_id.entity_type != "operation":
            raise ValueError("semantic_operation_id tipo invalido.")
        if self.correlation_id.entity_type != "correlation":
            raise ValueError("correlation_id tipo invalido.")
        if self.causation_id.entity_type not in {"domain_event", "command", "job"}:
            raise ValueError("causation_id tipo invalido.")
        if self.actor_reference.organization_id != self.organization_id:
            raise ValueError("Actor deve pertencer a Organization da mensagem.")
        if not isinstance(self.auth_evaluation_mode, AuthorizationEvaluationMode):
            raise TypeError("auth_evaluation_mode invalido.")
        if not self.purpose:
            raise ValueError("purpose nao pode ser vazio.")
        if (
            self.auth_evaluation_mode is AuthorizationEvaluationMode.AT_ACCEPTANCE
            and self.auth_reference is None
        ):
            raise ValueError("Mensagens AT_ACCEPTANCE exigem auth_reference verificavel.")
        if not isinstance(self.payload, CanonicalPayload):
            raise TypeError("payload deve ser CanonicalPayload.")

    def compute_semantic_digest(self) -> bytes:
        canonical_object: dict[str, CanonicalValue] = {
            "canonical_profile": "titan-json-v1",
            "message_id": str(self.message_id.value),
            "message_type": self.contract_type,
            "schema_version": self.contract_version,
            "semantic_operation_id": str(self.semantic_operation_id.value),
            "producer_identity": str(self.producer_reference.target_id.value),
            "record_owner_organization_id": str(self.organization_id.value),
            "authorization_evaluation_mode": self.auth_evaluation_mode.value,
            "purpose": self.purpose,
            "authorization_decision_reference": self.auth_reference.decision_reference
            if self.auth_reference
            else None,
            "payload_canonical_bytes": self.payload.canonical_bytes.hex(),
        }
        bytes_to_hash = CanonicalSerializer().serialize(canonical_object)
        return hashlib.sha256(bytes_to_hash).digest()


@dataclass(frozen=True, slots=True)
class ConsumerReceipt:
    message_id: TypedId
    organization_id: OrganizationId
    handling_outcome: DeliveryHandlingOutcome
    processing_outcome: ProcessingOutcome | None = None
    effect_reference: str | None = None
    decision_reference: str | None = None
    completed_at: datetime | None = None
    reason: str | None = None


class MessageHandler(Protocol):
    def handle(
        self, envelope: IncomingMessageEnvelope
    ) -> tuple[ProcessingOutcome, str | None, str | None]: ...


class MessageConsumerPort(Protocol):
    def process_message(
        self, envelope: IncomingMessageEnvelope, handler: MessageHandler
    ) -> ConsumerReceipt: ...

    def record_untrusted_quarantine(
        self,
        envelope_bytes: bytes,
        alleged_producer: str | None,
        alleged_org: str | None,
        reason_code: str,
    ) -> ConsumerReceipt: ...


@dataclass(frozen=True, slots=True)
class QuarantinedMessageRecord:
    quarantine_id: TypedId
    message_id: TypedId | None
    organization_id: OrganizationId | None
    alleged_producer: str | None
    reason_code: str
    quarantined_at: datetime


@dataclass(frozen=True, slots=True)
class ReplayRequest:
    quarantine_id: TypedId
    operator_actor_reference: UniversalReference
    reason: str
    override_tenant_id: OrganizationId | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.operator_actor_reference, UniversalReference):
            raise TypeError("operator_actor_reference deve ser UniversalReference.")
        if not self.reason or not self.reason.strip():
            raise ValueError("Justificativa e obrigatoria para operacao de replay.")


@dataclass(frozen=True, slots=True)
class ReplayResult:
    quarantine_id: TypedId
    status: str
    processed_at: datetime
    reason: str | None = None


class InboxQuarantineRepositoryPort(Protocol):
    def list_quarantined(
        self, *, limit: int = 50, offset: int = 0
    ) -> list[QuarantinedMessageRecord]: ...

    def replay_message(self, request: ReplayRequest) -> ReplayResult: ...


@dataclass(frozen=True, slots=True)
class InboxQuarantineService:
    repository: InboxQuarantineRepositoryPort

    def list_quarantined(
        self, *, limit: int = 50, offset: int = 0
    ) -> list[QuarantinedMessageRecord]:
        return self.repository.list_quarantined(limit=limit, offset=offset)

    def replay(self, request: ReplayRequest) -> ReplayResult:
        if not request.reason or not request.reason.strip():
            raise ValueError("Justificativa e obrigatoria para operacao de replay.")
        return self.repository.replay_message(request)
