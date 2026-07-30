"""Fan-in real de desossa (ADR-0046, Passo 11.6).

O que estes testes protegem: o contrato aceita N=1 saída, mas o cenário
validado é o fan-in -- abaixo de duas entradas o serviço recusa. O perfil do
processo (item 6 da ADR) decide quem pode ser entrada de DEBONING, não o
Core: só CARCASS/HALF_CARCASS. E a projeção em estrela (item 5) preserva o
conjunto de origens sem inventar correspondência 1:1 (invariante 15) -- a
prova real está no roteiro executável, contra o RecallService de verdade;
aqui o que se prova é que o serviço grava as duas entradas corretamente.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from packages.core_application.relation_service import RelationService
from packages.livestock_application.event_recorder import (
    LivestockEventRecorder,
    LivestockOperationContext,
)
from packages.livestock_application.transformation_service import (
    AlvoDeCorrecaoNaoEhVigente,
    DeboningInputSpec,
    DeboningService,
    ItemDeTipoInvalido,
    ItemJaConsumido,
    ParticipantRole,
    SaidaConsumidaAJusante,
    SlaughterService,
    TransformationOutputSpec,
)
from packages.livestock_domain.animal import Animal, AnimalSex
from packages.livestock_domain.events import TRANSFORMATION_EVENT_RECORDED
from packages.livestock_domain.exit import AnimalExit, ExitType
from packages.livestock_domain.property import RuralProperty
from packages.livestock_domain.transformation import (
    BalanceResult,
    BalanceStatus,
    TraceableItemType,
)
from packages.shared_kernel import OrganizationId, TypedId
from tests.livestock_application.conftest import FakeEventLog
from tests.livestock_application.test_exit_service import InMemoryAnimalRepo, InMemoryExitRepo
from tests.livestock_application.test_slaughter_service import (
    InMemoryEventRepo,
    InMemoryItemRepo,
    InMemoryLockPort,
    InMemoryPropertyRepo,
)
from tests.livestock_support import FakeRelationRepository, operation_context

ONTEM = datetime.now(UTC) - timedelta(days=1)


class Cenario:
    """Um animal já desdobrado em duas meias-carcaças, pronto para a desossa."""

    def __init__(
        self, recorder: LivestockEventRecorder, context: LivestockOperationContext
    ) -> None:
        self.context = context
        self.organization_id = context.organization_id
        self.exits = InMemoryExitRepo()
        self.animals = InMemoryAnimalRepo(self.exits)
        self.properties = InMemoryPropertyRepo()
        self.relations = FakeRelationRepository()
        self.events = InMemoryEventRepo()
        self.items = InMemoryItemRepo()
        self.relation_service = RelationService(repository=self.relations)
        self.lock_port = InMemoryLockPort(self.events, self.items, self.animals)

        self.slaughter_service = SlaughterService(
            event_repository=self.events,
            item_repository=self.items,
            animal_repository=self.animals,
            exit_repository=self.exits,
            property_repository=self.properties,
            relation_service=self.relation_service,
            recorder=recorder,
            lock_port=self.lock_port,
        )
        self.service = DeboningService(
            event_repository=self.events,
            item_repository=self.items,
            property_repository=self.properties,
            relation_service=self.relation_service,
            recorder=recorder,
            lock_port=self.lock_port,
        )

        self.facility_id = self._nova_propriedade()
        self.half_carcass_1, self.half_carcass_2 = self._abater_animal()

    def _nova_propriedade(self) -> TypedId:
        propriedade = RuralProperty(
            property_id=TypedId.new("rural_property"),
            organization_id=self.organization_id,
            code="FRIG-001",
            name="Frigorífico Central",
            municipality="Barretos",
            state_code="SP",
        )
        self.properties.save(propriedade)
        return propriedade.property_id

    def _abater_animal(self) -> tuple[TypedId, TypedId]:
        animal = Animal(
            animal_id=TypedId.new("animal"),
            organization_id=self.organization_id,
            birth_property_id=TypedId.new("rural_property"),
            sex=AnimalSex.MALE,
        )
        self.animals.save(animal)
        self.exits.save(
            AnimalExit(
                exit_id=TypedId.new("animal_exit"),
                organization_id=self.organization_id,
                animal_id=animal.animal_id,
                exit_type=ExitType.ABATE,
                occurred_at=ONTEM,
            )
        )
        resultado = self.slaughter_service.register_slaughter(
            context=self.context,
            animal_id=animal.animal_id,
            facility_property_id=self.facility_id,
            occurred_at=ONTEM + timedelta(hours=1),
            outputs=(
                TransformationOutputSpec(
                    item_type=TraceableItemType.HALF_CARCASS,
                    quantity=Decimal("150"),
                    unit="kg",
                    measurement_basis="peso liquido",
                ),
                TransformationOutputSpec(
                    item_type=TraceableItemType.HALF_CARCASS,
                    quantity=Decimal("150"),
                    unit="kg",
                    measurement_basis="peso liquido",
                ),
            ),
        )
        item_1, item_2 = resultado.created_items
        return item_1.item_id, item_2.item_id

    def entradas(self, quantidade_cada: Decimal = Decimal("150")) -> tuple[DeboningInputSpec, ...]:
        return (
            DeboningInputSpec(
                item_id=self.half_carcass_1,
                quantity=quantidade_cada,
                unit="kg",
                measurement_basis="peso liquido",
            ),
            DeboningInputSpec(
                item_id=self.half_carcass_2,
                quantity=quantidade_cada,
                unit="kg",
                measurement_basis="peso liquido",
            ),
        )

    def saidas(self) -> tuple[TransformationOutputSpec, ...]:
        return (
            TransformationOutputSpec(
                item_type=TraceableItemType.CUT_BATCH,
                quantity=Decimal("200"),
                unit="kg",
                measurement_basis="peso liquido",
                label="corte-primeira",
            ),
            TransformationOutputSpec(
                item_type=TraceableItemType.TRIM_BATCH,
                quantity=Decimal("100"),
                unit="kg",
                measurement_basis="peso liquido",
                label="apara",
            ),
        )


def test_registra_deboning_com_fan_in(
    recorder: LivestockEventRecorder,
    event_log: FakeEventLog,
    context: LivestockOperationContext,
) -> None:
    cenario = Cenario(recorder, context)

    resultado = cenario.service.register_deboning(
        context=context,
        facility_property_id=cenario.facility_id,
        occurred_at=ONTEM + timedelta(hours=2),
        inputs=cenario.entradas(),
        outputs=cenario.saidas(),
    )

    assert len(resultado.event.inputs) == 2
    assert len(resultado.created_items) == 2
    assert all(p.role is ParticipantRole.INPUT for p in resultado.event.inputs)
    assert all(p.role is ParticipantRole.OUTPUT for p in resultado.event.outputs)

    tipos_das_entradas = {p.subject_reference.target_id for p in resultado.event.inputs}
    assert tipos_das_entradas == {cenario.half_carcass_1, cenario.half_carcass_2}

    evento = event_log.of_type(TRANSFORMATION_EVENT_RECORDED)[-1]
    assert evento.aggregate_reference.target_id == resultado.event.event_id

    # Projeção em estrela: cada entrada já tinha uma relação output_of (criada
    # pelo SLAUGHTER anterior) e ganha agora uma input_of (consumida por este
    # DEBONING) -- as duas apontam para eventos diferentes, nunca uma para a
    # outra.
    for item_id in (cenario.half_carcass_1, cenario.half_carcass_2):
        relacoes_da_entrada = cenario.relations.list_outgoing(cenario.organization_id, item_id)
        tipos = {r.relation_type for r in relacoes_da_entrada}
        assert tipos == {"transformation.output_of", "transformation.input_of"}


def test_recusa_fan_in_menor_que_dois(
    recorder: LivestockEventRecorder, context: LivestockOperationContext
) -> None:
    cenario = Cenario(recorder, context)

    with pytest.raises(ValueError, match="ao menos 2 entradas"):
        cenario.service.register_deboning(
            context=context,
            facility_property_id=cenario.facility_id,
            occurred_at=ONTEM + timedelta(hours=2),
            inputs=cenario.entradas()[:1],
            outputs=cenario.saidas(),
        )


def test_recusa_sem_nenhuma_saida(
    recorder: LivestockEventRecorder, context: LivestockOperationContext
) -> None:
    cenario = Cenario(recorder, context)

    with pytest.raises(ValueError, match="ao menos uma saída"):
        cenario.service.register_deboning(
            context=context,
            facility_property_id=cenario.facility_id,
            occurred_at=ONTEM + timedelta(hours=2),
            inputs=cenario.entradas(),
            outputs=(),
        )


def test_recusa_entrada_duplicada(
    recorder: LivestockEventRecorder, context: LivestockOperationContext
) -> None:
    cenario = Cenario(recorder, context)
    duplicada = (cenario.entradas()[0], cenario.entradas()[0])

    with pytest.raises(ValueError, match="entrada duplicada"):
        cenario.service.register_deboning(
            context=context,
            facility_property_id=cenario.facility_id,
            occurred_at=ONTEM + timedelta(hours=2),
            inputs=duplicada,
            outputs=cenario.saidas(),
        )


def test_recusa_item_de_tipo_nao_permitido(
    recorder: LivestockEventRecorder, context: LivestockOperationContext
) -> None:
    """DEBONING só aceita CARCASS/HALF_CARCASS como entrada (item 6 da ADR)."""
    cenario = Cenario(recorder, context)
    outro_resultado = cenario.service.register_deboning(
        context=context,
        facility_property_id=cenario.facility_id,
        occurred_at=ONTEM + timedelta(hours=2),
        inputs=cenario.entradas(),
        outputs=cenario.saidas(),
    )
    cut_batch_id = outro_resultado.created_items[0].item_id

    with pytest.raises(ItemDeTipoInvalido, match="não aceita"):
        cenario.service.register_deboning(
            context=context,
            facility_property_id=cenario.facility_id,
            occurred_at=ONTEM + timedelta(hours=3),
            inputs=(
                DeboningInputSpec(item_id=cut_batch_id),
                DeboningInputSpec(item_id=TypedId.new("traceable_item")),
            ),
            outputs=cenario.saidas(),
        )


def test_item_nao_pode_ser_consumido_duas_vezes(
    recorder: LivestockEventRecorder, context: LivestockOperationContext
) -> None:
    cenario = Cenario(recorder, context)
    cenario.service.register_deboning(
        context=context,
        facility_property_id=cenario.facility_id,
        occurred_at=ONTEM + timedelta(hours=2),
        inputs=cenario.entradas(),
        outputs=cenario.saidas(),
    )

    novo_terceiro_animal_service = cenario.slaughter_service
    animal = Animal(
        animal_id=TypedId.new("animal"),
        organization_id=cenario.organization_id,
        birth_property_id=TypedId.new("rural_property"),
        sex=AnimalSex.MALE,
    )
    cenario.animals.save(animal)
    cenario.exits.save(
        AnimalExit(
            exit_id=TypedId.new("animal_exit"),
            organization_id=cenario.organization_id,
            animal_id=animal.animal_id,
            exit_type=ExitType.ABATE,
            occurred_at=ONTEM,
        )
    )
    novo_resultado = novo_terceiro_animal_service.register_slaughter(
        context=context,
        animal_id=animal.animal_id,
        facility_property_id=cenario.facility_id,
        occurred_at=ONTEM + timedelta(hours=1),
        outputs=(
            TransformationOutputSpec(item_type=TraceableItemType.HALF_CARCASS),
            TransformationOutputSpec(item_type=TraceableItemType.HALF_CARCASS),
        ),
    )
    novo_item = novo_resultado.created_items[0].item_id

    with pytest.raises(ItemJaConsumido, match="já foi utilizado"):
        cenario.service.register_deboning(
            context=context,
            facility_property_id=cenario.facility_id,
            occurred_at=ONTEM + timedelta(hours=4),
            inputs=(
                DeboningInputSpec(item_id=cenario.half_carcass_1),
                DeboningInputSpec(item_id=novo_item),
            ),
            outputs=cenario.saidas(),
        )


def test_balanco_soma_as_duas_entradas(
    recorder: LivestockEventRecorder, context: LivestockOperationContext
) -> None:
    cenario = Cenario(recorder, context)

    resultado = cenario.service.register_deboning(
        context=context,
        facility_property_id=cenario.facility_id,
        occurred_at=ONTEM + timedelta(hours=2),
        inputs=cenario.entradas(quantidade_cada=Decimal("150")),
        outputs=cenario.saidas(),
    )

    assert resultado.event.balance is not None
    assert resultado.event.balance.status is BalanceStatus.ASSESSED
    assert resultado.event.balance.result is BalanceResult.BALANCED
    assert resultado.event.balance.input_total == Decimal("300")
    assert resultado.event.balance.output_total == Decimal("300")


def test_item_de_outra_organizacao_nao_e_alcancado(
    recorder: LivestockEventRecorder, context: LivestockOperationContext
) -> None:
    cenario = Cenario(recorder, context)
    intruso = operation_context(OrganizationId.new())

    with pytest.raises(KeyError, match="não encontrad"):
        cenario.service.register_deboning(
            context=intruso,
            facility_property_id=cenario.facility_id,
            occurred_at=ONTEM + timedelta(hours=2),
            inputs=cenario.entradas(),
            outputs=cenario.saidas(),
        )


def test_evento_gravado_tem_todas_as_entradas(
    recorder: LivestockEventRecorder, context: LivestockOperationContext
) -> None:
    cenario = Cenario(recorder, context)

    resultado = cenario.service.register_deboning(
        context=context,
        facility_property_id=cenario.facility_id,
        occurred_at=ONTEM + timedelta(hours=2),
        inputs=cenario.entradas(),
        outputs=cenario.saidas(),
    )

    persistido = cenario.events.get_by_id(resultado.event.event_id)
    assert persistido is not None
    assert len(persistido.inputs) == 2
    entradas_persistidas = {p.subject_reference.target_id for p in persistido.inputs}
    assert entradas_persistidas == {cenario.half_carcass_1, cenario.half_carcass_2}


class TestCorrecaoDeDeboning:
    """ADR-0047, Passo 11.7: correção de TransformationEvent(DEBONING) publicado."""

    def test_corrige_reafirmando_as_mesmas_entradas(
        self, recorder: LivestockEventRecorder, context: LivestockOperationContext
    ) -> None:
        cenario = Cenario(recorder, context)
        original = cenario.service.register_deboning(
            context=context,
            facility_property_id=cenario.facility_id,
            occurred_at=ONTEM + timedelta(hours=2),
            inputs=cenario.entradas(),
            outputs=cenario.saidas(),
        )

        correcao = cenario.service.correct_deboning(
            context=context,
            corrects_transformation_id=original.event.event_id,
            correction_reason="Peso de saída lançado errado no apontamento original.",
            facility_property_id=cenario.facility_id,
            occurred_at=ONTEM + timedelta(hours=2),
            inputs=cenario.entradas(),
            outputs=cenario.saidas(),
        )

        assert correcao.event.corrects_transformation_id == original.event.event_id
        assert cenario.events.get_by_id(original.event.event_id) == original.event

    def test_recusa_corrigir_evento_que_ja_nao_e_o_leaf(
        self, recorder: LivestockEventRecorder, context: LivestockOperationContext
    ) -> None:
        cenario = Cenario(recorder, context)
        original = cenario.service.register_deboning(
            context=context,
            facility_property_id=cenario.facility_id,
            occurred_at=ONTEM + timedelta(hours=2),
            inputs=cenario.entradas(),
            outputs=cenario.saidas(),
        )
        cenario.service.correct_deboning(
            context=context,
            corrects_transformation_id=original.event.event_id,
            correction_reason="Primeira correção.",
            facility_property_id=cenario.facility_id,
            occurred_at=ONTEM + timedelta(hours=2),
            inputs=cenario.entradas(),
            outputs=cenario.saidas(),
        )

        with pytest.raises(AlvoDeCorrecaoNaoEhVigente, match="leaf atual"):
            cenario.service.correct_deboning(
                context=context,
                corrects_transformation_id=original.event.event_id,
                correction_reason="Tentativa de bifurcar a cadeia.",
                facility_property_id=cenario.facility_id,
                occurred_at=ONTEM + timedelta(hours=2),
                inputs=cenario.entradas(),
                outputs=cenario.saidas(),
            )

    def test_recusa_corrigir_slaughter_cuja_saida_ja_foi_desossada(
        self, recorder: LivestockEventRecorder, context: LivestockOperationContext
    ) -> None:
        """ADR-0047, item 9: o DEBONING do cenário já consumiu as duas saídas."""
        cenario = Cenario(recorder, context)
        cenario.service.register_deboning(
            context=context,
            facility_property_id=cenario.facility_id,
            occurred_at=ONTEM + timedelta(hours=2),
            inputs=cenario.entradas(),
            outputs=cenario.saidas(),
        )

        item_persistido = cenario.items.get_by_id(cenario.half_carcass_1)
        assert item_persistido is not None
        slaughter_original_id = item_persistido.created_by_transformation_id
        assert slaughter_original_id is not None
        slaughter_original = cenario.events.get_by_id(slaughter_original_id)
        assert slaughter_original is not None
        animal_original_id = slaughter_original.inputs[0].subject_reference.target_id

        with pytest.raises(SaidaConsumidaAJusante, match="consumida por uma transformação"):
            cenario.slaughter_service.correct_slaughter(
                context=context,
                corrects_transformation_id=slaughter_original_id,
                correction_reason="Tentativa de corrigir origem já desossada.",
                animal_id=animal_original_id,
                facility_property_id=cenario.facility_id,
                occurred_at=ONTEM + timedelta(hours=1),
                outputs=(
                    TransformationOutputSpec(item_type=TraceableItemType.HALF_CARCASS),
                    TransformationOutputSpec(item_type=TraceableItemType.HALF_CARCASS),
                ),
            )

    def test_entrada_removida_por_correcao_volta_a_ficar_disponivel(
        self, recorder: LivestockEventRecorder, context: LivestockOperationContext
    ) -> None:
        cenario = Cenario(recorder, context)
        original = cenario.service.register_deboning(
            context=context,
            facility_property_id=cenario.facility_id,
            occurred_at=ONTEM + timedelta(hours=2),
            inputs=cenario.entradas(),
            outputs=cenario.saidas(),
        )
        animal_extra = Animal(
            animal_id=TypedId.new("animal"),
            organization_id=cenario.organization_id,
            birth_property_id=TypedId.new("rural_property"),
            sex=AnimalSex.MALE,
        )
        cenario.animals.save(animal_extra)
        cenario.exits.save(
            AnimalExit(
                exit_id=TypedId.new("animal_exit"),
                organization_id=cenario.organization_id,
                animal_id=animal_extra.animal_id,
                exit_type=ExitType.ABATE,
                occurred_at=ONTEM,
            )
        )
        abate_extra = cenario.slaughter_service.register_slaughter(
            context=context,
            animal_id=animal_extra.animal_id,
            facility_property_id=cenario.facility_id,
            occurred_at=ONTEM + timedelta(hours=1),
            outputs=(
                TransformationOutputSpec(item_type=TraceableItemType.HALF_CARCASS),
                TransformationOutputSpec(item_type=TraceableItemType.HALF_CARCASS),
            ),
        )
        novo_item = abate_extra.created_items[0].item_id

        cenario.service.correct_deboning(
            context=context,
            corrects_transformation_id=original.event.event_id,
            correction_reason="Uma das meias-carcaças entrou por engano.",
            facility_property_id=cenario.facility_id,
            occurred_at=ONTEM + timedelta(hours=2),
            inputs=(
                cenario.entradas()[0],
                DeboningInputSpec(
                    item_id=novo_item,
                    quantity=Decimal("150"),
                    unit="kg",
                    measurement_basis="peso liquido",
                ),
            ),
            outputs=cenario.saidas(),
        )

        resultado = cenario.service.register_deboning(
            context=context,
            facility_property_id=cenario.facility_id,
            occurred_at=ONTEM + timedelta(hours=3),
            inputs=(
                DeboningInputSpec(
                    item_id=cenario.half_carcass_2,
                    quantity=Decimal("150"),
                    unit="kg",
                    measurement_basis="peso liquido",
                ),
                DeboningInputSpec(
                    item_id=abate_extra.created_items[1].item_id,
                    quantity=Decimal("150"),
                    unit="kg",
                    measurement_basis="peso liquido",
                ),
            ),
            outputs=cenario.saidas(),
        )

        assert resultado.event.inputs[0].subject_reference.target_id == cenario.half_carcass_2
