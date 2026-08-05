"""Roteiro executavel do POST-LIV-01 para suporte operacional derivado.

Uso:
  python -m uv run --locked python -m apps.validacao.post_liv_01_operational_summary
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime

from sqlalchemy import create_engine, insert, text

from packages.core_application import EventOutboxService, MessageKind, OutboxMessage
from packages.core_application.operational_support import OperationalSupportService
from packages.core_domain import CanonicalPayload, DomainEvent
from packages.core_infrastructure.persistence import (
    TransactionalEventOutboxRepository,
    set_local_organization_context,
)
from packages.core_infrastructure.persistence.inbox import (
    inbox_delivery_attempts_table,
    inbox_messages_table,
    untrusted_message_quarantine_table,
)
from packages.core_infrastructure.persistence.operational_support import (
    OperationalSupportRepository,
)
from packages.core_infrastructure.persistence.outbox import OutboxPublicationStateRepository
from packages.livestock_application.erp_contract import (
    ERP_OPERATIONAL_INTENT_CONTRACT_TYPE,
    ERP_OPERATIONAL_INTENT_PAYLOAD_SCHEMA,
    ERP_OPERATIONAL_INTENT_TYPE,
)
from packages.shared_kernel import OrganizationId, RecordTimestamps, TypedId, UniversalReference


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
    payload = CanonicalPayload.from_mapping(
        schema=ERP_OPERATIONAL_INTENT_PAYLOAD_SCHEMA,
        version=1,
        value={
            "intent_type": ERP_OPERATIONAL_INTENT_TYPE,
            "contract_profile": "POST_LIV_02A_NEUTRAL_EXTERNAL_CONTRACT",
            "contract_version": 1,
            "external_operation_id": (
                f"livestock-treatment-application:{TypedId.new('treatment_application').value}"
            ),
            "source_application_id": str(TypedId.new("treatment_application").value),
            "requested_effect": "REFLECT_TREATMENT_APPLICATION",
            "tenant_scope": "ORGANIZATION_ISOLATED",
            "authoritative_source": "titan",
            "treatment_application": {
                "application_id": str(TypedId.new("treatment_application").value),
            },
        },
    )
    event = DomainEvent(
        event_id=event_id,
        organization_id=org_id,
        aggregate_reference=aggregate_ref,
        aggregate_version=1,
        event_type="livestock.treatment_application.mirrored",
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
        idempotency_key=f"post-liv-01:{event_id.value}",
        payload=payload,
        classification="PROTECTED",
    )
    return event, message


def main() -> int:
    db_url = os.environ.get(
        "TITAN_DATABASE_URL",
        "postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan",
    )
    engine = create_engine(db_url, pool_pre_ping=True)
    org_id = OrganizationId.new()

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO core_identity.organizations (
                    organization_id,
                    record_owner_organization_id
                )
                VALUES (:org_id, :org_id)
                ON CONFLICT (organization_id) DO NOTHING
                """
            ),
            {"org_id": org_id.value},
        )
        set_local_organization_context(connection, org_id)

        event, message = _event_and_message(org_id)
        EventOutboxService(TransactionalEventOutboxRepository(connection)).append(event, message)
        claimed = OutboxPublicationStateRepository(connection).claim_next(publisher_id="validation")
        assert claimed is not None
        connection.execute(
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
        connection.execute(
            insert(inbox_messages_table).values(
                message_id=inbox_message_id.value,
                record_owner_organization_id=org_id.value,
                message_type=ERP_OPERATIONAL_INTENT_CONTRACT_TYPE,
                schema_version=1,
                semantic_operation_id=TypedId.new("operation").value,
                producer_identity="service-validation",
                semantic_message_digest=b"v" * 32,
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
        connection.execute(
            insert(inbox_delivery_attempts_table).values(
                attempt_id=TypedId.new("inbox_delivery_attempt").value,
                message_id=inbox_message_id.value,
                record_owner_organization_id=org_id.value,
                consumer_id="worker-validation",
                attempt_number=2,
                handling_result="DUPLICATE_RECOVERED",
                attempted_at=datetime.now(UTC),
                reason="DUPLICATE_RECOVERED",
            )
        )
        connection.execute(
            insert(untrusted_message_quarantine_table).values(
                quarantine_id=TypedId.new("untrusted_quarantine").value,
                message_id=TypedId.new("incoming_message").value,
                alleged_producer="service-validation",
                alleged_organization=str(org_id.value),
                received_bytes_digest=b"q" * 32,
                rejection_reason_code="INVALID_SIGNATURE",
                sanitized_routing_metadata=None,
                quarantined_at=datetime.now(UTC),
            )
        )

        summary = OperationalSupportService(
            repository=OperationalSupportRepository(connection)
        ).summary()
        print(
            json.dumps(
                {
                    "organization_id": str(summary.organization_id.value),
                    "observed_at": summary.observed_at.isoformat(),
                    "scope": summary.scope,
                    "diagnostic_condition": summary.diagnostic_condition.value,
                    "total_pending_outbox": summary.total_pending_outbox,
                    "unknown_results_total": summary.unknown_results_total,
                    "quarantined_messages": summary.quarantined_messages,
                    "duplicate_deliveries_detected": summary.duplicate_deliveries_detected,
                    "duplicate_recoveries_completed": summary.duplicate_recoveries_completed,
                    "recommended_action": summary.recommended_action,
                    "automatic_retry_allowed": summary.automatic_retry_allowed,
                    "reason_code": summary.reason_code,
                    "note": (
                        "This is a derived diagnostic projection. "
                        "It does not replace native Outbox or Inbox records."
                    ),
                },
                indent=2,
            )
        )

    engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
