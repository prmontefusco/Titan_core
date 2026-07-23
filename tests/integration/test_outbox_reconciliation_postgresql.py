"""Testes de integracao PostgreSQL real para reconciliacao da Outbox (Passo 4.9A)."""

import os
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import Connection, create_engine, text

from packages.core_application import (
    EventOutboxService,
    MessageKind,
    OutboxMessage,
    OutboxReconciliationService,
)
from packages.core_domain import CanonicalPayload, DomainEvent
from packages.core_infrastructure.persistence.outbox import (
    OutboxPublicationStateRepository,
    TransactionalEventOutboxRepository,
    TransactionalOutboxReconciliationRepository,
)
from packages.shared_kernel import OrganizationId, RecordTimestamps, TypedId, UniversalReference


@pytest.fixture
def db_connection() -> Iterator[Connection]:
    db_url = os.getenv(
        "TITAN_DATABASE_URL",
        "postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan",
    )
    engine = create_engine(db_url, pool_pre_ping=True)
    with engine.connect() as conn:
        with conn.begin():
            yield conn


def create_sample_event_and_message(
    org_id: OrganizationId,
) -> tuple[DomainEvent, OutboxMessage]:
    event_id = TypedId.new("domain_event")
    correlation_id = TypedId.new("correlation")

    actor_ref = UniversalReference(
        target_id=TypedId(entity_type="user", value=TypedId.new("user").value),
        organization_id=org_id,
        contract_version=1,
    )
    aggregate_ref = UniversalReference(
        target_id=TypedId(entity_type="test_aggregate", value=TypedId.new("test_aggregate").value),
        organization_id=org_id,
        contract_version=1,
    )
    producer_ref = UniversalReference(
        target_id=TypedId(entity_type="service", value=TypedId.new("service").value),
        organization_id=org_id,
        contract_version=1,
    )
    timestamps = RecordTimestamps(
        occurred_at=datetime.now(UTC),
        recorded_at=datetime.now(UTC),
    )
    payload = CanonicalPayload(schema="titan.test", version=1, value={"test": "data"})

    event = DomainEvent(
        event_id=event_id,
        organization_id=org_id,
        aggregate_reference=aggregate_ref,
        aggregate_version=1,
        event_type="titan.core.test_event",
        event_version=1,
        timestamps=timestamps,
        actor_reference=actor_ref,
        source_reference=producer_ref,
        correlation_id=correlation_id,
        causation_id=None,
        payload=payload,
    )

    message = OutboxMessage(
        message_id=TypedId.new("outbox_message"),
        organization_id=org_id,
        kind=MessageKind.DOMAIN_EVENT,
        contract_type="titan.core.test_event",
        contract_version=1,
        actor_reference=actor_ref,
        producer_reference=producer_ref,
        timestamps=timestamps,
        correlation_id=correlation_id,
        causation_id=event_id,
        idempotency_key=None,
        payload=payload,
        classification="PROTECTED",
    )

    return event, message


def test_outbox_reconciliation_sweeps_expired_claims_in_postgresql(
    db_connection: Connection,
) -> None:
    org_id = OrganizationId.new()
    db_connection.execute(
        text(
            """
            INSERT INTO core_identity.organizations (organization_id, record_owner_organization_id)
            VALUES (:org_id, :org_id)
            """
        ),
        {"org_id": org_id.value},
    )
    db_connection.execute(
        text("SELECT set_config('titan.organization_id', :org_id, true)"),
        {"org_id": str(org_id.value)},
    )

    # 1. Cria mensagem na Outbox
    event, message = create_sample_event_and_message(org_id)
    writer = TransactionalEventOutboxRepository(db_connection)
    EventOutboxService(writer).append(event, message)

    # 2. Faz claim da mensagem
    pub_state_repo = OutboxPublicationStateRepository(db_connection)
    claimed_msg = pub_state_repo.claim_next(publisher_id="publisher_1")
    assert claimed_msg is not None

    # 3. Simula expiracao da lease retrocedendo o lease_expires_at para o passado
    db_connection.execute(
        text(
            """
            UPDATE core_audit.outbox_publication_state
            SET lease_expires_at = CURRENT_TIMESTAMP - INTERVAL '10 seconds'
            WHERE message_id = :message_id
            """
        ),
        {"message_id": message.message_id.value},
    )

    # 4. Executa o servico de reconciliacao
    recon_repo = TransactionalOutboxReconciliationRepository(db_connection)
    service = OutboxReconciliationService(repository=recon_repo)
    report = service.run()

    # 5. Verifica que o claim expirado foi detectado e liberado
    assert report.summary_before.expired_claims == 1
    assert report.released_claims_count == 1
    assert report.summary_after.expired_claims == 0
    assert report.summary_after.unknown_results == 1

    # 6. Verifica que a mensagem se tornou novamente elegivel para claim_next()
    reclaimed_msg = pub_state_repo.claim_next(publisher_id="publisher_2")
    assert reclaimed_msg is not None
    assert reclaimed_msg.message.message_id == message.message_id
