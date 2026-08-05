from datetime import UTC, datetime

from packages.livestock_application.erp_contract import (
    ERP_OPERATIONAL_INTENT_PAYLOAD_SCHEMA,
    ERP_OPERATIONAL_INTENT_TYPE,
    build_treatment_operational_intent_payload,
    external_operation_id_for_application,
)
from packages.livestock_domain.treatment import TreatmentApplication
from packages.shared_kernel import OrganizationId, TypedId


def test_build_treatment_operational_intent_payload_preserves_neutral_contract() -> None:
    organization_id = OrganizationId.new()
    application = TreatmentApplication(
        application_id=TypedId.new("treatment_application"),
        organization_id=organization_id,
        animal_id=TypedId.new("animal"),
        medication_batch_id=TypedId.new("medication_batch"),
        actor_id=TypedId.new("actor"),
        applied_at=datetime.now(UTC),
        dose="1 mL",
    )

    payload = build_treatment_operational_intent_payload(application)

    assert payload.schema == ERP_OPERATIONAL_INTENT_PAYLOAD_SCHEMA
    assert ERP_OPERATIONAL_INTENT_TYPE.encode() in payload.canonical_bytes
    assert external_operation_id_for_application(application).encode() in payload.canonical_bytes
    assert b"vendor_specific_fields_forbidden" in payload.canonical_bytes
    assert b"unknown_requires_reconciliation" in payload.canonical_bytes
