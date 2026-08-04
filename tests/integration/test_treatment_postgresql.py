"""Testes de integração PostgreSQL com RLS para TreatmentApplication (Passo 9.3)."""

import os
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import Connection, create_engine, select, text
from sqlalchemy.exc import IntegrityError

from packages.core_application import OutboxMessage
from packages.core_infrastructure.persistence.outbox import (
    TransactionalOutboxMessageWriter,
    outbox_messages_table,
)
from packages.livestock_application.erp_contract import ERP_OPERATIONAL_INTENT_CONTRACT_TYPE
from packages.livestock_application.erp_outbox import LivestockErpOutboxService
from packages.livestock_application.medication_service import MedicationBatchService
from packages.livestock_application.treatment_service import TreatmentApplicationService
from packages.livestock_infrastructure.persistence.animal_repository import (
    TransactionalAnimalRepository,
)
from packages.livestock_infrastructure.persistence.medication_repository import (
    TransactionalMedicationBatchRepository,
    TransactionalMedicationRepository,
    TransactionalPrescriptionRepository,
)
from packages.livestock_infrastructure.persistence.treatment_repository import (
    TransactionalTreatmentApplicationRepository,
)
from packages.shared_kernel import OrganizationId, TypedId
from tests.livestock_support import in_memory_recorder, operation_context


@pytest.fixture
def db_connection() -> Iterator[Connection]:
    db_url = os.getenv(
        "TITAN_DATABASE_URL",
        "postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan",
    )
    engine = create_engine(db_url, pool_pre_ping=True)
    with engine.connect() as conn:
        with conn.begin():
            yield conn


def test_treatment_application_correction_and_rls(db_connection: Connection) -> None:
    org_1 = OrganizationId(uuid4())
    org_2 = OrganizationId(uuid4())
    db_connection.execute(
        text(
            """
            INSERT INTO core_identity.organizations (organization_id, record_owner_organization_id)
            VALUES (:org1, :org1), (:org2, :org2)
            """
        ),
        {"org1": org_1.value, "org2": org_2.value},
    )
    db_connection.execute(
        text("SELECT set_config('titan.organization_id', :org_id, true)"),
        {"org_id": str(org_1.value)},
    )

    # Pré-requisitos: propriedade, animal e medicamento por SQL direto.
    prop_id = TypedId.new("rural_property")
    animal_id = TypedId.new("animal")
    med_id = TypedId.new("medication")
    db_connection.execute(
        text(
            """
            INSERT INTO core_audit.rural_properties (
                property_id, record_owner_organization_id, code, name,
                municipality, state_code, created_at
            ) VALUES (:p, :org, 'P-01', 'Fazenda 1', 'RP', 'SP', NOW())
            """
        ),
        {"p": prop_id.value, "org": org_1.value},
    )
    db_connection.execute(
        text(
            """
            INSERT INTO core_audit.animals (
                animal_id, record_owner_organization_id, birth_property_id, sex, created_at
            ) VALUES (:a, :org, :p, 'FEMALE', NOW())
            """
        ),
        {"a": animal_id.value, "org": org_1.value, "p": prop_id.value},
    )
    db_connection.execute(
        text(
            """
            INSERT INTO core_audit.medications (
                medication_id, record_owner_organization_id, trade_name,
                active_ingredient, manufacturer, withdrawal_period_days,
                product_class, created_at
            ) VALUES (
                :m, :org, 'Ivomec', 'Ivermectina', 'Boehringer', 122,
                'PHARMACOLOGICAL', NOW()
            )
            """
        ),
        {"m": med_id.value, "org": org_1.value},
    )

    recorder, _ = in_memory_recorder()
    context_1 = operation_context(org_1)
    batch = MedicationBatchService(
        batch_repository=TransactionalMedicationBatchRepository(connection=db_connection),
        medication_repository=TransactionalMedicationRepository(connection=db_connection),
        recorder=recorder,
    ).register_batch(
        context=context_1,
        medication_id=med_id,
        batch_number="LOTE-2026-001",
        expiry_date=datetime.now(UTC) + timedelta(days=365),
    )

    service = TreatmentApplicationService(
        application_repository=TransactionalTreatmentApplicationRepository(
            connection=db_connection
        ),
        animal_repository=TransactionalAnimalRepository(connection=db_connection),
        batch_repository=TransactionalMedicationBatchRepository(connection=db_connection),
        prescription_repository=TransactionalPrescriptionRepository(connection=db_connection),
        recorder=recorder,
    )

    original = service.register_application(
        context=context_1,
        animal_id=animal_id,
        medication_batch_id=batch.batch_id,
        applied_at=datetime.now(UTC) - timedelta(hours=2),
        dose="1 mL",
        evidence_notes=("foto no celular do João",),
    )
    correction = service.correct_application(
        context=context_1,
        original_application_id=original.application_id,
        applied_at=datetime.now(UTC) - timedelta(hours=1),
        dose="2 mL",
    )

    repo = TransactionalTreatmentApplicationRepository(connection=db_connection)
    # Append-only: original preservado e correção aponta para ele.
    recarregado = repo.get_by_id(original.application_id)
    assert recarregado is not None
    assert recarregado.dose == "1 mL"
    assert recarregado.evidence_notes == ("foto no celular do João",)
    assert repo.get_by_id(correction.application_id).corrects_application_id == (  # type: ignore[union-attr]
        original.application_id
    )

    # Rastreabilidade por lote (base do recall): as duas aplicações do lote.
    do_lote = repo.list_by_batch(org_1, batch.batch_id)
    assert len(do_lote) == 2

    # RLS: role sem BYPASSRLS na outra Organization não enxerga aplicação alguma.
    role_name = f"titan_rls_treat_{uuid4().hex[:12]}"
    quoted_role = f'"{role_name}"'
    db_connection.execute(
        text(
            f"CREATE ROLE {quoted_role} "
            "NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS"
        )
    )
    db_connection.execute(text(f"GRANT USAGE ON SCHEMA core_audit TO {quoted_role}"))
    db_connection.execute(
        text(f"GRANT SELECT ON core_audit.treatment_applications TO {quoted_role}")
    )
    db_connection.execute(text(f"SET LOCAL ROLE {quoted_role}"))
    db_connection.execute(
        text("SELECT set_config('titan.organization_id', :org_id, true)"),
        {"org_id": str(org_2.value)},
    )

    repo_2 = TransactionalTreatmentApplicationRepository(connection=db_connection)
    assert repo_2.get_by_id(original.application_id) is None
    assert repo_2.list_by_batch(org_2, batch.batch_id) == []

    db_connection.execute(text("RESET ROLE"))
    db_connection.execute(text(f"DROP OWNED BY {quoted_role}"))
    db_connection.execute(text(f"DROP ROLE {quoted_role}"))


def test_treatment_application_persists_erp_outbox_command_in_same_transaction(
    db_connection: Connection,
) -> None:
    org_id = OrganizationId(uuid4())
    db_connection.execute(
        text(
            """
            INSERT INTO core_identity.organizations (organization_id, record_owner_organization_id)
            VALUES (:org, :org)
            """
        ),
        {"org": org_id.value},
    )
    db_connection.execute(
        text("SELECT set_config('titan.organization_id', :org_id, true)"),
        {"org_id": str(org_id.value)},
    )

    prop_id = TypedId.new("rural_property")
    animal_id = TypedId.new("animal")
    med_id = TypedId.new("medication")
    db_connection.execute(
        text(
            """
            INSERT INTO core_audit.rural_properties (
                property_id, record_owner_organization_id, code, name,
                municipality, state_code, created_at
            ) VALUES (:p, :org, 'P-01', 'Fazenda 1', 'RP', 'SP', NOW())
            """
        ),
        {"p": prop_id.value, "org": org_id.value},
    )
    db_connection.execute(
        text(
            """
            INSERT INTO core_audit.animals (
                animal_id, record_owner_organization_id, birth_property_id, sex, created_at
            ) VALUES (:a, :org, :p, 'FEMALE', NOW())
            """
        ),
        {"a": animal_id.value, "org": org_id.value, "p": prop_id.value},
    )
    db_connection.execute(
        text(
            """
            INSERT INTO core_audit.medications (
                medication_id, record_owner_organization_id, trade_name,
                active_ingredient, manufacturer, withdrawal_period_days,
                product_class, created_at
            ) VALUES (
                :m, :org, 'Ivomec', 'Ivermectina', 'Boehringer', 122,
                'PHARMACOLOGICAL', NOW()
            )
            """
        ),
        {"m": med_id.value, "org": org_id.value},
    )

    recorder, _ = in_memory_recorder()
    context = operation_context(org_id)
    batch = MedicationBatchService(
        batch_repository=TransactionalMedicationBatchRepository(connection=db_connection),
        medication_repository=TransactionalMedicationRepository(connection=db_connection),
        recorder=recorder,
    ).register_batch(
        context=context,
        medication_id=med_id,
        batch_number="LOTE-2026-OUTBOX",
        expiry_date=datetime.now(UTC) + timedelta(days=365),
    )

    service = TreatmentApplicationService(
        application_repository=TransactionalTreatmentApplicationRepository(
            connection=db_connection
        ),
        animal_repository=TransactionalAnimalRepository(connection=db_connection),
        batch_repository=TransactionalMedicationBatchRepository(connection=db_connection),
        prescription_repository=TransactionalPrescriptionRepository(connection=db_connection),
        recorder=recorder,
        erp_outbox_service=LivestockErpOutboxService(
            writer=TransactionalOutboxMessageWriter(connection=db_connection)
        ),
    )

    application = service.register_application(
        context=context,
        animal_id=animal_id,
        medication_batch_id=batch.batch_id,
        applied_at=datetime.now(UTC) - timedelta(hours=1),
        dose="1 mL",
    )

    rows = db_connection.execute(
        select(outbox_messages_table).where(
            outbox_messages_table.c.record_owner_organization_id == org_id.value,
            outbox_messages_table.c.contract_type == ERP_OPERATIONAL_INTENT_CONTRACT_TYPE,
        )
    ).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.kind == "COMMAND"
    assert row.causation_id is not None
    assert str(application.application_id.value).encode() in bytes(row.payload_canonical_bytes)


def test_outbox_failure_rolls_back_treatment_application(
    db_connection: Connection,
) -> None:
    org_id = OrganizationId(uuid4())
    db_connection.execute(
        text(
            """
            INSERT INTO core_identity.organizations (organization_id, record_owner_organization_id)
            VALUES (:org, :org)
            """
        ),
        {"org": org_id.value},
    )
    db_connection.execute(
        text("SELECT set_config('titan.organization_id', :org_id, true)"),
        {"org_id": str(org_id.value)},
    )

    prop_id = TypedId.new("rural_property")
    animal_id = TypedId.new("animal")
    med_id = TypedId.new("medication")
    db_connection.execute(
        text(
            """
            INSERT INTO core_audit.rural_properties (
                property_id, record_owner_organization_id, code, name,
                municipality, state_code, created_at
            ) VALUES (:p, :org, 'P-01', 'Fazenda 1', 'RP', 'SP', NOW())
            """
        ),
        {"p": prop_id.value, "org": org_id.value},
    )
    db_connection.execute(
        text(
            """
            INSERT INTO core_audit.animals (
                animal_id, record_owner_organization_id, birth_property_id, sex, created_at
            ) VALUES (:a, :org, :p, 'FEMALE', NOW())
            """
        ),
        {"a": animal_id.value, "org": org_id.value, "p": prop_id.value},
    )
    db_connection.execute(
        text(
            """
            INSERT INTO core_audit.medications (
                medication_id, record_owner_organization_id, trade_name,
                active_ingredient, manufacturer, withdrawal_period_days,
                product_class, created_at
            ) VALUES (
                :m, :org, 'Ivomec', 'Ivermectina', 'Boehringer', 122,
                'PHARMACOLOGICAL', NOW()
            )
            """
        ),
        {"m": med_id.value, "org": org_id.value},
    )

    recorder, _ = in_memory_recorder()
    context = operation_context(org_id)
    batch = MedicationBatchService(
        batch_repository=TransactionalMedicationBatchRepository(connection=db_connection),
        medication_repository=TransactionalMedicationRepository(connection=db_connection),
        recorder=recorder,
    ).register_batch(
        context=context,
        medication_id=med_id,
        batch_number="LOTE-2026-ROLLBACK",
        expiry_date=datetime.now(UTC) + timedelta(days=365),
    )

    duplicate_message_id = TypedId.new("outbox_message")
    db_connection.execute(
        outbox_messages_table.insert().values(
            message_id=duplicate_message_id.value,
            record_owner_organization_id=org_id.value,
            kind="COMMAND",
            contract_type="seed.duplicate",
            contract_version=1,
            actor_type="actor",
            actor_id=context.actor_reference.target_id.value,
            producer_type=context.source_reference.target_id.entity_type,
            producer_id=context.source_reference.target_id.value,
            occurred_at=datetime.now(UTC),
            recorded_at=datetime.now(UTC),
            correlation_id=context.correlation_id.value,
            causation_id=TypedId.new("domain_event").value,
            idempotency_key="seed-duplicate",
            payload_schema="seed.duplicate",
            payload_version=1,
            payload_canonical_bytes=b"{}",
            classification="PROTECTED",
            status="PENDENTE",
        )
    )

    class DuplicateIdWriter(TransactionalOutboxMessageWriter):
        def append(self, message: OutboxMessage) -> None:
            super().append(replace(message, message_id=duplicate_message_id))

    service = TreatmentApplicationService(
        application_repository=TransactionalTreatmentApplicationRepository(
            connection=db_connection
        ),
        animal_repository=TransactionalAnimalRepository(connection=db_connection),
        batch_repository=TransactionalMedicationBatchRepository(connection=db_connection),
        prescription_repository=TransactionalPrescriptionRepository(connection=db_connection),
        recorder=recorder,
        erp_outbox_service=LivestockErpOutboxService(
            writer=DuplicateIdWriter(connection=db_connection)
        ),
    )

    with pytest.raises(IntegrityError):
        service.register_application(
            context=context,
            animal_id=animal_id,
            medication_batch_id=batch.batch_id,
            applied_at=datetime.now(UTC) - timedelta(minutes=30),
            dose="1 mL",
        )

    repo = TransactionalTreatmentApplicationRepository(connection=db_connection)
    assert repo.list_by_batch(org_id, batch.batch_id) == []
