"""Testes de integracao com PostgreSQL real cobrindo o fluxo completo da Inbox (Passo 4.9B)."""

import os
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import Connection, create_engine, text

from packages.core_application import (
    AuthorizationEvaluationMode,
    DeliveryHandlingOutcome,
    IncomingMessageEnvelope,
    MessageKind,
    ProcessingOutcome,
)
from packages.core_domain import CanonicalPayload
from packages.core_infrastructure.persistence.inbox import TransactionalInboxRepository
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


class SampleHandler:
    def handle(
        self, envelope: IncomingMessageEnvelope
    ) -> tuple[ProcessingOutcome, str | None, str | None]:
        return (ProcessingOutcome.SUCCESS, f"effect:{envelope.message_id.value}", "decision:1")


def create_envelope(
    org_id: OrganizationId, msg_id: TypedId, payload_val: dict[str, int]
) -> IncomingMessageEnvelope:
    actor_ref = UniversalReference(
        target_id=TypedId(entity_type="user", value=TypedId.new("user").value),
        organization_id=org_id,
        contract_version=1,
    )
    producer_ref = UniversalReference(
        target_id=TypedId(entity_type="service", value=TypedId.new("service").value),
        organization_id=org_id,
        contract_version=1,
    )
    payload = CanonicalPayload(schema="titan.test", version=1, value=payload_val)

    return IncomingMessageEnvelope(
        message_id=msg_id,
        organization_id=org_id,
        kind=MessageKind.DOMAIN_EVENT,
        contract_type="titan.core.event",
        contract_version=1,
        semantic_operation_id=TypedId(
            entity_type="operation",
            value=TypedId.new("operation").value,
        ),
        actor_reference=actor_ref,
        producer_reference=producer_ref,
        timestamps=RecordTimestamps(
            occurred_at=datetime.now(UTC),
            recorded_at=datetime.now(UTC),
        ),
        correlation_id=TypedId(entity_type="correlation", value=TypedId.new("correlation").value),
        causation_id=TypedId(entity_type="domain_event", value=TypedId.new("domain_event").value),
        auth_evaluation_mode=AuthorizationEvaluationMode.SERVICE_AUTHORITY_ONLY,
        purpose="FLOW_TESTING",
        auth_reference=None,
        payload=payload,
        classification="PROTECTED",
    )


def test_inbox_postgresql_flow_duplicate_and_conflict_detection(
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

    msg_id = TypedId.new("outbox_message")
    envelope1 = create_envelope(org_id, msg_id, {"val": 100})
    envelope_conflict = create_envelope(org_id, msg_id, {"val": 999})

    repo = TransactionalInboxRepository(connection=db_connection, consumer_id="flow_worker")
    handler = SampleHandler()

    # 1. Processamento inicial
    receipt1 = repo.process_message(envelope=envelope1, handler=handler)
    assert receipt1.handling_outcome == DeliveryHandlingOutcome.PROCESSED
    assert receipt1.processing_outcome == ProcessingOutcome.SUCCESS

    # 2. Re-entrega com mesmo digest -> DUPLICATE_RECOVERED
    receipt2 = repo.process_message(envelope=envelope1, handler=handler)
    assert receipt2.handling_outcome == DeliveryHandlingOutcome.DUPLICATE_RECOVERED
    assert receipt2.effect_reference == f"effect:{msg_id.value}"

    # 3. Re-entrega com mesmo message_id mas digest alterado -> CONFLICT_DETECTED
    receipt3 = repo.process_message(envelope=envelope_conflict, handler=handler)
    assert receipt3.handling_outcome == DeliveryHandlingOutcome.CONFLICT_DETECTED
