"""Genealogia (Passo 13.2 - Titan Livestock).

O que estes testes protegem é a separação entre as duas maternidades. Com
transferência de embrião, doadora e receptora são fêmeas diferentes: a linhagem
sobe pela doadora, e a receptora responde pelo histórico reprodutivo. Colapsá-las
faria a árvore genealógica ganhar ancestrais que não são.
"""

from datetime import UTC, date, datetime, timedelta

import pytest

from packages.core_application.relation_service import RelationService
from packages.livestock_application.event_recorder import (
    LivestockEventRecorder,
    LivestockOperationContext,
)
from packages.livestock_application.parentage_service import (
    ParentageService,
    ParentescoInvalido,
    ProgenitorJaRegistrado,
)
from packages.livestock_domain.animal import Animal, AnimalSex
from packages.livestock_domain.events import PARENTAGE_REGISTERED
from packages.livestock_domain.parentage import (
    FATHER_OF,
    GENETIC_MOTHER_OF,
    GESTATIONAL_MOTHER_OF,
    ParentageConfidence,
    ParentageRole,
)
from packages.shared_kernel import TypedId
from tests.livestock_application.conftest import FakeEventLog
from tests.livestock_application.test_exit_service import InMemoryAnimalRepo, InMemoryExitRepo
from tests.livestock_support import FakeRelationRepository

ONTEM = datetime.now(UTC) - timedelta(days=1)


class Rebanho:
    """Um rebanho pequeno, com os animais que a genealogia precisa distinguir."""

    def __init__(
        self, recorder: LivestockEventRecorder, context: LivestockOperationContext
    ) -> None:
        self.context = context
        self.organization_id = context.organization_id
        self.relations = FakeRelationRepository()
        self.animals = InMemoryAnimalRepo(InMemoryExitRepo())
        self.service = ParentageService(
            relation_service=RelationService(repository=self.relations),
            animal_repository=self.animals,
            recorder=recorder,
        )

    def animal(self, sexo: AnimalSex, nascimento: date | None = None) -> TypedId:
        criado = Animal(
            animal_id=TypedId.new("animal"),
            organization_id=self.organization_id,
            birth_property_id=TypedId.new("rural_property"),
            sex=sexo,
            birth_date=nascimento,
        )
        self.animals.save(criado)
        return criado.animal_id

    def maternidade(
        self,
        cria: TypedId,
        doadora: TypedId,
        receptora: TypedId | None = None,
        confianca: ParentageConfidence = ParentageConfidence.DECLARADO,
    ) -> None:
        self.service.register_maternity(
            context=self.context,
            offspring_id=cria,
            genetic_mother_id=doadora,
            gestational_mother_id=receptora,
            occurred_at=ONTEM,
            confidence=confianca,
        )

    def paternidade(
        self,
        cria: TypedId,
        pai: TypedId,
        confianca: ParentageConfidence = ParentageConfidence.DECLARADO,
    ) -> None:
        self.service.register_parentage(
            context=self.context,
            offspring_id=cria,
            parent_id=pai,
            role=ParentageRole.PAI,
            occurred_at=ONTEM,
            confidence=confianca,
        )


@pytest.fixture
def rebanho(recorder: LivestockEventRecorder, context: LivestockOperationContext) -> Rebanho:
    return Rebanho(recorder, context)


def test_a_maternidade_grava_dois_fatos_mesmo_sem_transferencia(
    rebanho: Rebanho, event_log: FakeEventLog
) -> None:
    """Ausência se declara, nunca se infere: as duas relações existem sempre."""
    bezerro = rebanho.animal(AnimalSex.MALE)
    vaca = rebanho.animal(AnimalSex.FEMALE)

    genetica, gestacional = rebanho.service.register_maternity(
        context=rebanho.context,
        offspring_id=bezerro,
        genetic_mother_id=vaca,
        occurred_at=ONTEM,
        confidence=ParentageConfidence.DECLARADO,
    )

    assert genetica.relation_type == GENETIC_MOTHER_OF
    assert gestacional.relation_type == GESTATIONAL_MOTHER_OF
    # Sem transferência, as duas apontam para a mesma vaca — e ainda assim são duas.
    assert genetica.source_reference.target_id == vaca
    assert gestacional.source_reference.target_id == vaca
    assert len(event_log.of_type(PARENTAGE_REGISTERED)) == 2


def test_o_agregado_do_evento_e_a_relacao(rebanho: Rebanho, event_log: FakeEventLog) -> None:
    """O vínculo é a entidade criada; as duas pontas o enxergam por citação.

    Emitir um evento para a cria e outro para a mãe transformaria um fato em dois.
    """
    bezerro = rebanho.animal(AnimalSex.MALE)
    vaca = rebanho.animal(AnimalSex.FEMALE)

    genetica, _ = rebanho.service.register_maternity(
        context=rebanho.context,
        offspring_id=bezerro,
        genetic_mother_id=vaca,
        occurred_at=ONTEM,
        confidence=ParentageConfidence.DECLARADO,
    )

    agregados = {
        evento.aggregate_reference.target_id for evento in event_log.of_type(PARENTAGE_REGISTERED)
    }
    assert genetica.relation_id in agregados
    assert bezerro not in agregados
    assert vaca not in agregados


def test_a_relacao_guarda_o_evento_que_a_criou(rebanho: Rebanho) -> None:
    bezerro = rebanho.animal(AnimalSex.MALE)
    vaca = rebanho.animal(AnimalSex.FEMALE)

    genetica, _ = rebanho.service.register_maternity(
        context=rebanho.context,
        offspring_id=bezerro,
        genetic_mother_id=vaca,
        occurred_at=ONTEM,
        confidence=ParentageConfidence.DECLARADO,
    )

    assert genetica.created_by_event is not None


def test_a_transferencia_de_embriao_separa_doadora_de_receptora(rebanho: Rebanho) -> None:
    bezerro = rebanho.animal(AnimalSex.MALE)
    doadora = rebanho.animal(AnimalSex.FEMALE)
    receptora = rebanho.animal(AnimalSex.FEMALE)

    rebanho.maternidade(bezerro, doadora, receptora)

    # A linhagem sobe pela doadora.
    arvore = rebanho.service.ancestry(rebanho.organization_id, bezerro)
    ascendentes = {ramo.link.parent_id for ramo in arvore.parents}
    assert ascendentes == {doadora}

    # A receptora não é ancestral, e responde pelo que de fato fez.
    gestadas = rebanho.service.gestational_history(rebanho.organization_id, receptora)
    assert [link.offspring_id for link in gestadas] == [bezerro]
    assert rebanho.service.descendants(rebanho.organization_id, receptora) == ()


def test_a_arvore_sobe_pelas_geracoes_pedidas(rebanho: Rebanho) -> None:
    avo = rebanho.animal(AnimalSex.FEMALE)
    mae = rebanho.animal(AnimalSex.FEMALE)
    bezerro = rebanho.animal(AnimalSex.MALE)
    rebanho.maternidade(mae, avo)
    rebanho.maternidade(bezerro, mae)

    duas = rebanho.service.ancestry(rebanho.organization_id, bezerro, generations=2)
    uma = rebanho.service.ancestry(rebanho.organization_id, bezerro, generations=1)

    assert duas.parents[0].link.parent_id == mae
    assert duas.parents[0].ancestry.parents[0].link.parent_id == avo
    # O limite corta a travessia, e não apenas a resposta.
    assert uma.parents[0].ancestry.parents == ()


def test_o_touro_do_lote_admite_varios_pais_declarados(rebanho: Rebanho) -> None:
    """Paternidade indeterminada é caso reconhecido, não erro a corrigir."""
    bezerro = rebanho.animal(AnimalSex.MALE)
    touros = [rebanho.animal(AnimalSex.MALE) for _ in range(3)]

    for touro in touros:
        rebanho.paternidade(bezerro, touro)

    pais = [
        link
        for link in rebanho.service.parents_of(rebanho.organization_id, bezerro)
        if link.role is ParentageRole.PAI
    ]
    assert {link.parent_id for link in pais} == set(touros)


def test_paternidade_documentada_nao_convive_com_outra(rebanho: Rebanho) -> None:
    """Admitir um segundo pai ao lado de um vínculo documentado vira palpite."""
    bezerro = rebanho.animal(AnimalSex.MALE)
    touro = rebanho.animal(AnimalSex.MALE)
    outro = rebanho.animal(AnimalSex.MALE)
    rebanho.paternidade(bezerro, touro, ParentageConfidence.DOCUMENTADO)

    with pytest.raises(ProgenitorJaRegistrado):
        rebanho.paternidade(bezerro, outro)


def test_a_segunda_mae_genetica_e_recusada(rebanho: Rebanho) -> None:
    bezerro = rebanho.animal(AnimalSex.MALE)
    vaca = rebanho.animal(AnimalSex.FEMALE)
    outra = rebanho.animal(AnimalSex.FEMALE)
    rebanho.maternidade(bezerro, vaca)

    with pytest.raises(ProgenitorJaRegistrado):
        rebanho.service.register_parentage(
            context=rebanho.context,
            offspring_id=bezerro,
            parent_id=outra,
            role=ParentageRole.MAE_GENETICA,
            occurred_at=ONTEM,
            confidence=ParentageConfidence.DECLARADO,
        )


def test_o_mesmo_vinculo_nao_e_registrado_duas_vezes(rebanho: Rebanho) -> None:
    bezerro = rebanho.animal(AnimalSex.MALE)
    touro = rebanho.animal(AnimalSex.MALE)
    rebanho.paternidade(bezerro, touro)

    with pytest.raises(ProgenitorJaRegistrado):
        rebanho.paternidade(bezerro, touro)


@pytest.mark.parametrize(
    ("papel", "sexo"),
    [
        (ParentageRole.MAE_GENETICA, AnimalSex.MALE),
        (ParentageRole.MAE_GESTACIONAL, AnimalSex.UNKNOWN),
        (ParentageRole.PAI, AnimalSex.FEMALE),
    ],
)
def test_o_sexo_do_progenitor_precisa_caber_no_papel(
    rebanho: Rebanho, papel: ParentageRole, sexo: AnimalSex
) -> None:
    """Nomear alguém como mãe é afirmar que é fêmea."""
    bezerro = rebanho.animal(AnimalSex.MALE)
    progenitor = rebanho.animal(sexo)

    with pytest.raises(ParentescoInvalido):
        rebanho.service.register_parentage(
            context=rebanho.context,
            offspring_id=bezerro,
            parent_id=progenitor,
            role=papel,
            occurred_at=ONTEM,
            confidence=ParentageConfidence.DECLARADO,
        )


def test_o_progenitor_precisa_ter_nascido_antes(rebanho: Rebanho) -> None:
    bezerro = rebanho.animal(AnimalSex.MALE, date(2020, 1, 1))
    vaca = rebanho.animal(AnimalSex.FEMALE, date(2024, 1, 1))

    with pytest.raises(ParentescoInvalido):
        rebanho.maternidade(bezerro, vaca)


def test_sem_data_de_nascimento_a_conferencia_nao_e_inventada(rebanho: Rebanho) -> None:
    bezerro = rebanho.animal(AnimalSex.MALE, date(2020, 1, 1))
    vaca = rebanho.animal(AnimalSex.FEMALE)

    rebanho.maternidade(bezerro, vaca)

    assert len(rebanho.service.parents_of(rebanho.organization_id, bezerro)) == 2


def test_um_animal_nao_e_progenitor_de_si_mesmo(rebanho: Rebanho) -> None:
    vaca = rebanho.animal(AnimalSex.FEMALE)

    with pytest.raises(ParentescoInvalido):
        rebanho.maternidade(vaca, vaca)


def test_o_ciclo_direto_e_barrado(rebanho: Rebanho) -> None:
    mae = rebanho.animal(AnimalSex.FEMALE)
    filha = rebanho.animal(AnimalSex.FEMALE)
    rebanho.maternidade(filha, mae)

    with pytest.raises(ParentescoInvalido):
        rebanho.maternidade(mae, filha)


def test_animal_de_outra_organizacao_nao_e_alcancado(rebanho: Rebanho) -> None:
    bezerro = rebanho.animal(AnimalSex.MALE)

    with pytest.raises(KeyError):
        rebanho.maternidade(bezerro, TypedId.new("animal"))


def test_o_futuro_nao_e_aceito(rebanho: Rebanho) -> None:
    bezerro = rebanho.animal(AnimalSex.MALE)
    vaca = rebanho.animal(AnimalSex.FEMALE)

    with pytest.raises(ParentescoInvalido):
        rebanho.service.register_maternity(
            context=rebanho.context,
            offspring_id=bezerro,
            genetic_mother_id=vaca,
            occurred_at=datetime.now(UTC) + timedelta(days=1),
            confidence=ParentageConfidence.DECLARADO,
        )


def test_a_confianca_viaja_de_volta_no_vocabulario_da_vertical(rebanho: Rebanho) -> None:
    """Quem opera nunca vê `VERIFIED_SOURCE`: a tradução fica na fronteira."""
    bezerro = rebanho.animal(AnimalSex.MALE)
    touro = rebanho.animal(AnimalSex.MALE)
    rebanho.paternidade(bezerro, touro, ParentageConfidence.VERIFICADO_EM_FONTE)

    link = rebanho.service.parents_of(rebanho.organization_id, bezerro)[0]

    assert link.confidence is ParentageConfidence.VERIFICADO_EM_FONTE
    assert "DNA" in link.confidence_reason


def test_a_genealogia_de_animal_que_saiu_continua_registravel(rebanho: Rebanho) -> None:
    """A guarda de saída não vale aqui: parentesco é fato anterior ao nascimento.

    Descobrir a mãe de um boi já abatido é a regularização que a decisão D-2
    protege, e é o que uma auditoria pós-abate faz.
    """
    from packages.livestock_domain.exit import AnimalExit, ExitType

    bezerro = rebanho.animal(AnimalSex.MALE)
    vaca = rebanho.animal(AnimalSex.FEMALE)
    rebanho.animals._saidas.save(
        AnimalExit(
            exit_id=TypedId.new("animal_exit"),
            organization_id=rebanho.organization_id,
            animal_id=bezerro,
            exit_type=ExitType.ABATE,
            occurred_at=ONTEM - timedelta(days=10),
        )
    )

    rebanho.maternidade(bezerro, vaca)

    assert len(rebanho.service.parents_of(rebanho.organization_id, bezerro)) == 2


def test_relacao_de_outra_natureza_nao_vira_parentesco(rebanho: Rebanho) -> None:
    """A tabela `relations` é do Core e guarda vínculos de toda espécie."""
    from packages.core_domain.evidence import ConfidenceLevel, ConfidenceTier
    from packages.core_domain.relations import UniversalRelation
    from packages.shared_kernel import UniversalReference

    bezerro = rebanho.animal(AnimalSex.MALE)
    outro = rebanho.animal(AnimalSex.MALE)
    rebanho.relations.save(
        UniversalRelation.create(
            organization_id=rebanho.organization_id,
            source_reference=UniversalReference(
                target_id=outro, organization_id=rebanho.organization_id, contract_version=1
            ),
            target_reference=UniversalReference(
                target_id=bezerro, organization_id=rebanho.organization_id, contract_version=1
            ),
            relation_type="livestock.pastoreia_com",
            created_at=datetime.now(UTC),
            confidence=ConfidenceLevel(tier=ConfidenceTier.INFORMED, reason="qualquer"),
        )
    )

    assert rebanho.service.parents_of(rebanho.organization_id, bezerro) == ()


def test_os_tipos_de_relacao_sao_os_canonicos_do_core(rebanho: Rebanho) -> None:
    bezerro = rebanho.animal(AnimalSex.MALE)
    touro = rebanho.animal(AnimalSex.MALE)

    relacao = rebanho.service.register_parentage(
        context=rebanho.context,
        offspring_id=bezerro,
        parent_id=touro,
        role=ParentageRole.PAI,
        occurred_at=ONTEM,
        confidence=ParentageConfidence.DECLARADO,
    )

    assert relacao.relation_type == FATHER_OF
