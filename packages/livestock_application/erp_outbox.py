"""Publicacao do contrato outbound neutro do POST-LIV-02A."""

from dataclasses import dataclass

from packages.core_application import MessageKind, OutboxMessage
from packages.core_domain import DomainEvent
from packages.livestock_application.erp_contract import (
    ERP_OPERATIONAL_INTENT_CONTRACT_TYPE,
    ERP_OPERATIONAL_INTENT_CONTRACT_VERSION,
    build_treatment_operational_intent_payload,
    external_operation_id_for_application,
)
from packages.livestock_application.event_recorder import LivestockOperationContext
from packages.livestock_domain.treatment import TreatmentApplication
from packages.shared_kernel import TypedId

ERP_TREATMENT_COMMAND_TYPE = ERP_OPERATIONAL_INTENT_CONTRACT_TYPE
ERP_TREATMENT_COMMAND_VERSION = ERP_OPERATIONAL_INTENT_CONTRACT_VERSION


class OutboxMessageWriterPort:
    def append(self, message: OutboxMessage) -> None: ...


@dataclass(frozen=True, slots=True)
class LivestockErpOutboxService:
    writer: OutboxMessageWriterPort

    def publish_treatment_application(
        self,
        *,
        context: LivestockOperationContext,
        application: TreatmentApplication,
        event: DomainEvent,
    ) -> OutboxMessage:
        payload = build_treatment_operational_intent_payload(application)
        message = OutboxMessage(
            message_id=TypedId.new("outbox_message"),
            organization_id=application.organization_id,
            kind=MessageKind.COMMAND,
            contract_type=ERP_TREATMENT_COMMAND_TYPE,
            contract_version=ERP_TREATMENT_COMMAND_VERSION,
            actor_reference=event.actor_reference,
            producer_reference=context.source_reference,
            timestamps=event.timestamps,
            correlation_id=event.correlation_id,
            causation_id=event.event_id,
            idempotency_key=external_operation_id_for_application(application),
            payload=payload,
            classification="PROTECTED",
        )
        self.writer.append(message)
        return message
