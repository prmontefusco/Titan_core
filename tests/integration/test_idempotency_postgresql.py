import os
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, select, update

from packages.core_application import IdempotencyConflict, IdempotencyRequest, IdempotencyService
from packages.core_domain import CanonicalPayload, Organization
from packages.core_infrastructure.persistence import (
    IdempotencyRepository,
    OrganizationRepository,
    set_local_organization_context,
)
from packages.core_infrastructure.persistence.idempotency import idempotency_records_table
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


def test_expired_completed_idempotency_records_are_cleaned_explicitly() -> None:
    assert DATABASE_URL is not None
    engine = create_engine(DATABASE_URL)
    organization = Organization.create()
    principal = UniversalReference(
        TypedId.new("actor"), organization.organization_id, contract_version=1
    )
    requested_at = datetime(2026, 9, 9, 10, 0, tzinfo=UTC)
    request = IdempotencyRequest(
        key="postgres-operation-expiration-1234",
        organization_id=organization.organization_id,
        principal_reference=principal,
        purpose="TESTE_DE_IDEMPOTENCIA",
        operation="test.expiration",
        intent_digest=b"c" * 32,
        requested_at=requested_at,
    )

    try:
        with engine.begin() as connection:
            set_local_organization_context(connection, organization.organization_id)
            OrganizationRepository(connection).add(organization)
            repository = IdempotencyRepository(connection, retention_days=2)
            IdempotencyService(repository).execute(
                request,
                lambda: CanonicalPayload.from_mapping(
                    schema="resultado_idempotente", version=1, value={"efeito": "unico"}
                ),
            )
            expires_at = connection.execute(
                select(idempotency_records_table.c.expires_at).where(
                    idempotency_records_table.c.record_owner_organization_id
                    == organization.organization_id.value,
                    idempotency_records_table.c.idempotency_key == request.key,
                )
            ).scalar_one()
            assert expires_at == requested_at + timedelta(days=2)

        with engine.begin() as connection:
            set_local_organization_context(connection, organization.organization_id)
            replay = IdempotencyService(IdempotencyRepository(connection)).execute(
                request,
                lambda: CanonicalPayload.from_mapping(
                    schema="resultado_idempotente", version=1, value={"efeito": "repetido"}
                ),
            )
            assert replay.replayed is True

        with engine.begin() as connection:
            set_local_organization_context(connection, organization.organization_id)
            deleted_before_expiration = IdempotencyRepository(connection).delete_expired_completed(
                organization_id=organization.organization_id,
                expired_before=requested_at + timedelta(days=1),
            )
            assert deleted_before_expiration == 0

        with engine.begin() as connection:
            set_local_organization_context(connection, organization.organization_id)
            deleted_after_expiration = IdempotencyRepository(connection).delete_expired_completed(
                organization_id=organization.organization_id,
                expired_before=requested_at + timedelta(days=3),
            )
            assert deleted_after_expiration == 1

        with engine.begin() as connection:
            set_local_organization_context(connection, organization.organization_id)
            calls = 0

            def effect() -> CanonicalPayload:
                nonlocal calls
                calls += 1
                return CanonicalPayload.from_mapping(
                    schema="resultado_idempotente", version=1, value={"efeito": "novo"}
                )

            IdempotencyService(IdempotencyRepository(connection)).execute(request, effect)
            assert calls == 1
    finally:
        engine.dispose()


def test_idempotency_completion_trigger_rejects_expiration_mutation() -> None:
    assert DATABASE_URL is not None
    engine = create_engine(DATABASE_URL)
    organization = Organization.create()
    principal = UniversalReference(
        TypedId.new("actor"), organization.organization_id, contract_version=1
    )
    request = IdempotencyRequest(
        key="postgres-operation-trigger-1234",
        organization_id=organization.organization_id,
        principal_reference=principal,
        purpose="TESTE_DE_IDEMPOTENCIA",
        operation="test.trigger",
        intent_digest=b"d" * 32,
        requested_at=datetime(2026, 9, 9, 11, 0, tzinfo=UTC),
    )

    try:
        with engine.begin() as connection:
            set_local_organization_context(connection, organization.organization_id)
            OrganizationRepository(connection).add(organization)
            IdempotencyRepository(connection).acquire(request)
            with pytest.raises(Exception, match="TRANSICAO_DE_IDEMPOTENCIA_INVALIDA"):
                connection.execute(
                    update(idempotency_records_table)
                    .where(idempotency_records_table.c.idempotency_key == request.key)
                    .values(
                        status="CONCLUIDA",
                        result_schema="resultado_idempotente",
                        result_version=1,
                        result_canonical_bytes=b"{}",
                        expires_at=request.requested_at + timedelta(days=60),
                    )
                )
    finally:
        engine.dispose()
