"""Testes de integração PostgreSQL com RLS para TreatmentApplication (Passo 9.3)."""

import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import Connection, create_engine, text

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
                active_ingredient, manufacturer, withdrawal_period_days, created_at
            ) VALUES (:m, :org, 'Ivomec', 'Ivermectina', 'Boehringer', 122, NOW())
            """
        ),
        {"m": med_id.value, "org": org_1.value},
    )

    batch = MedicationBatchService(
        batch_repository=TransactionalMedicationBatchRepository(connection=db_connection),
        medication_repository=TransactionalMedicationRepository(connection=db_connection),
    ).register_batch(
        organization_id=org_1,
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
    )

    original = service.register_application(
        organization_id=org_1,
        animal_id=animal_id,
        medication_batch_id=batch.batch_id,
        actor_id=TypedId.new("actor"),
        applied_at=datetime.now(UTC) - timedelta(hours=2),
        dose="1 mL",
        evidence_references=("evidence:foto-1",),
    )
    correction = service.correct_application(
        organization_id=org_1,
        original_application_id=original.application_id,
        actor_id=TypedId.new("actor"),
        applied_at=datetime.now(UTC) - timedelta(hours=1),
        dose="2 mL",
    )

    repo = TransactionalTreatmentApplicationRepository(connection=db_connection)
    # Append-only: original preservado e correção aponta para ele.
    recarregado = repo.get_by_id(original.application_id)
    assert recarregado is not None
    assert recarregado.dose == "1 mL"
    assert recarregado.evidence_references == ("evidence:foto-1",)
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
