"""Testes unitarios de deduplicacao semantica e digest do envelope (ADR-0038/Passo 4.9B)."""

from datetime import UTC, datetime

from packages.core_application.inbox import (
    AuthorizationEvaluationMode,
    IncomingMessageEnvelope,
)
from packages.core_application.outbox import MessageKind
from packages.core_domain import CanonicalPayload
from packages.shared_kernel import OrganizationId, RecordTimestamps, TypedId, UniversalReference


def test_semantic_digest_changes_when_payload_changes() -> None:
    org_id = OrganizationId.new()
    msg_id = TypedId(entity_type="outbox_message", value=TypedId.new("outbox_message").value)

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

    payload1 = CanonicalPayload(schema="titan.test", version=1, value={"amount": 100})
    payload2 = CanonicalPayload(schema="titan.test", version=1, value={"amount": 200})

    envelope1 = IncomingMessageEnvelope(
        message_id=msg_id,
        organization_id=org_id,
        kind=MessageKind.COMMAND,
        contract_type="titan.core.command",
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
        causation_id=TypedId(entity_type="command", value=TypedId.new("command").value),
        auth_evaluation_mode=AuthorizationEvaluationMode.SERVICE_AUTHORITY_ONLY,
        purpose="DEDUPLICATION_TESTING",
        auth_reference=None,
        payload=payload1,
        classification="PROTECTED",
    )

    envelope2 = IncomingMessageEnvelope(
        message_id=msg_id,
        organization_id=org_id,
        kind=MessageKind.COMMAND,
        contract_type="titan.core.command",
        contract_version=1,
        semantic_operation_id=envelope1.semantic_operation_id,
        actor_reference=actor_ref,
        producer_reference=producer_ref,
        timestamps=envelope1.timestamps,
        correlation_id=envelope1.correlation_id,
        causation_id=envelope1.causation_id,
        auth_evaluation_mode=AuthorizationEvaluationMode.SERVICE_AUTHORITY_ONLY,
        purpose="DEDUPLICATION_TESTING",
        auth_reference=None,
        payload=payload2,
        classification="PROTECTED",
    )

    assert envelope1.compute_semantic_digest() != envelope2.compute_semantic_digest()
