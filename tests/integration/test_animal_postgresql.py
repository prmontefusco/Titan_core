"""Testes de integração PostgreSQL com RLS para Animal (Passo 8.2 - Titan Livestock)."""

import os
from collections.abc import Iterator
from uuid import uuid4

import pytest
from sqlalchemy import Connection, create_engine, text

from packages.livestock_application.animal_service import AnimalService
from packages.livestock_domain.animal import AnimalSex, IdentifierType
from packages.livestock_infrastructure.persistence.animal_repository import (
    TransactionalAnimalRepository,
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


def test_animal_persistence_and_rls(db_connection: Connection) -> None:
    org_1 = OrganizationId(uuid4())
    org_2 = OrganizationId(uuid4())

    # Cadastra organizações
    db_connection.execute(
        text(
            """
            INSERT INTO core_identity.organizations (organization_id, record_owner_organization_id)
            VALUES (:org1, :org1), (:org2, :org2)
            """
        ),
        {"org1": org_1.value, "org2": org_2.value},
    )

    # 1. Configura RLS para org_1 e cadastra propriedade de nascimento
    db_connection.execute(
        text("SELECT set_config('titan.organization_id', :org_id, true)"),
        {"org_id": str(org_1.value)},
    )

    # Usa inserção SQL direta para a propriedade de nascimento
    prop_id_1 = TypedId.new("rural_property")
    db_connection.execute(
        text(
            """
            INSERT INTO core_audit.rural_properties (
                property_id, record_owner_organization_id, code, name,
                municipality, state_code, created_at
            ) VALUES (
                :id, :org_id, 'PROP-01', 'Fazenda Origem', 'Ribeirão Preto', 'SP', NOW()
            )
            """
        ),
        {"id": prop_id_1.value, "org_id": org_1.value},
    )

    animal_repo_1 = TransactionalAnimalRepository(connection=db_connection)
    animal_service_1 = AnimalService(repository=animal_repo_1)

    # 2. Cadastra animal com SISBOV
    animal_1 = animal_service_1.register_animal(
        organization_id=org_1,
        birth_property_id=prop_id_1,
        sex=AnimalSex.MALE,
        breed="Nelore",
        initial_identifier_type=IdentifierType.OFFICIAL_SISBOV,
        initial_identifier_value="BR-SISBOV-9988",
    )

    saved_animal = animal_service_1.get_animal(animal_1.animal_id)
    assert saved_animal is not None
    assert saved_animal.breed == "Nelore"
    assert len(saved_animal.identifiers) == 1
    assert saved_animal.identifiers[0].identifier_value == "BR-SISBOV-9988"

    # 3. Anexa brinco de manejo e atualiza
    updated_animal = animal_service_1.attach_identifier(
        animal_1.animal_id, IdentifierType.EAR_TAG, "TAG-101"
    )
    assert len(updated_animal.identifiers) == 2

    # 4. RLS Isolation: role sem BYPASSRLS em outra Organization
    role_name = f"titan_rls_anim_{uuid4().hex[:12]}"
    quoted_role = f'"{role_name}"'
    db_connection.execute(
        text(
            f"CREATE ROLE {quoted_role} "
            "NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS"
        )
    )

    db_connection.execute(text(f"GRANT USAGE ON SCHEMA core_audit TO {quoted_role}"))
    db_connection.execute(text(f"GRANT ALL ON core_audit.animals TO {quoted_role}"))
    db_connection.execute(text(f"GRANT ALL ON core_audit.animal_identifiers TO {quoted_role}"))
    db_connection.execute(text(f"SET LOCAL ROLE {quoted_role}"))

    db_connection.execute(
        text("SELECT set_config('titan.organization_id', :org_id, true)"),
        {"org_id": str(org_2.value)},
    )

    animal_repo_2 = TransactionalAnimalRepository(connection=db_connection)
    animal_service_2 = AnimalService(repository=animal_repo_2)

    # RLS impede org_2 de enxergar o animal da org_1
    assert animal_service_2.get_animal(animal_1.animal_id) is None
    assert (
        animal_service_2.find_by_identifier(org_2, IdentifierType.OFFICIAL_SISBOV, "BR-SISBOV-9988")
        is None
    )

    db_connection.execute(text("RESET ROLE"))
    db_connection.execute(text(f"DROP OWNED BY {quoted_role}"))
    db_connection.execute(text(f"DROP ROLE {quoted_role}"))
