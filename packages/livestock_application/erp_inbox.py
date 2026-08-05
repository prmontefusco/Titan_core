"""Handler operacional do contrato neutro POST-LIV-02A no worker."""

import json
from dataclasses import dataclass
from typing import Protocol

from packages.core_application import (
    IncomingMessageEnvelope,
    PermanentConsumptionError,
    ProcessingOutcome,
    TransientConsumptionError,
)
from packages.livestock_application.erp_contract import (
    ERP_OPERATIONAL_INTENT_TYPE,
    ERP_SIMULATION_DEFAULT,
)
from packages.livestock_application.erp_outbox import ERP_TREATMENT_COMMAND_TYPE


class ExternalErpDeliveryPort(Protocol):
    def deliver_treatment_application(
        self, envelope: IncomingMessageEnvelope
    ) -> tuple[ProcessingOutcome, str | None, str | None]: ...


@dataclass(frozen=True, slots=True)
class LivestockErpInboxHandler:
    delivery: ExternalErpDeliveryPort

    def handle(
        self, envelope: IncomingMessageEnvelope
    ) -> tuple[ProcessingOutcome, str | None, str | None]:
        if envelope.contract_type != ERP_TREATMENT_COMMAND_TYPE:
            raise PermanentConsumptionError("CONTRACT_TYPE_NAO_SUPORTADO")
        return self.delivery.deliver_treatment_application(envelope)


@dataclass(frozen=True, slots=True)
class NeutralOperationalIntentSimulatorAdapter:
    """Simulador local do contrato neutro sem adapter ERP concreto."""

    def deliver_treatment_application(
        self, envelope: IncomingMessageEnvelope
    ) -> tuple[ProcessingOutcome, str | None, str | None]:
        payload_data = _decode_payload_data(envelope)
        intent_type = payload_data.get("intent_type")
        if intent_type != ERP_OPERATIONAL_INTENT_TYPE:
            raise PermanentConsumptionError("OPERACAO_ERP_INVALIDA")

        external_operation_id = str(payload_data["external_operation_id"])
        simulation_mode = str(payload_data.get("simulation_mode", ERP_SIMULATION_DEFAULT))
        application_data = payload_data.get("treatment_application")
        if not isinstance(application_data, dict):
            raise PermanentConsumptionError("PAYLOAD_OPERACIONAL_INVALIDO")
        application_id = str(application_data["application_id"])

        if simulation_mode == "external_unknown":
            raise TransientConsumptionError("EXTERNAL_OUTCOME_UNKNOWN")
        if simulation_mode == "external_rejected":
            return (
                ProcessingOutcome.BUSINESS_REJECTION,
                f"external-rejection:{external_operation_id}",
                f"ack:EXTERNAL_REJECTED:{application_id}",
            )
        if simulation_mode == "duplicate_recovered":
            return (
                ProcessingOutcome.NO_OP,
                f"external-duplicate-recovery:{external_operation_id}",
                f"ack:DUPLICATE_RECOVERED:{application_id}",
            )
        if simulation_mode == "duplicate_detected":
            raise PermanentConsumptionError("DUPLICATE_DETECTED_UNRESOLVED")
        if simulation_mode == "indeterminate":
            raise PermanentConsumptionError("EXTERNAL_EVIDENCE_INDETERMINATE")
        if simulation_mode == "inconsistent":
            raise PermanentConsumptionError("EXTERNAL_EVIDENCE_INCONSISTENT")
        if simulation_mode == "external_received":
            return (
                ProcessingOutcome.SUCCESS,
                f"external-receipt:{external_operation_id}",
                f"ack:EXTERNAL_RECEIVED:{application_id}",
            )
        if simulation_mode == "external_accepted":
            return (
                ProcessingOutcome.SUCCESS,
                f"external-acceptance:{external_operation_id}",
                f"ack:EXTERNAL_ACCEPTED:{application_id}",
            )

        return (
            ProcessingOutcome.SUCCESS,
            f"external-effect:{external_operation_id}",
            f"ack:EXTERNAL_APPLIED:{application_id}",
        )


InMemoryLivestockErpDeliveryAdapter = NeutralOperationalIntentSimulatorAdapter


def _decode_payload_data(envelope: IncomingMessageEnvelope) -> dict[str, object]:
    raw_envelope = json.loads(envelope.payload.canonical_bytes.decode("utf-8"))
    if not isinstance(raw_envelope, list) or len(raw_envelope) != 2:
        raise ValueError("Envelope canonico invalido para handler operacional.")
    normalized = raw_envelope[1]
    decoded = _denormalize(normalized)
    if not isinstance(decoded, dict):
        raise ValueError("Payload canonico invalido para handler operacional.")
    data = decoded.get("data")
    if not isinstance(data, dict):
        raise ValueError("Campo 'data' ausente no payload canonico operacional.")
    return data


def _denormalize(value: object) -> object:
    if value == ["null"]:
        return None
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError("Payload canonico invalido para handler operacional.")
    value_type, payload = value
    if value_type == "string":
        return payload
    if value_type == "integer":
        return int(payload)
    if value_type == "boolean":
        return payload == "true"
    if value_type == "datetime":
        return payload
    if value_type == "list":
        return [_denormalize(item) for item in payload]
    if value_type == "map":
        return {key: _denormalize(item) for key, item in payload}
    return payload
