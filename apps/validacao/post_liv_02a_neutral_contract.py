"""Roteiro executavel do POST-LIV-02A.

Uso:
  python -m uv run --locked python -m apps.validacao.post_liv_02a_neutral_contract
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from packages.core_application import (
    AuthorizationEvaluationMode,
    IncomingMessageEnvelope,
    MessageKind,
    OutboxMessage,
)
from packages.core_domain import DomainEvent
from packages.livestock_application.erp_contract import (
    ERP_OPERATIONAL_INTENT_CONTRACT_TYPE,
    build_treatment_operational_intent_payload,
)
from packages.livestock_application.erp_inbox import NeutralOperationalIntentSimulatorAdapter
from packages.livestock_application.erp_outbox import LivestockErpOutboxService
from packages.livestock_application.event_recorder import LivestockOperationContext
from packages.livestock_domain.treatment import TreatmentApplication
from packages.shared_kernel import OrganizationId, RecordTimestamps, TypedId, UniversalReference


class CaptureWriter:
    def __init__(self) -> None:
        self.message: OutboxMessage | None = None

    def append(self, message: OutboxMessage) -> None:
        self.message = message


def _context(organization_id: OrganizationId) -> LivestockOperationContext:
    return LivestockOperationContext(
        organization_id=organization_id,
        actor_reference=UniversalReference(
            target_id=TypedId(entity_type="user", value=TypedId.new("user").value),
            organization_id=organization_id,
            contract_version=1,
        ),
        source_reference=UniversalReference(
            target_id=TypedId(entity_type="service", value=TypedId.new("service").value),
            organization_id=organization_id,
            contract_version=1,
        ),
        correlation_id=TypedId(entity_type="correlation", value=TypedId.new("correlation").value),
    )


def _application(organization_id: OrganizationId) -> TreatmentApplication:
    return TreatmentApplication(
        application_id=TypedId.new("treatment_application"),
        organization_id=organization_id,
        animal_id=TypedId.new("animal"),
        medication_batch_id=TypedId.new("medication_batch"),
        actor_id=TypedId.new("actor"),
        applied_at=datetime.now(UTC),
        dose="1 mL",
    )


def _event(context: LivestockOperationContext, application: TreatmentApplication) -> DomainEvent:
    return DomainEvent(
        event_id=TypedId(entity_type="domain_event", value=TypedId.new("domain_event").value),
        organization_id=application.organization_id,
        aggregate_reference=UniversalReference(
            target_id=application.application_id,
            organization_id=application.organization_id,
            contract_version=1,
        ),
        aggregate_version=1,
        event_type="livestock.treatment_application.applied",
        event_version=1,
        timestamps=RecordTimestamps(
            occurred_at=application.applied_at,
            recorded_at=application.applied_at,
        ),
        actor_reference=context.actor_reference,
        source_reference=context.source_reference,
        correlation_id=context.correlation_id,
        causation_id=None,
        payload=build_treatment_operational_intent_payload(application),
    )


def main() -> int:
    organization_id = OrganizationId.new()
    context = _context(organization_id)
    application = _application(organization_id)
    payload = build_treatment_operational_intent_payload(application)
    event = _event(context, application)

    print("STEP 1: publicar um contrato outbound neutro")
    print("WHY: provar que Titan emite intencao operacional auditavel sem semantica de fornecedor.")
    print(
        json.dumps(
            {
                "contract_type": ERP_OPERATIONAL_INTENT_CONTRACT_TYPE,
                "payload_schema": payload.schema,
                "payload_preview": payload.canonical_bytes.decode("utf-8"),
            },
            indent=2,
        )
    )

    writer = CaptureWriter()
    service = LivestockErpOutboxService(writer=writer)
    service.publish_treatment_application(
        context=context,
        application=application,
        event=event,
    )
    if writer.message is None:
        raise RuntimeError("Falha ao capturar mensagem outbound do POST-LIV-02A.")
    message = writer.message

    envelope = IncomingMessageEnvelope(
        message_id=message.message_id,
        organization_id=organization_id,
        kind=MessageKind.COMMAND,
        contract_type=message.contract_type,
        contract_version=message.contract_version,
        semantic_operation_id=TypedId(
            entity_type="operation",
            value=TypedId.new("operation").value,
        ),
        actor_reference=context.actor_reference,
        producer_reference=context.source_reference,
        timestamps=message.timestamps,
        correlation_id=context.correlation_id,
        causation_id=message.causation_id,
        auth_evaluation_mode=AuthorizationEvaluationMode.SERVICE_AUTHORITY_ONLY,
        purpose="POST_LIV_02A_VALIDATION",
        auth_reference=None,
        payload=message.payload,
        classification=message.classification,
    )

    print("STEP 2: simular confirmacao externa aplicada")
    print("WHY: provar que o simulador exercita acknowledgement explicito sem ERP real.")
    success = NeutralOperationalIntentSimulatorAdapter().deliver_treatment_application(envelope)
    print(
        json.dumps(
            {
                "processing_outcome": success[0].value,
                "effect_reference": success[1],
                "decision_reference": success[2],
            },
            indent=2,
        )
    )

    print("STEP 3: simular resultado externo desconhecido")
    print("WHY: provar que ausencia de confirmacao continua honesta e nao vira sucesso silencioso.")
    unknown_payload = build_treatment_operational_intent_payload(
        application,
        simulation_mode="external_unknown",
    )
    unknown_envelope = IncomingMessageEnvelope(
        message_id=message.message_id,
        organization_id=organization_id,
        kind=MessageKind.COMMAND,
        contract_type=message.contract_type,
        contract_version=message.contract_version,
        semantic_operation_id=TypedId(
            entity_type="operation",
            value=TypedId.new("operation").value,
        ),
        actor_reference=context.actor_reference,
        producer_reference=context.source_reference,
        timestamps=message.timestamps,
        correlation_id=context.correlation_id,
        causation_id=message.causation_id,
        auth_evaluation_mode=AuthorizationEvaluationMode.SERVICE_AUTHORITY_ONLY,
        purpose="POST_LIV_02A_VALIDATION",
        auth_reference=None,
        payload=unknown_payload,
        classification=message.classification,
    )
    try:
        NeutralOperationalIntentSimulatorAdapter().deliver_treatment_application(unknown_envelope)
    except Exception as exc:
        print(json.dumps({"unknown_outcome": exc.__class__.__name__, "reason": str(exc)}, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
