"""Testes de integração PostgreSQL com RLS para Medication (Passo 9.1 - Titan Livestock)."""

import os
from collections.abc import Iterator
from uuid import uuid4

import pytest
from sqlalchemy import Connection, create_engine, text

from packages.livestock_application.medication_service import MedicationService
from packages.livestock_domain.prescription import PrescriptionTargetType
from packages.livestock_infrastructure.persistence.medication_repository import (
    TransactionalMedicationRepository,
    TransactionalPrescriptionRepository,
)
from packages.livestock_infrastructure.persistence.property_repository import (
    TransactionalRuralPropertyRepository,
)
from packages.livestock_infrastructure.persistence.veterinarian_repository import (
    TransactionalVeterinarianRepository,
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


def test_medication_and_prescription_persistence_and_rls(
    db_connection: Connection,
) -> None:
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

    prop_id = TypedId.new("rural_property")
    vet_id = TypedId.new("veterinarian")
    animal_id = TypedId.new("animal")

    # SQLs diretos para carga de propriedade e veterinario
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
            INSERT INTO core_audit.veterinarians (
                veterinarian_id, record_owner_organization_id, name, cpf,
                council_number, council_state, verification_status, created_at
            ) VALUES (
                :v, :org, 'Dr. Silva', '11122233344', '12345', 'SP',
                'VERIFICADO_EM_FONTE', NOW()
            )

            """
        ),
        {"v": vet_id.value, "org": org_1.value},
    )

    med_repo_1 = TransactionalMedicationRepository(connection=db_connection)
    presc_repo_1 = TransactionalPrescriptionRepository(connection=db_connection)
    vet_repo_1 = TransactionalVeterinarianRepository(connection=db_connection)
    prop_repo_1 = TransactionalRuralPropertyRepository(connection=db_connection)

    service_1 = MedicationService(
        medication_repository=med_repo_1,
        prescription_repository=presc_repo_1,
        veterinarian_repository=vet_repo_1,
        property_repository=prop_repo_1,
    )

    med_1 = service_1.register_medication(
        organization_id=org_1,
        trade_name="Ivomec Gold",
        active_ingredient="Ivermectina",
        manufacturer="Boehringer",
        withdrawal_period_days=122,
    )

    presc_1 = service_1.issue_prescription(
        organization_id=org_1,
        veterinarian_id=vet_id,
        medication_id=med_1.medication_id,
        property_id=prop_id,
        dosage="1 mL / 50 kg",
        administration_route="SUBCUTANEOUS",
        target_type=PrescriptionTargetType.ANIMAL,
        target_ids=(animal_id,),
        reason="Tratamento preventivo",
    )

    assert presc_1.prescription_id is not None

    # Testar RLS em outra Role
    role_name = f"titan_rls_med_{uuid4().hex[:12]}"
    quoted_role = f'"{role_name}"'
    db_connection.execute(
        text(
            f"CREATE ROLE {quoted_role} "
            "NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS"
        )
    )
    db_connection.execute(text(f"GRANT USAGE ON SCHEMA core_audit TO {quoted_role}"))
    db_connection.execute(text(f"GRANT ALL ON core_audit.medications TO {quoted_role}"))
    db_connection.execute(text(f"GRANT ALL ON core_audit.prescriptions TO {quoted_role}"))
    db_connection.execute(text(f"GRANT ALL ON core_audit.prescription_targets TO {quoted_role}"))
    db_connection.execute(text(f"SET LOCAL ROLE {quoted_role}"))

    db_connection.execute(
        text("SELECT set_config('titan.organization_id', :org_id, true)"),
        {"org_id": str(org_2.value)},
    )

    med_repo_2 = TransactionalMedicationRepository(connection=db_connection)
    presc_repo_2 = TransactionalPrescriptionRepository(connection=db_connection)
    vet_repo_2 = TransactionalVeterinarianRepository(connection=db_connection)
    prop_repo_2 = TransactionalRuralPropertyRepository(connection=db_connection)

    service_2 = MedicationService(
        medication_repository=med_repo_2,
        prescription_repository=presc_repo_2,
        veterinarian_repository=vet_repo_2,
        property_repository=prop_repo_2,
    )

    assert service_2.medication_repository.get_by_id(med_1.medication_id) is None
    assert service_2.prescription_repository.get_by_id(presc_1.prescription_id) is None

    db_connection.execute(text("RESET ROLE"))
    db_connection.execute(text(f"DROP OWNED BY {quoted_role}"))
    db_connection.execute(text(f"DROP ROLE {quoted_role}"))
