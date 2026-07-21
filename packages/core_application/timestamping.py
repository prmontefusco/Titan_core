"""Contratos substituíveis para prova temporal externa."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from packages.core_integrity import IntegrityCheckpoint
from packages.shared_kernel import TypedId
from packages.shared_kernel.temporal import require_utc


class TimestampAttemptStatus(StrEnum):
    PENDENTE = "PENDENTE"
    RESULTADO_DESCONHECIDO = "RESULTADO_DESCONHECIDO"
    TOKEN_RECEBIDO = "TOKEN_RECEBIDO"


class TimestampValidationStatus(StrEnum):
    VALIDO = "VALIDO"
    INVALIDO = "INVALIDO"
    INDETERMINADO = "INDETERMINADO"


class TimestampProviderUnavailable(RuntimeError):
    """Indisponibilidade confirmada antes de receber token."""


class TimestampProviderUnknownOutcome(RuntimeError):
    """A emissão pode ter ocorrido, mas o resultado não foi recebido."""


@dataclass(frozen=True, slots=True)
class TimestampRequest:
    attempt_id: TypedId
    checkpoint_id: TypedId
    message_imprint: bytes
    digest_algorithm: str
    policy: str
    nonce: bytes
    correlation_id: TypedId
    requested_at: datetime

    def __post_init__(self) -> None:
        _require_id(self.attempt_id, "timestamp_attempt")
        _require_id(self.checkpoint_id, "integrity_checkpoint")
        _require_id(self.correlation_id, "correlation")
        if not isinstance(self.message_imprint, bytes) or len(self.message_imprint) != 32:
            raise ValueError("message_imprint deve possuir 32 bytes.")
        if self.digest_algorithm != "SHA-256":
            raise ValueError("digest_algorithm não pertence ao perfil aprovado.")
        if not isinstance(self.policy, str) or not self.policy:
            raise ValueError("policy deve ser texto não vazio.")
        if not isinstance(self.nonce, bytes) or len(self.nonce) < 16:
            raise ValueError("nonce deve possuir ao menos 16 bytes.")
        require_utc(self.requested_at, field_name="requested_at")


@dataclass(frozen=True, slots=True)
class TimestampProviderResponse:
    provider_id: str
    raw_token: bytes
    received_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.provider_id, str) or not self.provider_id:
            raise ValueError("provider_id deve ser texto não vazio.")
        if not isinstance(self.raw_token, bytes) or not self.raw_token:
            raise ValueError("raw_token deve conter bytes.")
        require_utc(self.received_at, field_name="received_at")


@dataclass(frozen=True, slots=True)
class TimestampAttempt:
    request: TimestampRequest
    status: TimestampAttemptStatus
    provider_id: str
    raw_token: bytes | None
    received_at: datetime | None


@dataclass(frozen=True, slots=True)
class TimestampValidation:
    validation_id: TypedId
    attempt_id: TypedId
    status: TimestampValidationStatus
    reason_code: str
    validated_at: datetime
    proved_at: datetime | None
    token_digest: bytes


@dataclass(frozen=True, slots=True)
class TemporalAnchor:
    anchor_id: TypedId
    checkpoint_id: TypedId
    attempt_id: TypedId
    validation_id: TypedId
    message_imprint: bytes
    proved_at: datetime


class TimestampProvider(Protocol):
    @property
    def provider_id(self) -> str: ...

    def issue(self, request: TimestampRequest) -> TimestampProviderResponse: ...


class TimestampTokenValidator(Protocol):
    def validate(
        self,
        *,
        validation_id: TypedId,
        attempt: TimestampAttempt,
        validated_at: datetime,
    ) -> TimestampValidation: ...


class TimestampAuditWriter(Protocol):
    def add_attempt(self, attempt: TimestampAttempt) -> None: ...

    def add_validation(self, validation: TimestampValidation) -> None: ...

    def add_anchor(self, anchor: TemporalAnchor) -> None: ...


@dataclass(frozen=True, slots=True)
class TimestampService:
    writer: TimestampAuditWriter

    def request(
        self,
        *,
        checkpoint: IntegrityCheckpoint,
        attempt_id: TypedId,
        policy: str,
        nonce: bytes,
        correlation_id: TypedId,
        requested_at: datetime,
        provider: TimestampProvider,
    ) -> TimestampAttempt:
        request = TimestampRequest(
            attempt_id=attempt_id,
            checkpoint_id=checkpoint.checkpoint_id,
            message_imprint=checkpoint.checkpoint_digest,
            digest_algorithm=checkpoint.hash_algorithm,
            policy=policy,
            nonce=nonce,
            correlation_id=correlation_id,
            requested_at=requested_at,
        )
        try:
            response = provider.issue(request)
        except TimestampProviderUnavailable:
            attempt = TimestampAttempt(
                request, TimestampAttemptStatus.PENDENTE, provider.provider_id, None, None
            )
        except TimestampProviderUnknownOutcome:
            attempt = TimestampAttempt(
                request,
                TimestampAttemptStatus.RESULTADO_DESCONHECIDO,
                provider.provider_id,
                None,
                None,
            )
        else:
            attempt = TimestampAttempt(
                request,
                TimestampAttemptStatus.TOKEN_RECEBIDO,
                response.provider_id,
                response.raw_token,
                response.received_at,
            )
        self.writer.add_attempt(attempt)
        return attempt

    def validate_and_anchor(
        self,
        *,
        checkpoint: IntegrityCheckpoint,
        attempt: TimestampAttempt,
        validation_id: TypedId,
        anchor_id: TypedId,
        validated_at: datetime,
        validator: TimestampTokenValidator,
    ) -> tuple[TimestampValidation, TemporalAnchor | None]:
        if attempt.request.checkpoint_id != checkpoint.checkpoint_id:
            raise ValueError("CHECKPOINT_DIVERGENTE")
        if attempt.request.message_imprint != checkpoint.checkpoint_digest:
            raise ValueError("IMPRINT_DO_CHECKPOINT_DIVERGENTE")
        validation = validator.validate(
            validation_id=validation_id,
            attempt=attempt,
            validated_at=validated_at,
        )
        self.writer.add_validation(validation)
        if validation.status is not TimestampValidationStatus.VALIDO:
            return validation, None
        if validation.proved_at is None:
            raise ValueError("Validação válida exige proved_at.")
        anchor = TemporalAnchor(
            anchor_id=anchor_id,
            checkpoint_id=checkpoint.checkpoint_id,
            attempt_id=attempt.request.attempt_id,
            validation_id=validation.validation_id,
            message_imprint=checkpoint.checkpoint_digest,
            proved_at=validation.proved_at,
        )
        self.writer.add_anchor(anchor)
        return validation, anchor


def _require_id(identifier: TypedId, entity_type: str) -> None:
    if not isinstance(identifier, TypedId) or identifier.entity_type != entity_type:
        raise ValueError(f"O identificador deve possuir tipo lógico {entity_type!r}.")
