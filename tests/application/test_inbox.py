"""Testes unitarios dos contratos da Inbox e envelope canonico (ADR-0038)."""

from datetime import UTC, datetime

import pytest

from packages.core_application.inbox import (
    AuthorizationEvaluationMode,
    IncomingMessageEnvelope,
)
from packages.core_application.outbox import MessageKind
from packages.core_domain import CanonicalPayload
from packages.shared_kernel import OrganizationId, RecordTimestamps, TypedId, UniversalReference


def test_incoming_message_envelope_digest_determinism() -> None:
    org_id = OrganizationId.new()
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

    envelope1 = IncomingMessageEnvelope(
        message_id=TypedId(entity_type="outbox_message", value=TypedId.new("outbox_message").value),
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
            occurred_at=datetime(2026, 7, 22, 10, 0, tzinfo=UTC),
            recorded_at=datetime(2026, 7, 22, 10, 0, tzinfo=UTC),
        ),
        correlation_id=TypedId(entity_type="correlation", value=TypedId.new("correlation").value),
        causation_id=TypedId(entity_type="domain_event", value=TypedId.new("domain_event").value),
        auth_evaluation_mode=AuthorizationEvaluationMode.SERVICE_AUTHORITY_ONLY,
        purpose="TESTING",
        auth_reference=None,
        payload=payload,
        classification="PROTECTED",
    )

    digest1 = envelope1.compute_semantic_digest()
    digest2 = envelope1.compute_semantic_digest()
    assert digest1 == digest2
    assert len(digest1) == 32


def test_incoming_message_envelope_requires_auth_reference_when_at_acceptance() -> None:
    org_id = OrganizationId.new()
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

    with pytest.raises(ValueError, match="Mensagens AT_ACCEPTANCE exigem auth_reference"):
        IncomingMessageEnvelope(
            message_id=TypedId(
                entity_type="outbox_message", value=TypedId.new("outbox_message").value
            ),
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
                occurred_at=datetime(2026, 7, 22, 10, 0, tzinfo=UTC),
                recorded_at=datetime(2026, 7, 22, 10, 0, tzinfo=UTC),
            ),
            correlation_id=TypedId(
                entity_type="correlation", value=TypedId.new("correlation").value
            ),
            causation_id=TypedId(entity_type="command", value=TypedId.new("command").value),
            auth_evaluation_mode=AuthorizationEvaluationMode.AT_ACCEPTANCE,
            purpose="TESTING",
            auth_reference=None,
            payload=payload,
            classification="PROTECTED",
        )
