"""Testes de integração PostgreSQL com RLS para LivestockLot (Passo 8.4 - Titan Livestock)."""

import os
from collections.abc import Iterator
from uuid import uuid4

import pytest
from sqlalchemy import Connection, create_engine, text

from packages.livestock_application.lot_service import LotService
from packages.livestock_domain.lot import LotType
from packages.livestock_infrastructure.persistence.animal_repository import (
    TransactionalAnimalRepository,
)
from packages.livestock_infrastructure.persistence.lot_repository import (
    TransactionalLivestockLotRepository,
    TransactionalLotMembershipRepository,
)
from packages.livestock_infrastructure.persistence.property_repository import (
    TransactionalRuralPropertyRepository,
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


def test_lot_persistence_and_rls(db_connection: Connection) -> None:
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

    # Configura RLS para Org 1
    db_connection.execute(
        text("SELECT set_config('titan.organization_id', :org_id, true)"),
        {"org_id": str(org_1.value)},
    )

    prop_id = TypedId.new("rural_property")
    animal_id = TypedId.new("animal")

    # SQLs diretos de carga inicial
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
            ) VALUES (:aid, :org, :p, 'MALE', NOW())
            """
        ),
        {"aid": animal_id.value, "org": org_1.value, "p": prop_id.value},
    )

    lot_repo_1 = TransactionalLivestockLotRepository(connection=db_connection)
    mem_repo_1 = TransactionalLotMembershipRepository(connection=db_connection)
    anim_repo_1 = TransactionalAnimalRepository(connection=db_connection)
    prop_repo_1 = TransactionalRuralPropertyRepository(connection=db_connection)

    service_1 = LotService(
        lot_repository=lot_repo_1,
        membership_repository=mem_repo_1,
        animal_repository=anim_repo_1,
        property_repository=prop_repo_1,
    )

    # 1. Cria lote e associa animal
    lot_1 = service_1.create_lot(
        organization_id=org_1,
        property_id=prop_id,
        code="LOTE-01",
        name="Lote Principal",
        lot_type=LotType.OPERATIONAL,
    )

    m_1 = service_1.add_animal_to_lot(lot_1.lot_id, animal_id)
    assert m_1.animal_id == animal_id

    composition = service_1.get_lot_composition(lot_1.lot_id)
    assert len(composition) == 1

    # 2. RLS Isolation: role sem BYPASSRLS em outra Organization
    role_name = f"titan_rls_lot_{uuid4().hex[:12]}"
    quoted_role = f'"{role_name}"'
    db_connection.execute(
        text(
            f"CREATE ROLE {quoted_role} "
            "NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS"
        )
    )
    db_connection.execute(text(f"GRANT USAGE ON SCHEMA core_audit TO {quoted_role}"))
    db_connection.execute(text(f"GRANT ALL ON core_audit.livestock_lots TO {quoted_role}"))
    db_connection.execute(text(f"GRANT ALL ON core_audit.lot_memberships TO {quoted_role}"))
    db_connection.execute(text(f"SET LOCAL ROLE {quoted_role}"))

    db_connection.execute(
        text("SELECT set_config('titan.organization_id', :org_id, true)"),
        {"org_id": str(org_2.value)},
    )

    lot_repo_2 = TransactionalLivestockLotRepository(connection=db_connection)
    mem_repo_2 = TransactionalLotMembershipRepository(connection=db_connection)
    anim_repo_2 = TransactionalAnimalRepository(connection=db_connection)
    prop_repo_2 = TransactionalRuralPropertyRepository(connection=db_connection)

    service_2 = LotService(
        lot_repository=lot_repo_2,
        membership_repository=mem_repo_2,
        animal_repository=anim_repo_2,
        property_repository=prop_repo_2,
    )

    # RLS impede org_2 de enxergar o lote da org_1
    assert service_2.lot_repository.get_by_id(lot_1.lot_id) is None
    assert len(service_2.get_lot_composition(lot_1.lot_id)) == 0

    db_connection.execute(text("RESET ROLE"))
    db_connection.execute(text(f"DROP OWNED BY {quoted_role}"))
    db_connection.execute(text(f"DROP ROLE {quoted_role}"))
