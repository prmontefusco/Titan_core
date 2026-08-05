"""Contrato neutro do POST-LIV-02A para reflexo operacional outbound."""

from packages.core_domain import CanonicalPayload
from packages.livestock_domain.treatment import TreatmentApplication

ERP_OPERATIONAL_INTENT_CONTRACT_TYPE = "livestock.erp.operational_intent.command"
ERP_OPERATIONAL_INTENT_CONTRACT_VERSION = 1
ERP_OPERATIONAL_INTENT_PAYLOAD_SCHEMA = "livestock.erp.operational_intent_command"
ERP_OPERATIONAL_INTENT_PAYLOAD_VERSION = 1

ERP_OPERATIONAL_INTENT_TYPE = "REGISTER_TREATMENT_OPERATIONAL_REFLECTION"
ERP_SIMULATION_DEFAULT = "external_applied"


def external_operation_id_for_application(application: TreatmentApplication) -> str:
    return f"livestock-treatment-application:{application.application_id.value}"


def build_treatment_operational_intent_payload(
    application: TreatmentApplication,
    *,
    simulation_mode: str = ERP_SIMULATION_DEFAULT,
) -> CanonicalPayload:
    external_operation_id = external_operation_id_for_application(application)
    return CanonicalPayload.from_mapping(
        schema=ERP_OPERATIONAL_INTENT_PAYLOAD_SCHEMA,
        version=ERP_OPERATIONAL_INTENT_PAYLOAD_VERSION,
        value={
            "intent_type": ERP_OPERATIONAL_INTENT_TYPE,
            "contract_profile": "POST_LIV_02A_NEUTRAL_EXTERNAL_CONTRACT",
            "contract_version": ERP_OPERATIONAL_INTENT_CONTRACT_VERSION,
            "external_operation_id": external_operation_id,
            "source_application_id": str(application.application_id.value),
            "requested_effect": "REFLECT_TREATMENT_APPLICATION",
            "tenant_scope": "ORGANIZATION_ISOLATED",
            "authoritative_source": "titan",
            "treatment_application": {
                "application_id": str(application.application_id.value),
                "animal_id": str(application.animal_id.value),
                "medication_batch_id": str(application.medication_batch_id.value),
                "applied_at": application.applied_at.isoformat(),
                "dose": application.dose,
                "prescription_id": (
                    None
                    if application.prescription_id is None
                    else str(application.prescription_id.value)
                ),
                "sanitary_campaign_id": (
                    None
                    if application.sanitary_campaign_id is None
                    else str(application.sanitary_campaign_id.value)
                ),
                "corrects_application_id": (
                    None
                    if application.corrects_application_id is None
                    else str(application.corrects_application_id.value)
                ),
                "evidence_ids": [
                    str(reference.target_id.value) for reference in application.evidence_references
                ],
                "notes_present": bool(application.evidence_notes),
            },
            "delivery_contract": {
                "idempotency_scope": "EXTERNAL_OPERATION_ID",
                "acknowledgement_classes": [
                    "EXTERNAL_RECEIVED",
                    "EXTERNAL_ACCEPTED",
                    "EXTERNAL_APPLIED",
                    "EXTERNAL_REJECTED",
                    "EXTERNAL_UNKNOWN",
                ],
                "duplicate_outcomes": [
                    "DUPLICATE_DETECTED",
                    "DUPLICATE_RECOVERED",
                ],
                "unknown_requires_reconciliation": True,
                "vendor_specific_fields_forbidden": True,
            },
            "non_authority_assertions": {
                "erp_stock_movement_is_not_proof_of_application": True,
                "erp_task_completion_is_not_proof_of_handling": True,
                "broker_acceptance_is_not_external_receipt": True,
                "external_acknowledgement_is_not_sanitary_truth": True,
            },
            "simulation_mode": simulation_mode,
        },
    )
