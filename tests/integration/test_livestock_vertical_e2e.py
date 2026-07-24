"""Teste de integração E2E da vertical Titan Livestock (Passo 8.6 - Encerramento do Marco 8)."""

import os
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import Connection, create_engine, text

from packages.core_infrastructure.persistence.decision import TransactionalDecisionRepository
from packages.core_infrastructure.persistence.evaluation import TransactionalEvaluationRepository
from packages.core_infrastructure.persistence.events import DomainEventRepository
from packages.livestock_application.animal_service import AnimalService
from packages.livestock_application.event_recorder import LivestockEventRecorder
from packages.livestock_application.fact_provider import LivestockFactProvider
from packages.livestock_application.lot_service import LotService
from packages.livestock_application.movement_service import MovementService
from packages.livestock_application.property_service import RuralPropertyService
from packages.livestock_application.timeline_service import (
    LivestockTimelineService,
    TimelineCutoff,
)
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
from packages.livestock_infrastructure.persistence.medication_repository import (
    TransactionalMedicationBatchRepository,
)
from packages.livestock_infrastructure.persistence.movement_repository import (
    TransactionalAnimalMovementRepository,
    TransactionalPropertyStayRepository,
)
from packages.livestock_infrastructure.persistence.property_repository import (
    TransactionalRuralPropertyRepository,
)
from packages.livestock_infrastructure.persistence.treatment_repository import (
    TransactionalTreatmentApplicationRepository,
)
from packages.livestock_infrastructure.persistence.veterinarian_repository import (
    TransactionalVeterinarianRepository,
)
from packages.shared_kernel import OrganizationId, SystemClock, TypedId, UniversalReference
from tests.livestock_support import operation_context


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

    # O log de eventos é o do Core, no mesmo PostgreSQL: é aqui que se prova que a
    # vertical grava de verdade, com numeração por agregado e cadeia de hash.
    event_log = DomainEventRepository(connection=db_connection)
    recorder = LivestockEventRecorder(event_log=event_log, clock=SystemClock())
    ctx = operation_context(org_1)

    # Serviços
    prop_service = RuralPropertyService(repository=prop_repo, recorder=recorder)
    anim_service = AnimalService(repository=anim_repo, recorder=recorder)
    mov_service = MovementService(
        movement_repository=mov_repo,
        stay_repository=stay_repo,
        animal_repository=anim_repo,
        property_repository=prop_repo,
        recorder=recorder,
    )
    lot_service = LotService(
        lot_repository=lot_repo,
        membership_repository=mem_repo,
        animal_repository=anim_repo,
        property_repository=prop_repo,
        recorder=recorder,
    )
    vet_service = VeterinarianService(repository=vet_repo, recorder=recorder)
    fact_provider = LivestockFactProvider(
        property_repository=prop_repo,
        animal_repository=anim_repo,
        stay_repository=stay_repo,
    )

    # A. Cadastra 2 Fazendas (Nascimento/Origem e Engorda/Destino)
    p_origem = prop_service.register_property(
        context=ctx,
        code="FAZ-ORIGEM",
        name="Fazenda Primavera",
        municipality="Ribeirão Preto",
        state_code="SP",
        total_area_hectares=500.0,
    )
    p_destino = prop_service.register_property(
        context=ctx,
        code="FAZ-DESTINO",
        name="Fazenda Santa Inês",
        municipality="Sertãozinho",
        state_code="SP",
        total_area_hectares=800.0,
    )

    # B. Cadastra Veterinário e Eleva para VERIFICADO_EM_FONTE
    vet = vet_service.register_veterinarian(
        context=ctx,
        name="Dr. Marcos Silva",
        cpf="123.456.789-01",
        council_number="12345",
        council_state="SP",
    )
    vet_service.attach_evidence(ctx, vet.veterinarian_id, "evidence:crmv-card-pdf-123")
    vet_verified = vet_service.update_verification_status(
        ctx, vet.veterinarian_id, VerificationStatus.VERIFICADO_EM_FONTE
    )
    assert vet_verified.verification_status == VerificationStatus.VERIFICADO_EM_FONTE

    # C. Cadastra Animal na Fazenda Origem com SISBOV e Brinco de Manejo
    animal = anim_service.register_animal(
        context=ctx,
        birth_property_id=p_origem.property_id,
        sex=AnimalSex.MALE,
        breed="Nelore Mocho",
        birth_date=date(2025, 2, 1),
    )
    anim_service.attach_identifier(
        context=ctx,
        animal_id=animal.animal_id,
        identifier_type=IdentifierType.OFFICIAL_SISBOV,
        identifier_value="BR5544332211",
    )
    anim_service.attach_identifier(
        context=ctx,
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
        context=ctx,
        property_id=p_origem.property_id,
        code="LOTE-DESMAME",
        name="Lote Desmame Primavera",
        lot_type=LotType.OPERATIONAL,
    )
    lot_service.add_animal_to_lot(
        ctx, lot_bezerros.lot_id, animal.animal_id, reason="Entrada no lote de bezerros desmamados"
    )

    comp_origem = lot_service.get_lot_composition(lot_bezerros.lot_id)
    assert len(comp_origem) == 1

    # E. Movimenta o Animal da Origem para o Destino
    m_time = datetime.now(UTC) - timedelta(hours=3)
    mov = mov_service.register_movement(
        context=ctx,
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
    lot_service.remove_animal_from_lot(ctx, lot_bezerros.lot_id, animal.animal_id)
    lot_engorda = lot_service.create_lot(
        context=ctx,
        property_id=p_destino.property_id,
        code="LOTE-ENGORDA-P5",
        name="Lote Engorda Pasto 5",
        lot_type=LotType.OPERATIONAL,
    )
    lot_service.add_animal_to_lot(
        ctx, lot_engorda.lot_id, animal.animal_id, reason="Alojamento em engorda"
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

    # H2. Os fatos da vertical chegaram ao log append-only do Core.
    def stream(target_id: TypedId) -> tuple[str, ...]:
        reference = UniversalReference(
            target_id=target_id, organization_id=org_1, contract_version=1
        )
        return tuple(event.event_type for event in event_log.list_for_aggregate(reference))

    # O animal tem cadastro e duas marcações, na ordem em que aconteceram.
    assert stream(animal.animal_id) == (
        "livestock.animal_registered",
        "livestock.identifier_attached",
        "livestock.identifier_attached",
    )
    # O lote de desmame guarda entrada e saída: remover não apagou a entrada.
    assert stream(lot_bezerros.lot_id) == (
        "livestock.lot_created",
        "livestock.animal_added_to_lot",
        "livestock.animal_removed_from_lot",
    )
    assert stream(mov.movement_id) == ("livestock.animal_moved",)
    assert stream(vet.veterinarian_id) == (
        "livestock.veterinarian_registered",
        "livestock.veterinarian_status_updated",
        "livestock.veterinarian_status_updated",
    )

    # A cadeia de hash do Core foi aplicada aos eventos da vertical: o primeiro
    # não tem elo anterior e os seguintes encadeiam no hash do antecessor.
    animal_reference = UniversalReference(
        target_id=animal.animal_id, organization_id=org_1, contract_version=1
    )
    stored = event_log.list_for_aggregate(animal_reference)
    assert [event.aggregate_version for event in stored] == [1, 2, 3]
    assert stored[0].previous_hash is None
    assert stored[1].previous_hash == stored[0].current_hash
    assert stored[2].previous_hash == stored[1].current_hash
    # A autoria e a correlação atravessaram o fluxo inteiro.
    assert {event.correlation_id for event in stored} == {ctx.correlation_id}
    assert {event.actor_reference for event in stored} == {ctx.actor_reference}

    # H3. A linha do tempo do Passo 10.1b, montada sobre o log real do Core.
    timeline_service = LivestockTimelineService(
        event_reader=event_log,
        movement_repository=mov_repo,
        application_repository=TransactionalTreatmentApplicationRepository(
            connection=db_connection
        ),
        membership_repository=mem_repo,
        batch_repository=TransactionalMedicationBatchRepository(connection=db_connection),
        evaluation_repository=TransactionalEvaluationRepository(connection=db_connection),
        decision_repository=TransactionalDecisionRepository(connection=db_connection),
    )
    historia = timeline_service.animal_timeline(org_1, animal.animal_id)
    tipos = [entry.entry_type for entry in historia]

    # A história do animal reúne os fluxos de tudo que o tocou: cadastro e
    # marcações dele, os dois lotes por onde passou e a movimentação.
    assert tipos.count("livestock.animal_registered") == 1
    assert tipos.count("livestock.identifier_attached") == 2
    assert "livestock.animal_moved" in tipos
    assert tipos.count("livestock.animal_added_to_lot") == 2
    assert "livestock.animal_removed_from_lot" in tipos
    # A propriedade não é história do animal e não entra.
    assert "livestock.property_registered" not in tipos

    # Ordem total e reproduzível: duas leituras são idênticas, não parecidas.
    assert historia == timeline_service.animal_timeline(org_1, animal.animal_id)
    assert [entry.sort_key() for entry in historia] == sorted(
        entry.sort_key() for entry in historia
    )

    # O corte por instante devolve um prefixo do que a leitura completa devolveu.
    corte = timeline_service.animal_timeline(
        org_1,
        animal.animal_id,
        TimelineCutoff(occurred_until=m_time - timedelta(seconds=1)),
    )
    assert list(corte) == [
        entry for entry in historia if entry.occurred_at <= m_time - timedelta(seconds=1)
    ]
    assert "livestock.animal_moved" not in [entry.entry_type for entry in corte]

    # Outra Organization não enxerga história alguma deste animal.
    assert timeline_service.animal_timeline(org_2, animal.animal_id) == ()

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
