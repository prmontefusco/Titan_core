"""Testes de integração PostgreSQL com RLS para Veterinarian (Passo 8.5 - Titan Livestock)."""

import os
from collections.abc import Iterator
from uuid import uuid4

import pytest
from sqlalchemy import Connection, create_engine, text

from packages.livestock_application.veterinarian_service import VeterinarianService
from packages.livestock_domain.animal import VerificationStatus
from packages.livestock_infrastructure.persistence.veterinarian_repository import (
    TransactionalVeterinarianRepository,
)
from packages.shared_kernel import OrganizationId


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


def test_veterinarian_persistence_and_rls(db_connection: Connection) -> None:
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

    repo_1 = TransactionalVeterinarianRepository(connection=db_connection)
    service_1 = VeterinarianService(repository=repo_1)

    vet_1 = service_1.register_veterinarian(
        organization_id=org_1,
        name="Dr. Carlos Eduardo",
        cpf="111.222.333-44",
        council_number="44332",
        council_state="MG",
    )

    assert vet_1.verification_status == VerificationStatus.DECLARADO

    # Atualiza status e anexa prova
    updated = service_1.attach_evidence(vet_1.veterinarian_id, "evidence:doc-crmv-44332")
    assert updated.verification_status == VerificationStatus.DOCUMENTADO

    # Testar RLS em outra Role
    role_name = f"titan_rls_vet_{uuid4().hex[:12]}"
    quoted_role = f'"{role_name}"'
    db_connection.execute(
        text(
            f"CREATE ROLE {quoted_role} "
            "NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS"
        )
    )
    db_connection.execute(text(f"GRANT USAGE ON SCHEMA core_audit TO {quoted_role}"))
    db_connection.execute(text(f"GRANT ALL ON core_audit.veterinarians TO {quoted_role}"))
    db_connection.execute(text(f"SET LOCAL ROLE {quoted_role}"))

    db_connection.execute(
        text("SELECT set_config('titan.organization_id', :org_id, true)"),
        {"org_id": str(org_2.value)},
    )

    repo_2 = TransactionalVeterinarianRepository(connection=db_connection)
    service_2 = VeterinarianService(repository=repo_2)

    assert service_2.repository.get_by_id(vet_1.veterinarian_id) is None

    db_connection.execute(text("RESET ROLE"))
    db_connection.execute(text(f"DROP OWNED BY {quoted_role}"))
    db_connection.execute(text(f"DROP ROLE {quoted_role}"))
