import os
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import Connection, create_engine, insert, text

from packages.core_application import EventOutboxService, MessageKind, OutboxMessage
from packages.core_domain import CanonicalPayload, DomainEvent
from packages.core_infrastructure.persistence import (
    TransactionalEventOutboxRepository,
    set_local_organization_context,
)
from packages.core_infrastructure.persistence.inbox import (
    inbox_conflicts_table,
    inbox_delivery_attempts_table,
    inbox_messages_table,
    untrusted_message_quarantine_table,
)
from packages.core_infrastructure.persistence.operational_support import (
    OperationalSupportRepository,
)
from packages.core_infrastructure.persistence.outbox import (
    OutboxPublicationStateRepository,
)
from packages.livestock_application.erp_contract import ERP_OPERATIONAL_INTENT_CONTRACT_TYPE
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


def _event_and_message(org_id: OrganizationId) -> tuple[DomainEvent, OutboxMessage]:
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
    payload = CanonicalPayload.from_mapping(schema="titan.test", version=1, value={"x": "y"})
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
        kind=MessageKind.COMMAND,
        contract_type=ERP_OPERATIONAL_INTENT_CONTRACT_TYPE,
        contract_version=1,
        actor_reference=actor_ref,
        producer_reference=producer_ref,
        timestamps=timestamps,
        correlation_id=correlation_id,
        causation_id=event_id,
        idempotency_key="operational-support",
        payload=payload,
        classification="PROTECTED",
    )
    return event, message


def test_operational_support_summary_is_derived_and_tenant_safe(
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
    set_local_organization_context(db_connection, org_id)

    event, message = _event_and_message(org_id)
    EventOutboxService(TransactionalEventOutboxRepository(db_connection)).append(event, message)
    state_repository = OutboxPublicationStateRepository(db_connection)
    claimed = state_repository.claim_next(publisher_id="publisher-1")
    assert claimed is not None
    db_connection.execute(
        text(
            """
            UPDATE core_audit.outbox_publication_state
            SET status = 'RESULTADO_DESCONHECIDO',
                last_reason = 'AMQPConnectionError',
                last_result_at = CURRENT_TIMESTAMP
            WHERE message_id = :message_id
            """
        ),
        {"message_id": message.message_id.value},
    )

    inbox_message_id = TypedId.new("outbox_message")
    db_connection.execute(
        insert(inbox_messages_table).values(
            message_id=inbox_message_id.value,
            record_owner_organization_id=org_id.value,
            message_type=ERP_OPERATIONAL_INTENT_CONTRACT_TYPE,
            schema_version=1,
            semantic_operation_id=TypedId.new("operation").value,
            producer_identity="service-x",
            semantic_message_digest=b"x" * 32,
            authorization_evaluation_mode="SERVICE_AUTHORITY_ONLY",
            status="EM_QUARENTENA",
            available_at=None,
            attempt_number=2,
            received_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            completion_result_code=None,
            effect_reference=None,
            decision_reference=None,
            result_digest=None,
        )
    )
    db_connection.execute(
        insert(inbox_delivery_attempts_table).values(
            attempt_id=TypedId.new("inbox_delivery_attempt").value,
            message_id=inbox_message_id.value,
            record_owner_organization_id=org_id.value,
            consumer_id="worker-1",
            attempt_number=2,
            handling_result="DUPLICATE_RECOVERED",
            attempted_at=datetime.now(UTC),
            reason="DUPLICATE_RECOVERED",
        )
    )
    db_connection.execute(
        insert(inbox_conflicts_table).values(
            conflict_id=TypedId.new("inbox_conflict").value,
            message_id=inbox_message_id.value,
            record_owner_organization_id=org_id.value,
            received_digest=b"a" * 32,
            expected_digest=b"b" * 32,
            handling_result="CONFLICT_DETECTED",
            detected_at=datetime.now(UTC),
        )
    )
    db_connection.execute(
        insert(untrusted_message_quarantine_table).values(
            quarantine_id=TypedId.new("untrusted_quarantine").value,
            message_id=TypedId.new("incoming_message").value,
            alleged_producer="service-y",
            alleged_organization=str(org_id.value),
            received_bytes_digest=b"z" * 32,
            rejection_reason_code="INVALID_SIGNATURE",
            sanitized_routing_metadata=None,
            quarantined_at=datetime.now(UTC),
        )
    )

    summary = OperationalSupportRepository(db_connection).build_summary()

    assert summary.organization_id == org_id
    assert summary.scope == "organization"
    assert summary.unknown_results_total == 1
    assert summary.unknown_results_human_intervention == 1
    assert summary.duplicate_deliveries_detected == 1
    assert summary.duplicate_recoveries_completed == 1
    assert summary.quarantined_messages == 2
    assert summary.diagnostic_condition.value == "INCONSISTENT"
    assert summary.recommended_action == "INVESTIGATE"

    set_local_organization_context(db_connection, other_org_id)
    summary_other = OperationalSupportRepository(db_connection).build_summary()
    assert summary_other.organization_id == other_org_id
    assert summary_other.unknown_results_total == 0
    assert summary_other.quarantined_messages == 0
    assert summary_other.duplicate_deliveries_detected == 0
