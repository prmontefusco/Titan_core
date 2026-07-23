"""Teste de integração E2E da vertical Titan Livestock (Passo 8.6 - Encerramento do Marco 8)."""

import os
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import Connection, create_engine, text

from packages.livestock_application.animal_service import AnimalService
from packages.livestock_application.fact_provider import LivestockFactProvider
from packages.livestock_application.lot_service import LotService
from packages.livestock_application.movement_service import MovementService
from packages.livestock_application.property_service import RuralPropertyService
from packages.livestock_application.veterinarian_service import VeterinarianService
from packages.livestock_domain.animal import AnimalSex, IdentifierType, VerificationStatus
from packages.livestock_domain.lot import LotType
from packages.livestock_domain.movement import StayStatus
from packages.livestock_infrastructure.persistence.animal_repository import (
    TransactionalAnimalRepository,
)
from packages.livestock_infrastructure.persistence.lot_repository import (
    TransactionalLivestockLotRepository,
    TransactionalLotMembershipRepository,
)
from packages.livestock_infrastructure.persistence.movement_repository import (
    TransactionalAnimalMovementRepository,
    TransactionalPropertyStayRepository,
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


def test_livestock_vertical_full_e2e_flow(db_connection: Connection) -> None:
    org_1 = OrganizationId(uuid4())
    org_2 = OrganizationId(uuid4())

    # 1. Cadastra Organizações
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

    # Repositórios
    prop_repo = TransactionalRuralPropertyRepository(connection=db_connection)
    anim_repo = TransactionalAnimalRepository(connection=db_connection)
    mov_repo = TransactionalAnimalMovementRepository(connection=db_connection)
    stay_repo = TransactionalPropertyStayRepository(connection=db_connection)
    lot_repo = TransactionalLivestockLotRepository(connection=db_connection)
    mem_repo = TransactionalLotMembershipRepository(connection=db_connection)
    vet_repo = TransactionalVeterinarianRepository(connection=db_connection)

    # Serviços
    prop_service = RuralPropertyService(repository=prop_repo)
    anim_service = AnimalService(repository=anim_repo)
    mov_service = MovementService(
        movement_repository=mov_repo,
        stay_repository=stay_repo,
        animal_repository=anim_repo,
        property_repository=prop_repo,
    )
    lot_service = LotService(
        lot_repository=lot_repo,
        membership_repository=mem_repo,
        animal_repository=anim_repo,
        property_repository=prop_repo,
    )
    vet_service = VeterinarianService(repository=vet_repo)
    fact_provider = LivestockFactProvider(
        property_repository=prop_repo,
        animal_repository=anim_repo,
        stay_repository=stay_repo,
    )

    # A. Cadastra 2 Fazendas (Nascimento/Origem e Engorda/Destino)
    p_origem = prop_service.register_property(
        organization_id=org_1,
        code="FAZ-ORIGEM",
        name="Fazenda Primavera",
        municipality="Ribeirão Preto",
        state_code="SP",
        total_area_hectares=500.0,
    )
    p_destino = prop_service.register_property(
        organization_id=org_1,
        code="FAZ-DESTINO",
        name="Fazenda Santa Inês",
        municipality="Sertãozinho",
        state_code="SP",
        total_area_hectares=800.0,
    )

    # B. Cadastra Veterinário e Eleva para VERIFICADO_EM_FONTE
    vet = vet_service.register_veterinarian(
        organization_id=org_1,
        name="Dr. Marcos Silva",
        cpf="123.456.789-01",
        council_number="12345",
        council_state="SP",
    )
    vet_service.attach_evidence(vet.veterinarian_id, "evidence:crmv-card-pdf-123")
    vet_verified = vet_service.update_verification_status(
        vet.veterinarian_id, VerificationStatus.VERIFICADO_EM_FONTE
    )
    assert vet_verified.verification_status == VerificationStatus.VERIFICADO_EM_FONTE

    # C. Cadastra Animal na Fazenda Origem com SISBOV e Brinco de Manejo
    animal = anim_service.register_animal(
        organization_id=org_1,
        birth_property_id=p_origem.property_id,
        sex=AnimalSex.MALE,
        breed="Nelore Mocho",
        birth_date=date(2025, 2, 1),
    )
    anim_service.attach_identifier(
        animal_id=animal.animal_id,
        identifier_type=IdentifierType.OFFICIAL_SISBOV,
        identifier_value="BR5544332211",
    )
    anim_service.attach_identifier(
        animal_id=animal.animal_id,
        identifier_type=IdentifierType.EAR_TAG,
        identifier_value="MANEJO-101",
    )

    # Registra a estada inicial de nascimento
    from packages.livestock_domain.movement import PropertyStay

    stay_repo.save(
        PropertyStay(
            stay_id=TypedId.new("property_stay"),
            organization_id=org_1,
            animal_id=animal.animal_id,
            property_id=p_origem.property_id,
            start_time=datetime.now(UTC) - timedelta(days=90),
            end_time=None,
            status=StayStatus.ACTIVE,
        )
    )

    # D. Cria Lote de Bezerros na Origem e Insere Animal
    lot_bezerros = lot_service.create_lot(
        organization_id=org_1,
        property_id=p_origem.property_id,
        code="LOTE-DESMAME",
        name="Lote Desmame Primavera",
        lot_type=LotType.OPERATIONAL,
    )
    lot_service.add_animal_to_lot(
        lot_bezerros.lot_id, animal.animal_id, reason="Entrada no lote de bezerros desmamados"
    )

    comp_origem = lot_service.get_lot_composition(lot_bezerros.lot_id)
    assert len(comp_origem) == 1

    # E. Movimenta o Animal da Origem para o Destino
    m_time = datetime.now(UTC) - timedelta(hours=3)
    mov = mov_service.register_movement(
        organization_id=org_1,
        origin_property_id=p_origem.property_id,
        destination_property_id=p_destino.property_id,
        movement_time=m_time,
        animal_ids=(animal.animal_id,),
        reason="Transferência para recria e engorda",
    )
    assert mov.movement_id is not None

    # F. Valida atualização determinística da linha do tempo de permanências
    active_stay = mov_service.get_active_stay(animal.animal_id)
    assert active_stay is not None
    assert active_stay.property_id == p_destino.property_id
    assert active_stay.status == StayStatus.ACTIVE

    timeline = mov_service.get_stay_timeline(animal.animal_id)
    assert len(timeline) == 2
    assert timeline[0].status == StayStatus.CLOSED
    assert timeline[1].status == StayStatus.ACTIVE

    # G. Transfere Lote na Fazenda Destino
    lot_service.remove_animal_from_lot(lot_bezerros.lot_id, animal.animal_id)
    lot_engorda = lot_service.create_lot(
        organization_id=org_1,
        property_id=p_destino.property_id,
        code="LOTE-ENGORDA-P5",
        name="Lote Engorda Pasto 5",
        lot_type=LotType.OPERATIONAL,
    )
    lot_service.add_animal_to_lot(
        lot_engorda.lot_id, animal.animal_id, reason="Alojamento em engorda"
    )

    comp_engorda = lot_service.get_lot_composition(lot_engorda.lot_id)
    assert len(comp_engorda) == 1

    # H. Consulta Provedor de Fatos do Core
    snapshot = fact_provider.get_snapshot(
        organization_id=org_1,
        target_id=animal.animal_id,
        at_time=datetime.now(UTC),
    )
    assert len(snapshot.facts) > 0
    animal_fact = snapshot.facts[0]
    assert animal_fact.payload["current_property_id"] == p_destino.property_id.value.hex
    assert animal_fact.payload["stay_status"] == StayStatus.ACTIVE.value

    # I. RLS Isolation: Org 2 não enxerga dados da Org 1
    role_name = f"titan_e2e_role_{uuid4().hex[:12]}"
    quoted_role = f'"{role_name}"'
    db_connection.execute(
        text(
            f"CREATE ROLE {quoted_role} "
            "NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS"
        )
    )
    db_connection.execute(text(f"GRANT USAGE ON SCHEMA core_audit TO {quoted_role}"))
    db_connection.execute(text(f"GRANT ALL ON ALL TABLES IN SCHEMA core_audit TO {quoted_role}"))
    db_connection.execute(text(f"SET LOCAL ROLE {quoted_role}"))

    db_connection.execute(
        text("SELECT set_config('titan.organization_id', :org_id, true)"),
        {"org_id": str(org_2.value)},
    )

    anim_repo_2 = TransactionalAnimalRepository(connection=db_connection)
    prop_repo_2 = TransactionalRuralPropertyRepository(connection=db_connection)
    mov_repo_2 = TransactionalAnimalMovementRepository(connection=db_connection)
    lot_repo_2 = TransactionalLivestockLotRepository(connection=db_connection)

    assert anim_repo_2.get_by_id(animal.animal_id) is None
    assert prop_repo_2.get_by_id(p_origem.property_id) is None
    assert mov_repo_2.get_by_id(mov.movement_id) is None
    assert lot_repo_2.get_by_id(lot_engorda.lot_id) is None

    db_connection.execute(text("RESET ROLE"))
    db_connection.execute(text(f"DROP OWNED BY {quoted_role}"))
    db_connection.execute(text(f"DROP ROLE {quoted_role}"))
