"""Testes de integração PostgreSQL com RLS para Movement (Passo 8.3 - Titan Livestock)."""

import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import Connection, create_engine, text

from packages.livestock_application.movement_service import MovementService
from packages.livestock_domain.movement import StayStatus
from packages.livestock_infrastructure.persistence.animal_repository import (
    TransactionalAnimalRepository,
)
from packages.livestock_infrastructure.persistence.movement_repository import (
    TransactionalAnimalMovementRepository,
    TransactionalPropertyStayRepository,
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


def test_movement_persistence_and_rls(db_connection: Connection) -> None:
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

    prop_id_orig = TypedId.new("rural_property")
    prop_id_dest = TypedId.new("rural_property")
    animal_id = TypedId.new("animal")

    # Inserções SQL diretas de base
    db_connection.execute(
        text(
            """
            INSERT INTO core_audit.rural_properties (
                property_id, record_owner_organization_id, code, name,
                municipality, state_code, created_at
            ) VALUES
                (:p1, :org, 'P-ORIGEM', 'Fazenda Origem', 'Ribeirão Preto', 'SP', NOW()),
                (:p2, :org, 'P-DESTINO', 'Fazenda Destino', 'Sertãozinho', 'SP', NOW())

            """
        ),
        {"p1": prop_id_orig.value, "p2": prop_id_dest.value, "org": org_1.value},
    )
    db_connection.execute(
        text(
            """
            INSERT INTO core_audit.animals (
                animal_id, record_owner_organization_id, birth_property_id, sex, breed, created_at
            ) VALUES (
                :aid, :org, :p1, 'MALE', 'Nelore', NOW()
            )
            """
        ),
        {"aid": animal_id.value, "org": org_1.value, "p1": prop_id_orig.value},
    )

    m_repo_1 = TransactionalAnimalMovementRepository(connection=db_connection)
    stay_repo_1 = TransactionalPropertyStayRepository(connection=db_connection)
    anim_repo_1 = TransactionalAnimalRepository(connection=db_connection)
    prop_repo_1 = TransactionalRuralPropertyRepository(connection=db_connection)

    service_1 = MovementService(
        movement_repository=m_repo_1,
        stay_repository=stay_repo_1,
        animal_repository=anim_repo_1,
        property_repository=prop_repo_1,
    )

    # 1. Registra movimentação
    m_time = datetime.now(UTC) - timedelta(hours=3)
    movement_1 = service_1.register_movement(
        organization_id=org_1,
        origin_property_id=prop_id_orig,
        destination_property_id=prop_id_dest,
        movement_time=m_time,
        animal_ids=(animal_id,),
        reason="Manejo sanitário",
    )

    saved_m = service_1.movement_repository.get_by_id(movement_1.movement_id)
    assert saved_m is not None
    assert saved_m.origin_property_id == prop_id_orig
    assert saved_m.destination_property_id == prop_id_dest

    active_stay = service_1.get_active_stay(animal_id)
    assert active_stay is not None
    assert active_stay.property_id == prop_id_dest
    assert active_stay.status == StayStatus.ACTIVE

    # 2. RLS Isolation: role sem BYPASSRLS em outra Organization
    role_name = f"titan_rls_mov_{uuid4().hex[:12]}"
    quoted_role = f'"{role_name}"'
    db_connection.execute(
        text(
            f"CREATE ROLE {quoted_role} "
            "NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS"
        )
    )
    db_connection.execute(text(f"GRANT USAGE ON SCHEMA core_audit TO {quoted_role}"))
    db_connection.execute(text(f"GRANT ALL ON core_audit.animal_movements TO {quoted_role}"))
    db_connection.execute(text(f"GRANT ALL ON core_audit.animal_movement_items TO {quoted_role}"))
    db_connection.execute(text(f"GRANT ALL ON core_audit.property_stays TO {quoted_role}"))
    db_connection.execute(text(f"SET LOCAL ROLE {quoted_role}"))

    db_connection.execute(
        text("SELECT set_config('titan.organization_id', :org_id, true)"),
        {"org_id": str(org_2.value)},
    )

    m_repo_2 = TransactionalAnimalMovementRepository(connection=db_connection)
    stay_repo_2 = TransactionalPropertyStayRepository(connection=db_connection)
    anim_repo_2 = TransactionalAnimalRepository(connection=db_connection)
    prop_repo_2 = TransactionalRuralPropertyRepository(connection=db_connection)

    service_2 = MovementService(
        movement_repository=m_repo_2,
        stay_repository=stay_repo_2,
        animal_repository=anim_repo_2,
        property_repository=prop_repo_2,
    )

    # RLS impede org_2 de enxergar a movimentação ou a estada da org_1
    assert service_2.movement_repository.get_by_id(movement_1.movement_id) is None
    assert service_2.get_active_stay(animal_id) is None

    db_connection.execute(text("RESET ROLE"))
    db_connection.execute(text(f"DROP OWNED BY {quoted_role}"))
    db_connection.execute(text(f"DROP ROLE {quoted_role}"))
