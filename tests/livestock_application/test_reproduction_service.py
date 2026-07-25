"""Evento reprodutivo (Passo 13.3 - Titan Livestock, ADR-0040).

O que estes testes protegem é a separação entre o evento reprodutivo e o
indivíduo rastreável. Natimorto não é morte, aborto não inventa indivíduo, e o
parto gemelar é um evento com duas crias — perder qualquer uma dessas três
distinções produz indicador errado, que é onde alguém decide comprar ou reprovar.
"""

from datetime import UTC, datetime, timedelta

import pytest

from packages.core_application.relation_service import RelationService
from packages.livestock_application.event_recorder import (
    LivestockEventRecorder,
    LivestockOperationContext,
)
from packages.livestock_application.exit_service import AnimalForaDoRebanho, guard_animal_active
from packages.livestock_application.parentage_service import ParentageService
from packages.livestock_application.reproduction_service import (
    CriaDeclarada,
    PartoInvalido,
    PartoRegistrado,
    PropriedadeDivergeDaPermanencia,
    ReproductionService,
    ReproductiveEventRepositoryPort,
)
from packages.livestock_domain.animal import (
    Animal,
    AnimalSex,
    BirthOutcome,
    BirthPropertySource,
)
from packages.livestock_domain.events import ANIMAL_REGISTERED, REPRODUCTIVE_EVENT_RECORDED
from packages.livestock_domain.parentage import ParentageRole
from packages.livestock_domain.reproduction import (
    GestationalAgeBasis,
    ReproductiveEvent,
    ReproductiveEventType,
)
from packages.shared_kernel import OrganizationId, TypedId
from tests.livestock_application.conftest import FakeEventLog
from tests.livestock_application.test_exit_service import InMemoryAnimalRepo, InMemoryExitRepo
from tests.livestock_support import FakeRelationRepository

ONTEM = datetime.now(UTC) - timedelta(days=1)


class InMemoryEventRepo(ReproductiveEventRepositoryPort):
    def __init__(self) -> None:
        self.eventos: dict[str, ReproductiveEvent] = {}

    def save(self, event: ReproductiveEvent) -> None:
        self.eventos[str(event.event_id.value)] = event

    def get_by_id(self, event_id: TypedId) -> ReproductiveEvent | None:
        return self.eventos.get(str(event_id.value))

    def list_by_dam(
        self, organization_id: OrganizationId, dam_id: TypedId
    ) -> list[ReproductiveEvent]:
        return sorted(
            (
                evento
                for evento in self.eventos.values()
                if evento.organization_id == organization_id and evento.dam_id == dam_id
            ),
            key=lambda evento: evento.occurred_at,
        )

    def get_by_offspring(self, animal_id: TypedId) -> ReproductiveEvent | None:
        for evento in self.eventos.values():
            if any(cria.animal_id == animal_id for cria in evento.offspring):
                return evento
        return None


class FakeStayReader:
    """Onde a mãe estava. `None` é resposta legítima, e não falha."""

    def __init__(self, propriedade: TypedId | None = None) -> None:
        self.propriedade = propriedade

    def property_at(self, animal_id: TypedId, instant: datetime) -> TypedId | None:
        return self.propriedade


class Fazenda:
    def __init__(
        self,
        recorder: LivestockEventRecorder,
        context: LivestockOperationContext,
        permanencia: TypedId | None = None,
    ) -> None:
        self.context = context
        self.organization_id = context.organization_id
        self.animals = InMemoryAnimalRepo(InMemoryExitRepo())
        self.eventos = InMemoryEventRepo()
        self.service = ReproductionService(
            event_repository=self.eventos,
            animal_repository=self.animals,
            parentage_service=ParentageService(
                relation_service=RelationService(repository=FakeRelationRepository()),
                animal_repository=self.animals,
                recorder=recorder,
            ),
            stay_reader=FakeStayReader(permanencia),
            recorder=recorder,
        )

    def animal(self, sexo: AnimalSex) -> TypedId:
        criado = Animal(
            animal_id=TypedId.new("animal"),
            organization_id=self.organization_id,
            birth_property_id=TypedId.new("rural_property"),
            sex=sexo,
        )
        self.animals.save(criado)
        return criado.animal_id


@pytest.fixture
def fazenda(recorder: LivestockEventRecorder, context: LivestockOperationContext) -> Fazenda:
    return Fazenda(recorder, context)


def _parir(
    fazenda: Fazenda, mae: TypedId, *crias: CriaDeclarada, **kwargs: object
) -> PartoRegistrado:
    return fazenda.service.register_parturition(
        context=fazenda.context,
        dam_id=mae,
        occurred_at=ONTEM,
        offspring=crias,
        **kwargs,  # type: ignore[arg-type]
    )


def test_o_parto_cria_a_cria_e_a_linhagem_no_mesmo_ato(fazenda: Fazenda) -> None:
    """Sem isto, o bezerro fica cadastrado sem saber de quem é até a segunda chamada."""
    vaca = fazenda.animal(AnimalSex.FEMALE)

    registrado = _parir(fazenda, vaca, CriaDeclarada(outcome=BirthOutcome.NASCIDO_VIVO))

    bezerro = registrado.animals[0]
    assert bezerro.birth_outcome is BirthOutcome.NASCIDO_VIVO
    assert bezerro.birth_date == ONTEM.date()
    ascendentes = fazenda.service.parentage_service.parents_of(
        fazenda.organization_id, bezerro.animal_id
    )
    assert {link.parent_id for link in ascendentes} == {vaca}


def test_o_agregado_do_evento_e_o_proprio_evento(fazenda: Fazenda, event_log: FakeEventLog) -> None:
    """Mãe e cria o citam; emitir um por ponta transformaria um fato em dois."""
    vaca = fazenda.animal(AnimalSex.FEMALE)

    registrado = _parir(fazenda, vaca, CriaDeclarada(outcome=BirthOutcome.NASCIDO_VIVO))

    evento = event_log.only(REPRODUCTIVE_EVENT_RECORDED)
    assert evento.aggregate_reference.target_id == registrado.event.event_id
    assert evento.aggregate_reference.target_id != vaca


def test_o_gemelar_e_um_evento_com_duas_crias(fazenda: Fazenda, event_log: FakeEventLog) -> None:
    """Dois partos perderiam o vínculo obstétrico que explica o natimorto."""
    vaca = fazenda.animal(AnimalSex.FEMALE)

    registrado = _parir(
        fazenda,
        vaca,
        CriaDeclarada(outcome=BirthOutcome.NASCIDO_VIVO),
        CriaDeclarada(outcome=BirthOutcome.NATIMORTO),
    )

    evento = registrado.event
    assert len(evento.offspring) == 2
    assert evento.nascidos_vivos == 1
    assert evento.natimortos == 1
    assert len(event_log.of_type(REPRODUCTIVE_EVENT_RECORDED)) == 1
    assert len(event_log.of_type(ANIMAL_REGISTERED)) == 2


def test_o_natimorto_nao_recebe_registro_de_saida(fazenda: Fazenda) -> None:
    """`MORTE` diria que nasceu vivo e morreu depois."""
    vaca = fazenda.animal(AnimalSex.FEMALE)

    registrado = _parir(fazenda, vaca, CriaDeclarada(outcome=BirthOutcome.NATIMORTO))

    natimorto = registrado.animals[0]
    assert natimorto.birth_outcome is BirthOutcome.NATIMORTO
    assert fazenda.animals.get_exit(natimorto.animal_id) is None
    assert not natimorto.born_alive


def test_o_natimorto_nao_recebe_fatos(fazenda: Fazenda) -> None:
    """Ele é rastreável pela genealogia, mas nunca entrou no ciclo operacional."""
    vaca = fazenda.animal(AnimalSex.FEMALE)
    registrado = _parir(fazenda, vaca, CriaDeclarada(outcome=BirthOutcome.NATIMORTO))

    with pytest.raises(AnimalForaDoRebanho):
        guard_animal_active(
            fazenda.animals,
            registrado.animals[0].animal_id,
            datetime.now(UTC),
        )


def test_o_nascido_vivo_recebe_fatos(fazenda: Fazenda) -> None:
    vaca = fazenda.animal(AnimalSex.FEMALE)
    registrado = _parir(fazenda, vaca, CriaDeclarada(outcome=BirthOutcome.NASCIDO_VIVO))

    guard_animal_active(
        fazenda.animals,
        registrado.animals[0].animal_id,
        datetime.now(UTC),
    )


def test_a_cria_conserva_a_linhagem_mesmo_natimorta(fazenda: Fazenda) -> None:
    """É o que permite investigar a causa: de qual matriz e de qual touro veio."""
    vaca = fazenda.animal(AnimalSex.FEMALE)
    touro = fazenda.animal(AnimalSex.MALE)

    registrado = _parir(fazenda, vaca, CriaDeclarada(outcome=BirthOutcome.NATIMORTO), sire_id=touro)

    ascendentes = fazenda.service.parentage_service.parents_of(
        fazenda.organization_id,
        registrado.animals[0].animal_id,
    )
    papeis = {link.role: link.parent_id for link in ascendentes}
    assert papeis[ParentageRole.MAE_GENETICA] == vaca
    assert papeis[ParentageRole.PAI] == touro


# -- Aborto ------------------------------------------------------------------


def test_o_aborto_nao_cria_animal(fazenda: Fazenda, event_log: FakeEventLog) -> None:
    vaca = fazenda.animal(AnimalSex.FEMALE)

    evento = fazenda.service.register_pregnancy_loss(
        context=fazenda.context, dam_id=vaca, occurred_at=ONTEM
    )

    assert evento.event_type is ReproductiveEventType.ABORTO
    assert evento.offspring == ()
    assert event_log.of_type(ANIMAL_REGISTERED) == []


def test_a_idade_gestacional_ausente_significa_desconhecida(fazenda: Fazenda) -> None:
    """Nunca zero, nunca estimativa fabricada."""
    vaca = fazenda.animal(AnimalSex.FEMALE)

    evento = fazenda.service.register_pregnancy_loss(
        context=fazenda.context, dam_id=vaca, occurred_at=ONTEM
    )

    assert evento.gestational_age_days is None
    assert evento.gestational_age_basis is GestationalAgeBasis.UNKNOWN


def test_a_idade_gestacional_viaja_com_a_base(fazenda: Fazenda) -> None:
    vaca = fazenda.animal(AnimalSex.FEMALE)

    evento = fazenda.service.register_pregnancy_loss(
        context=fazenda.context,
        dam_id=vaca,
        occurred_at=ONTEM,
        gestational_age_days=170,
        gestational_age_basis=GestationalAgeBasis.ESTIMATED,
    )

    assert evento.gestational_age_days == 170
    assert evento.gestational_age_basis is GestationalAgeBasis.ESTIMATED


def test_idade_sem_base_e_recusada(fazenda: Fazenda) -> None:
    """Declarar idade sem dizer como se chegou a ela é inventar precisão."""
    vaca = fazenda.animal(AnimalSex.FEMALE)

    with pytest.raises(ValueError, match="base de determinação"):
        fazenda.service.register_pregnancy_loss(
            context=fazenda.context, dam_id=vaca, occurred_at=ONTEM, gestational_age_days=170
        )


def test_base_sem_idade_e_recusada(fazenda: Fazenda) -> None:
    vaca = fazenda.animal(AnimalSex.FEMALE)

    with pytest.raises(ValueError, match="UNKNOWN"):
        fazenda.service.register_pregnancy_loss(
            context=fazenda.context,
            dam_id=vaca,
            occurred_at=ONTEM,
            gestational_age_basis=GestationalAgeBasis.KNOWN,
        )


# -- Propriedade de nascimento -----------------------------------------------


def test_a_propriedade_e_derivada_da_permanencia_da_mae(
    recorder: LivestockEventRecorder, context: LivestockOperationContext
) -> None:
    fazenda_x = TypedId.new("rural_property")
    fazenda = Fazenda(recorder, context, permanencia=fazenda_x)
    vaca = fazenda.animal(AnimalSex.FEMALE)

    registrado = _parir(fazenda, vaca, CriaDeclarada(outcome=BirthOutcome.NASCIDO_VIVO))

    bezerro = registrado.animals[0]
    assert bezerro.birth_property_id == fazenda_x
    assert bezerro.birth_property_source is BirthPropertySource.DERIVED_FROM_MATERNAL_STAY


def test_sem_permanencia_aceita_a_declarada(fazenda: Fazenda) -> None:
    vaca = fazenda.animal(AnimalSex.FEMALE)
    declarada = TypedId.new("rural_property")

    registrado = _parir(
        fazenda,
        vaca,
        CriaDeclarada(outcome=BirthOutcome.NASCIDO_VIVO),
        birth_property_id=declarada,
    )

    bezerro = registrado.animals[0]
    assert bezerro.birth_property_id == declarada
    assert bezerro.birth_property_source is BirthPropertySource.DECLARED


def test_sem_permanencia_e_sem_declaracao_o_parto_entra_com_a_lacuna(fazenda: Fazenda) -> None:
    """Ausência de dado contextual não apaga um fato real ocorrido."""
    vaca = fazenda.animal(AnimalSex.FEMALE)

    registrado = _parir(fazenda, vaca, CriaDeclarada(outcome=BirthOutcome.NASCIDO_VIVO))

    bezerro = registrado.animals[0]
    assert bezerro.birth_property_id is None
    assert bezerro.birth_property_source is BirthPropertySource.UNKNOWN


def test_declarada_divergente_da_permanencia_e_conflito(
    recorder: LivestockEventRecorder, context: LivestockOperationContext
) -> None:
    """Não porque a declarada esteja errada, mas porque alguém precisa decidir."""
    fazenda = Fazenda(recorder, context, permanencia=TypedId.new("rural_property"))
    vaca = fazenda.animal(AnimalSex.FEMALE)

    with pytest.raises(PropriedadeDivergeDaPermanencia):
        _parir(
            fazenda,
            vaca,
            CriaDeclarada(outcome=BirthOutcome.NASCIDO_VIVO),
            birth_property_id=TypedId.new("rural_property"),
        )


# -- Guardas -----------------------------------------------------------------


def test_quem_pare_e_femea(fazenda: Fazenda) -> None:
    touro = fazenda.animal(AnimalSex.MALE)

    with pytest.raises(PartoInvalido):
        _parir(fazenda, touro, CriaDeclarada(outcome=BirthOutcome.NASCIDO_VIVO))


def test_parto_sem_cria_e_recusado(fazenda: Fazenda) -> None:
    """Gestação encerrada sem indivíduo é perda gestacional, e tem rota própria."""
    vaca = fazenda.animal(AnimalSex.FEMALE)

    with pytest.raises(PartoInvalido):
        _parir(fazenda, vaca)


def test_o_futuro_nao_e_aceito(fazenda: Fazenda) -> None:
    vaca = fazenda.animal(AnimalSex.FEMALE)

    with pytest.raises(PartoInvalido):
        fazenda.service.register_parturition(
            context=fazenda.context,
            dam_id=vaca,
            occurred_at=datetime.now(UTC) + timedelta(days=1),
            offspring=(CriaDeclarada(outcome=BirthOutcome.NASCIDO_VIVO),),
        )


def test_mae_de_outra_organizacao_nao_e_alcancada(fazenda: Fazenda) -> None:
    with pytest.raises(KeyError):
        _parir(fazenda, TypedId.new("animal"), CriaDeclarada(outcome=BirthOutcome.NASCIDO_VIVO))


def test_cria_com_resultado_nao_informado_e_recusada(fazenda: Fazenda) -> None:
    """Quem registra o parto sabe se o bezerro nasceu vivo."""
    vaca = fazenda.animal(AnimalSex.FEMALE)

    with pytest.raises(ValueError, match="resultado conhecido"):
        _parir(fazenda, vaca, CriaDeclarada(outcome=BirthOutcome.NAO_INFORMADO))


# -- Consultas ---------------------------------------------------------------


def test_o_historico_reprodutivo_conta_cada_desfecho(fazenda: Fazenda) -> None:
    vaca = fazenda.animal(AnimalSex.FEMALE)
    _parir(fazenda, vaca, CriaDeclarada(outcome=BirthOutcome.NASCIDO_VIVO))
    fazenda.service.register_pregnancy_loss(
        context=fazenda.context, dam_id=vaca, occurred_at=ONTEM - timedelta(days=400)
    )

    historia = fazenda.service.history_of(fazenda.organization_id, vaca)

    assert [evento.event_type for evento in historia] == [
        ReproductiveEventType.ABORTO,
        ReproductiveEventType.PARTO,
    ]


def test_a_origem_do_animal_e_o_parto_de_onde_ele_veio(fazenda: Fazenda) -> None:
    vaca = fazenda.animal(AnimalSex.FEMALE)
    registrado = _parir(fazenda, vaca, CriaDeclarada(outcome=BirthOutcome.NASCIDO_VIVO))

    origem = fazenda.service.origin_of(registrado.animals[0].animal_id)

    assert origem is not None
    assert origem.event_id == registrado.event.event_id


def test_o_rebanho_legado_nao_tem_origem(fazenda: Fazenda) -> None:
    """`None` é resposta honesta: ninguém registrou o parto dele."""
    vaca = fazenda.animal(AnimalSex.FEMALE)

    assert fazenda.service.origin_of(vaca) is None
