from datetime import UTC, datetime
from typing import Any

import pytest

from packages.core_application import (
    AuthorizationEvaluationMode,
    IncomingMessageEnvelope,
    MessageKind,
    ProcessingOutcome,
    TransientConsumptionError,
)
from packages.core_domain import CanonicalPayload
from packages.livestock_application.erp_contract import (
    ERP_OPERATIONAL_INTENT_PAYLOAD_SCHEMA,
    ERP_OPERATIONAL_INTENT_TYPE,
)
from packages.livestock_application.erp_inbox import (
    LivestockErpInboxHandler,
    NeutralOperationalIntentSimulatorAdapter,
)
from packages.livestock_application.erp_outbox import ERP_TREATMENT_COMMAND_TYPE
from packages.shared_kernel import OrganizationId, RecordTimestamps, TypedId, UniversalReference


def _envelope(*, simulate: str | None = None) -> IncomingMessageEnvelope:
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
    operation_id = TypedId.new("treatment_application")
    value: dict[str, Any] = {
        "intent_type": ERP_OPERATIONAL_INTENT_TYPE,
        "contract_profile": "POST_LIV_02A_NEUTRAL_EXTERNAL_CONTRACT",
        "contract_version": 1,
        "external_operation_id": f"livestock-treatment-application:{operation_id.value}",
        "source_application_id": str(operation_id.value),
        "requested_effect": "REFLECT_TREATMENT_APPLICATION",
        "tenant_scope": "ORGANIZATION_ISOLATED",
        "authoritative_source": "titan",
        "treatment_application": {
            "application_id": str(operation_id.value),
        },
    }
    if simulate is not None:
        value["simulation_mode"] = simulate
    return IncomingMessageEnvelope(
        message_id=TypedId.new("outbox_message"),
        organization_id=org_id,
        kind=MessageKind.COMMAND,
        contract_type=ERP_TREATMENT_COMMAND_TYPE,
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
        correlation_id=TypedId(
            entity_type="correlation",
            value=TypedId.new("correlation").value,
        ),
        causation_id=TypedId(
            entity_type="domain_event",
            value=TypedId.new("domain_event").value,
        ),
        auth_evaluation_mode=AuthorizationEvaluationMode.SERVICE_AUTHORITY_ONLY,
        purpose="LIVESTOCK_ERP_DELIVERY",
        auth_reference=None,
        payload=CanonicalPayload.from_mapping(
            schema=ERP_OPERATIONAL_INTENT_PAYLOAD_SCHEMA,
            version=1,
            value=value,
        ),
        classification="PROTECTED",
    )


def test_livestock_erp_inbox_handler_returns_operational_effect() -> None:
    outcome, effect_reference, decision_reference = LivestockErpInboxHandler(
        delivery=NeutralOperationalIntentSimulatorAdapter()
    ).handle(_envelope())

    assert outcome is ProcessingOutcome.SUCCESS
    assert effect_reference is not None
    assert decision_reference is not None


def test_livestock_erp_inbox_handler_preserves_external_rejection() -> None:
    outcome, effect_reference, decision_reference = LivestockErpInboxHandler(
        delivery=NeutralOperationalIntentSimulatorAdapter()
    ).handle(_envelope(simulate="external_rejected"))

    assert outcome is ProcessingOutcome.BUSINESS_REJECTION
    assert effect_reference is not None
    assert effect_reference.startswith("external-rejection:")
    assert decision_reference is not None
    assert decision_reference.startswith("ack:EXTERNAL_REJECTED:")


def test_livestock_erp_inbox_handler_distinguishes_duplicate_recovery() -> None:
    outcome, effect_reference, decision_reference = LivestockErpInboxHandler(
        delivery=NeutralOperationalIntentSimulatorAdapter()
    ).handle(_envelope(simulate="duplicate_recovered"))

    assert outcome is ProcessingOutcome.NO_OP
    assert effect_reference is not None
    assert effect_reference.startswith("external-duplicate-recovery:")
    assert decision_reference is not None
    assert decision_reference.startswith("ack:DUPLICATE_RECOVERED:")


def test_livestock_erp_inbox_handler_preserves_unknown_outcome() -> None:
    with pytest.raises(TransientConsumptionError, match="EXTERNAL_OUTCOME_UNKNOWN"):
        LivestockErpInboxHandler(delivery=NeutralOperationalIntentSimulatorAdapter()).handle(
            _envelope(simulate="external_unknown")
        )
