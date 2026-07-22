import os
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine

from packages.core_application import IdempotencyConflict, IdempotencyRequest, IdempotencyService
from packages.core_domain import CanonicalPayload, Organization
from packages.core_infrastructure.persistence import (
    IdempotencyRepository,
    OrganizationRepository,
    set_local_organization_context,
)
from packages.shared_kernel import TypedId, UniversalReference

DATABASE_URL = os.environ.get("TITAN_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="TITAN_DATABASE_URL não configurada para teste PostgreSQL.",
)


def test_retry_recovers_committed_result_and_divergent_intent_conflicts() -> None:
    assert DATABASE_URL is not None
    engine = create_engine(DATABASE_URL)
    organization = Organization.create()
    principal = UniversalReference(
        TypedId.new("actor"), organization.organization_id, contract_version=1
    )
    request = IdempotencyRequest(
        key="postgres-operation-1234",
        organization_id=organization.organization_id,
        principal_reference=principal,
        purpose="TESTE_DE_IDEMPOTENCIA",
        operation="test.execute",
        intent_digest=b"a" * 32,
        requested_at=datetime(2026, 7, 22, 11, 0, tzinfo=UTC),
    )
    calls = 0

    def effect() -> CanonicalPayload:
        nonlocal calls
        calls += 1
        return CanonicalPayload.from_mapping(
            schema="resultado_idempotente", version=1, value={"efeito": "unico"}
        )

    try:
        with engine.begin() as connection:
            set_local_organization_context(connection, organization.organization_id)
            OrganizationRepository(connection).add(organization)
            first = IdempotencyService(IdempotencyRepository(connection)).execute(request, effect)

        with engine.begin() as connection:
            set_local_organization_context(connection, organization.organization_id)
            second = IdempotencyService(IdempotencyRepository(connection)).execute(request, effect)

        assert calls == 1
        assert first.replayed is False
        assert second.replayed is True
        assert first.result_canonical_bytes == second.result_canonical_bytes

        divergent = IdempotencyRequest(
            key=request.key,
            organization_id=request.organization_id,
            principal_reference=request.principal_reference,
            purpose=request.purpose,
            operation=request.operation,
            intent_digest=b"b" * 32,
            requested_at=request.requested_at,
        )
        with engine.begin() as connection:
            set_local_organization_context(connection, organization.organization_id)
            with pytest.raises(IdempotencyConflict, match="INTENCAO_DIVERGENTE"):
                IdempotencyService(IdempotencyRepository(connection)).execute(divergent, effect)
    finally:
        engine.dispose()
