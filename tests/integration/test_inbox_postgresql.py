"""Testes de integracao com banco PostgreSQL real para Inbox (ADR-0038)."""

import os
from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import Connection, create_engine, text

from packages.core_application import (
    AuthorizationEvaluationMode,
    DeliveryHandlingOutcome,
    IncomingMessageEnvelope,
    MessageKind,
    PermanentConsumptionError,
    ProcessingOutcome,
    TransientConsumptionError,
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


class SuccessHandler:
    def handle(
        self, envelope: IncomingMessageEnvelope
    ) -> tuple[ProcessingOutcome, str | None, str | None]:
        return (ProcessingOutcome.SUCCESS, f"effect:{envelope.message_id.value}", "decision:1")


class TransientFailureHandler:
    def handle(
        self, envelope: IncomingMessageEnvelope
    ) -> tuple[ProcessingOutcome, str | None, str | None]:
        raise TransientConsumptionError("DELIVERY_OUTCOME_UNKNOWN")


class PermanentFailureHandler:
    def handle(
        self, envelope: IncomingMessageEnvelope
    ) -> tuple[ProcessingOutcome, str | None, str | None]:
        raise PermanentConsumptionError("DELIVERY_REJECTED")


def create_sample_envelope(org_id: OrganizationId, msg_id: TypedId) -> IncomingMessageEnvelope:
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
    payload = CanonicalPayload(schema="titan.test", version=1, value={"key": "val"})

    return IncomingMessageEnvelope(
        message_id=msg_id,
        organization_id=org_id,
        kind=MessageKind.DOMAIN_EVENT,
        contract_type="titan.core.event",
        contract_version=1,
        semantic_operation_id=TypedId(
            entity_type="operation", value=TypedId.new("operation").value
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
        purpose="INTEGRATION_TESTING",
        auth_reference=None,
        payload=payload,
        classification="PROTECTED",
    )


def test_inbox_postgresql_atomic_processing(db_connection: Connection) -> None:
    org_id = OrganizationId.new()
    # Adiciona a Organization temporaria
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
    envelope = create_sample_envelope(org_id, msg_id)
    repo = TransactionalInboxRepository(connection=db_connection, consumer_id="test_worker")
    handler = SuccessHandler()

    receipt = repo.process_message(envelope=envelope, handler=handler)

    assert receipt.handling_outcome == DeliveryHandlingOutcome.PROCESSED
    assert receipt.processing_outcome == ProcessingOutcome.SUCCESS
    assert receipt.effect_reference == f"effect:{msg_id.value}"


def test_inbox_postgresql_duplicate_recovered(db_connection: Connection) -> None:

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
    envelope = create_sample_envelope(org_id, msg_id)
    repo = TransactionalInboxRepository(connection=db_connection, consumer_id="test_worker")
    handler = SuccessHandler()

    # Primeiro processamento
    receipt1 = repo.process_message(envelope=envelope, handler=handler)
    assert receipt1.handling_outcome == DeliveryHandlingOutcome.PROCESSED

    # Segundo processamento da mesma mensagem (redelivery)
    receipt2 = repo.process_message(envelope=envelope, handler=handler)
    assert receipt2.handling_outcome == DeliveryHandlingOutcome.DUPLICATE_RECOVERED
    assert receipt2.processing_outcome == ProcessingOutcome.SUCCESS


def test_inbox_postgresql_transient_failure_schedules_retry(db_connection: Connection) -> None:
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
    envelope = create_sample_envelope(org_id, msg_id)
    repo = TransactionalInboxRepository(connection=db_connection, consumer_id="test_worker")

    receipt = repo.process_message(envelope=envelope, handler=TransientFailureHandler())

    assert receipt.handling_outcome == DeliveryHandlingOutcome.RETRY_SCHEDULED
    row = db_connection.execute(
        text(
            """
            SELECT status, completion_result_code, available_at
            FROM core_messaging.inbox_messages
            WHERE message_id = :message_id
            """
        ),
        {"message_id": msg_id.value},
    ).one()
    assert row.status == "AGUARDANDO_RETRY"
    assert row.completion_result_code is None
    assert row.available_at is not None


def test_inbox_postgresql_permanent_failure_goes_to_quarantine(db_connection: Connection) -> None:
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
    envelope = create_sample_envelope(org_id, msg_id)
    repo = TransactionalInboxRepository(connection=db_connection, consumer_id="test_worker")

    receipt = repo.process_message(envelope=envelope, handler=PermanentFailureHandler())

    assert receipt.handling_outcome == DeliveryHandlingOutcome.QUARANTINED
    assert receipt.reason == "DELIVERY_REJECTED"
    row = db_connection.execute(
        text(
            """
            SELECT status, completion_result_code
            FROM core_messaging.inbox_messages
            WHERE message_id = :message_id
            """
        ),
        {"message_id": msg_id.value},
    ).one()
    assert row.status == "EM_QUARENTENA"
    assert row.completion_result_code is None


def test_inbox_postgresql_cross_organization_message_is_not_visible(
    db_connection: Connection,
) -> None:
    org_id = OrganizationId.new()
    other_org_id = OrganizationId.new()
    db_connection.execute(
        text(
            """
            INSERT INTO core_identity.organizations (organization_id, record_owner_organization_id)
            VALUES (:org_a, :org_a), (:org_b, :org_b)
            """
        ),
        {"org_a": org_id.value, "org_b": other_org_id.value},
    )

    msg_id = TypedId.new("outbox_message")
    repo = TransactionalInboxRepository(connection=db_connection, consumer_id="test_worker")
    receipt = repo.process_message(
        envelope=create_sample_envelope(org_id, msg_id),
        handler=SuccessHandler(),
    )
    assert receipt.handling_outcome == DeliveryHandlingOutcome.PROCESSED

    role_name = f"titan_rls_inbox_{uuid4().hex[:12]}"
    quoted_role = f'"{role_name}"'
    db_connection.execute(
        text(
            f"CREATE ROLE {quoted_role} "
            "NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS"
        )
    )
    db_connection.execute(text(f"GRANT USAGE ON SCHEMA core_messaging TO {quoted_role}"))
    db_connection.execute(text(f"GRANT SELECT ON core_messaging.inbox_messages TO {quoted_role}"))
    db_connection.execute(text(f"SET LOCAL ROLE {quoted_role}"))
    db_connection.execute(
        text("SELECT set_config('titan.organization_id', :org_id, true)"),
        {"org_id": str(other_org_id.value)},
    )
    visible = db_connection.execute(
        text(
            """
            SELECT count(*)
            FROM core_messaging.inbox_messages
            WHERE message_id = :message_id
            """
        ),
        {"message_id": msg_id.value},
    ).scalar_one()
    assert visible == 0
    db_connection.execute(text("RESET ROLE"))
    db_connection.execute(text(f"DROP OWNED BY {quoted_role}"))
    db_connection.execute(text(f"DROP ROLE {quoted_role}"))
