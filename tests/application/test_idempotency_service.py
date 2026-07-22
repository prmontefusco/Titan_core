from dataclasses import dataclass, field
from datetime import UTC, datetime

import pytest

from packages.core_application import (
    IdempotencyConflict,
    IdempotencyRequest,
    IdempotencyResultUnknown,
    IdempotencyService,
)
from packages.core_application.idempotency import StoredIdempotencyResult
from packages.core_domain import CanonicalPayload
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference


def _request(*, digest: bytes = b"a" * 32) -> IdempotencyRequest:
    organization_id = OrganizationId.new()
    return IdempotencyRequest(
        key="operacao-12345678",
        organization_id=organization_id,
        principal_reference=UniversalReference(
            TypedId.new("actor"), organization_id, contract_version=1
        ),
        purpose="CORRECAO_DE_REGISTRO",
        operation="correction.create",
        intent_digest=digest,
        requested_at=datetime(2026, 7, 22, 10, 0, tzinfo=UTC),
    )


@dataclass
class InMemoryIdempotencyStore:
    records: dict[tuple[str, str, str], StoredIdempotencyResult] = field(default_factory=dict)

    def acquire(self, request: IdempotencyRequest) -> StoredIdempotencyResult | None:
        scope = (request.key, request.purpose, request.operation)
        existing = self.records.get(scope)
        if existing is None:
            self.records[scope] = StoredIdempotencyResult(request.intent_digest, None, None, None)
        return existing

    def complete(self, request: IdempotencyRequest, result: CanonicalPayload) -> None:
        self.records[(request.key, request.purpose, request.operation)] = StoredIdempotencyResult(
            request.intent_digest,
            result.schema,
            result.version,
            result.canonical_bytes,
        )


def test_equivalent_retry_recovers_result_without_repeating_effect() -> None:
    store = InMemoryIdempotencyStore()
    service = IdempotencyService(store)
    request = _request()
    calls = 0

    def effect() -> CanonicalPayload:
        nonlocal calls
        calls += 1
        return CanonicalPayload.from_mapping(
            schema="resultado_operacao", version=1, value={"status": "concluida"}
        )

    first = service.execute(request, effect)
    second = service.execute(request, effect)

    assert calls == 1
    assert first.replayed is False
    assert second.replayed is True
    assert second.result_canonical_bytes == first.result_canonical_bytes


def test_same_key_with_different_intent_is_conflict() -> None:
    store = InMemoryIdempotencyStore()
    service = IdempotencyService(store)
    original = _request()
    service.execute(
        original,
        lambda: CanonicalPayload.from_mapping(schema="resultado", version=1, value={"ok": True}),
    )

    divergent = IdempotencyRequest(
        key=original.key,
        organization_id=original.organization_id,
        principal_reference=original.principal_reference,
        purpose=original.purpose,
        operation=original.operation,
        intent_digest=b"b" * 32,
        requested_at=original.requested_at,
    )
    with pytest.raises(IdempotencyConflict, match="INTENCAO_DIVERGENTE"):
        service.execute(
            divergent,
            lambda: CanonicalPayload.from_mapping(schema="resultado", version=1, value={}),
        )


def test_acquired_operation_without_result_is_not_reexecuted() -> None:
    store = InMemoryIdempotencyStore()
    request = _request()
    store.acquire(request)

    with pytest.raises(IdempotencyResultUnknown, match="RESULTADO_IDEMPOTENTE_DESCONHECIDO"):
        IdempotencyService(store).execute(
            request,
            lambda: CanonicalPayload.from_mapping(schema="resultado", version=1, value={}),
        )
