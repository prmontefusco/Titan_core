"""Teste end-to-end do ciclo operacional minimo do LIV-C09."""

import os
from datetime import UTC, datetime

from sqlalchemy import create_engine, text

from packages.core_application import (
    AuthorizationEvaluationMode,
    DeliveryHandlingOutcome,
    IncomingMessageEnvelope,
    MessageKind,
    ProcessingOutcome,
)
from packages.core_domain import CanonicalPayload
from packages.core_infrastructure.persistence.inbox import TransactionalInboxRepository
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


def test_worker_e2e_flow() -> None:
    db_url = os.getenv(
        "TITAN_DATABASE_URL",
        "postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan",
    )
    engine = create_engine(db_url, pool_pre_ping=True)

    org_id = OrganizationId.new()
    msg_id = TypedId.new("outbox_message")

    with engine.connect() as conn:
        with conn.begin():
            conn.execute(
                text(
                    """
                    INSERT INTO core_identity.organizations
                    (organization_id, record_owner_organization_id)
                    VALUES (:org_id, :org_id)
                    """
                ),
                {"org_id": org_id.value},
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
            envelope = IncomingMessageEnvelope(
                message_id=msg_id,
                organization_id=org_id,
                kind=MessageKind.COMMAND,
                contract_type=ERP_TREATMENT_COMMAND_TYPE,
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
                correlation_id=TypedId(
                    entity_type="correlation", value=TypedId.new("correlation").value
                ),
                causation_id=TypedId(
                    entity_type="domain_event", value=TypedId.new("domain_event").value
                ),
                auth_evaluation_mode=AuthorizationEvaluationMode.SERVICE_AUTHORITY_ONLY,
                purpose="LIV_C09_E2E",
                auth_reference=None,
                payload=CanonicalPayload.from_mapping(
                    schema=ERP_OPERATIONAL_INTENT_PAYLOAD_SCHEMA,
                    version=1,
                    value={
                        "intent_type": ERP_OPERATIONAL_INTENT_TYPE,
                        "contract_profile": "POST_LIV_02A_NEUTRAL_EXTERNAL_CONTRACT",
                        "contract_version": 1,
                        "external_operation_id": (
                            f"livestock-treatment-application:"
                            f"{TypedId.new('treatment_application').value}"
                        ),
                        "source_application_id": str(TypedId.new("treatment_application").value),
                        "requested_effect": "REFLECT_TREATMENT_APPLICATION",
                        "tenant_scope": "ORGANIZATION_ISOLATED",
                        "authoritative_source": "titan",
                        "treatment_application": {
                            "application_id": str(TypedId.new("treatment_application").value),
                        },
                    },
                ),
                classification="PROTECTED",
            )

            repo = TransactionalInboxRepository(connection=conn, consumer_id="e2e_worker")
            receipt = repo.process_message(
                envelope=envelope,
                handler=LivestockErpInboxHandler(
                    delivery=NeutralOperationalIntentSimulatorAdapter()
                ),
            )

            assert receipt.handling_outcome == DeliveryHandlingOutcome.PROCESSED
            assert receipt.processing_outcome == ProcessingOutcome.SUCCESS
            assert receipt.effect_reference is not None
