"""Roteiro executavel minimo do LIV-C09.

Uso:
  python -m uv run --locked python -m apps.validacao.liv_c09_integracao_operacional
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime

from sqlalchemy import create_engine, select, text

from packages.core_application import (
    AuthorizationEvaluationMode,
    IncomingMessageEnvelope,
    MessageKind,
)
from packages.core_domain import CanonicalPayload
from packages.core_infrastructure.persistence.events import domain_events_table
from packages.core_infrastructure.persistence.inbox import TransactionalInboxRepository
from packages.core_infrastructure.persistence.outbox import outbox_messages_table
from packages.livestock_application.erp_contract import (
    ERP_OPERATIONAL_INTENT_CONTRACT_TYPE,
    ERP_OPERATIONAL_INTENT_PAYLOAD_SCHEMA,
    ERP_OPERATIONAL_INTENT_TYPE,
)
from packages.livestock_application.erp_inbox import (
    InMemoryLivestockErpDeliveryAdapter,
    LivestockErpInboxHandler,
)
from packages.shared_kernel import OrganizationId, RecordTimestamps, TypedId, UniversalReference


def main() -> int:
    db_url = os.environ.get(
        "TITAN_DATABASE_URL",
        "postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan",
    )
    engine = create_engine(db_url, pool_pre_ping=True)
    org_id = OrganizationId.new()
    message_id = TypedId.new("outbox_message")
    event_id = TypedId.new("domain_event")
    correlation_id = TypedId.new("correlation")
    causation_id = TypedId.new("domain_event")
    aggregate_id = TypedId.new("treatment_application")
    occurred_at = datetime.now(UTC)
    recorded_at = datetime.now(UTC)
    payload = CanonicalPayload.from_mapping(
        schema=ERP_OPERATIONAL_INTENT_PAYLOAD_SCHEMA,
        version=1,
        value={
            "intent_type": ERP_OPERATIONAL_INTENT_TYPE,
            "contract_profile": "POST_LIV_02A_NEUTRAL_EXTERNAL_CONTRACT",
            "contract_version": 1,
            "external_operation_id": f"livestock-treatment-application:{aggregate_id.value}",
            "source_application_id": str(aggregate_id.value),
            "requested_effect": "REFLECT_TREATMENT_APPLICATION",
            "tenant_scope": "ORGANIZATION_ISOLATED",
            "authoritative_source": "titan",
            "treatment_application": {
                "application_id": str(aggregate_id.value),
            },
        },
    )

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

        connection.execute(
            domain_events_table.insert().values(
                event_id=event_id.value,
                record_owner_organization_id=org_id.value,
                aggregate_type="treatment_application",
                aggregate_id=aggregate_id.value,
                aggregate_contract_version=1,
                aggregate_version=1,
                event_type="livestock.treatment_application.mirrored",
                event_version=1,
                occurred_at=occurred_at,
                recorded_at=recorded_at,
                actor_type="user",
                actor_id=actor_ref.target_id.value,
                actor_organization_id=org_id.value,
                actor_contract_version=1,
                source_type="service",
                source_id=producer_ref.target_id.value,
                source_organization_id=org_id.value,
                source_contract_version=1,
                correlation_id=correlation_id.value,
                causation_id=causation_id.value,
                payload_schema=payload.schema,
                payload_version=payload.version,
                payload_canonical_bytes=payload.canonical_bytes,
            )
        )

        connection.execute(
            outbox_messages_table.insert().values(
                message_id=message_id.value,
                record_owner_organization_id=org_id.value,
                kind="COMMAND",
                contract_type=ERP_OPERATIONAL_INTENT_CONTRACT_TYPE,
                contract_version=1,
                actor_type="user",
                actor_id=actor_ref.target_id.value,
                producer_type="service",
                producer_id=producer_ref.target_id.value,
                occurred_at=occurred_at,
                recorded_at=recorded_at,
                correlation_id=correlation_id.value,
                causation_id=event_id.value,
                idempotency_key=f"liv-c09:{message_id.value}",
                payload_schema=payload.schema,
                payload_version=payload.version,
                payload_canonical_bytes=payload.canonical_bytes,
                classification="PROTECTED",
                status="PENDENTE",
            )
        )

        envelope = IncomingMessageEnvelope(
            message_id=message_id,
            organization_id=org_id,
            kind=MessageKind.COMMAND,
            contract_type=ERP_OPERATIONAL_INTENT_CONTRACT_TYPE,
            contract_version=1,
            semantic_operation_id=TypedId(
                entity_type="operation", value=TypedId.new("operation").value
            ),
            actor_reference=actor_ref,
            producer_reference=producer_ref,
            timestamps=RecordTimestamps(
                occurred_at=occurred_at,
                recorded_at=recorded_at,
            ),
            correlation_id=TypedId(entity_type="correlation", value=correlation_id.value),
            causation_id=TypedId(entity_type="domain_event", value=event_id.value),
            auth_evaluation_mode=AuthorizationEvaluationMode.SERVICE_AUTHORITY_ONLY,
            purpose="LIV_C09_VALIDATION",
            auth_reference=None,
            payload=payload,
            classification="PROTECTED",
        )

        receipt = TransactionalInboxRepository(
            connection=connection,
            consumer_id="liv_c09_validation_worker",
        ).process_message(
            envelope=envelope,
            handler=LivestockErpInboxHandler(delivery=InMemoryLivestockErpDeliveryAdapter()),
        )

        print(
            json.dumps(
                {
                    "organization_id": str(org_id.value),
                    "message_id": str(message_id.value),
                    "handling_outcome": receipt.handling_outcome.value,
                    "processing_outcome": (
                        None
                        if receipt.processing_outcome is None
                        else receipt.processing_outcome.value
                    ),
                    "effect_reference": receipt.effect_reference,
                    "decision_reference": receipt.decision_reference,
                    "note": (
                        "Inbox acceptance is local technical handling only; it is not ERP proof."
                    ),
                },
                indent=2,
            )
        )

        persisted = connection.execute(
            select(outbox_messages_table.c.contract_type).where(
                outbox_messages_table.c.record_owner_organization_id == org_id.value
            )
        ).scalar_one()
        print(json.dumps({"persisted_outbox_contract_type": persisted}, indent=2))

    engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
