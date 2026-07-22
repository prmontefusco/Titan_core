"""Idempotência autoritativa para uma intenção semanticamente delimitada."""

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from packages.core_domain import CanonicalPayload
from packages.shared_kernel import OrganizationId, UniversalReference
from packages.shared_kernel.temporal import require_utc

_KEY_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{8,200}$")
_CODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{1,99}$")
_OPERATION_PATTERN = re.compile(r"^[a-z][a-z0-9_.]{1,99}$")


class IdempotencyConflict(RuntimeError):
    """A mesma chave foi reutilizada para intenção semanticamente diferente."""


class IdempotencyResultUnknown(RuntimeError):
    """Existe operação adquirida sem resultado recuperável concluído."""


@dataclass(frozen=True, slots=True)
class IdempotencyRequest:
    key: str
    organization_id: OrganizationId
    principal_reference: UniversalReference
    purpose: str
    operation: str
    intent_digest: bytes
    requested_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.key, str) or not _KEY_PATTERN.fullmatch(self.key):
            raise ValueError("IdempotencyKey possui formato inválido.")
        if not isinstance(self.organization_id, OrganizationId):
            raise TypeError("organization_id deve ser OrganizationId.")
        if not isinstance(self.principal_reference, UniversalReference):
            raise TypeError("principal_reference deve ser UniversalReference.")
        if self.principal_reference.organization_id != self.organization_id:
            raise ValueError("O principal deve pertencer ao contexto da Organization.")
        if not isinstance(self.purpose, str) or not _CODE_PATTERN.fullmatch(self.purpose):
            raise ValueError("purpose deve possuir código canônico.")
        if not isinstance(self.operation, str) or not _OPERATION_PATTERN.fullmatch(self.operation):
            raise ValueError("operation deve possuir nome canônico.")
        if not isinstance(self.intent_digest, bytes) or len(self.intent_digest) != 32:
            raise ValueError("intent_digest deve possuir 32 bytes.")
        require_utc(self.requested_at, field_name="requested_at")


@dataclass(frozen=True, slots=True)
class StoredIdempotencyResult:
    intent_digest: bytes
    result_schema: str | None
    result_version: int | None
    result_canonical_bytes: bytes | None

    @property
    def completed(self) -> bool:
        return self.result_canonical_bytes is not None


@dataclass(frozen=True, slots=True)
class IdempotencyExecution:
    result_schema: str
    result_version: int
    result_canonical_bytes: bytes
    replayed: bool


class IdempotencyStore(Protocol):
    def acquire(self, request: IdempotencyRequest) -> StoredIdempotencyResult | None: ...

    def complete(self, request: IdempotencyRequest, result: CanonicalPayload) -> None: ...


@dataclass(frozen=True, slots=True)
class IdempotencyService:
    store: IdempotencyStore

    def execute(
        self,
        request: IdempotencyRequest,
        handler: Callable[[], CanonicalPayload],
    ) -> IdempotencyExecution:
        stored = self.store.acquire(request)
        if stored is not None:
            if stored.intent_digest != request.intent_digest:
                raise IdempotencyConflict("IDEMPOTENCY_KEY_COM_INTENCAO_DIVERGENTE")
            if (
                not stored.completed
                or stored.result_schema is None
                or stored.result_version is None
                or stored.result_canonical_bytes is None
            ):
                raise IdempotencyResultUnknown("RESULTADO_IDEMPOTENTE_DESCONHECIDO")
            return IdempotencyExecution(
                stored.result_schema,
                stored.result_version,
                stored.result_canonical_bytes,
                True,
            )

        result = handler()
        if not isinstance(result, CanonicalPayload):
            raise TypeError("O handler idempotente deve retornar CanonicalPayload.")
        self.store.complete(request, result)
        return IdempotencyExecution(
            result.schema,
            result.version,
            result.canonical_bytes,
            False,
        )
