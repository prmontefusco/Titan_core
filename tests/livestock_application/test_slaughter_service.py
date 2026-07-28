"""Fan-out real de abate (ADR-0046, Passo 11.2).

O que estes testes protegem: o contrato aceita N=1 entrada, mas o cenário
validado é o fan-out — abaixo de duas saídas o serviço recusa. E a fronteira
de Organization (item 9 da ADR) continua fechada mesmo para um conceito novo:
animal, propriedade e evidência de outro tenant nunca são alcançados.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Protocol

import pytest

from packages.core_application.relation_service import RelationService
from packages.livestock_application.event_recorder import (
    LivestockEventRecorder,
    LivestockOperationContext,
)
from packages.livestock_application.transformation_service import (
    AlvoDeCorrecaoNaoEhVigente,
    AnimalJaTransformado,
    AnimalNaoAbatido,
    SlaughterService,
    TraceableItemRepositoryPort,
    TransformationEventRepositoryPort,
    TransformationLockPort,
    TransformationOutputSpec,
    operational_status_now,
)
from packages.livestock_domain.animal import Animal, AnimalSex
from packages.livestock_domain.events import TRANSFORMATION_EVENT_RECORDED
from packages.livestock_domain.exit import AnimalExit, ExitType
from packages.livestock_domain.property import RuralProperty
from packages.livestock_domain.transformation import (
    BalanceResult,
    BalanceStatus,
    ParticipantRole,
    ProcessType,
    TraceableItem,
    TraceableItemType,
    TransformationEvent,
    TransformationParticipant,
    TransformationStatus,
)
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference
from tests.livestock_application.conftest import FakeEventLog
from tests.livestock_application.test_exit_service import InMemoryAnimalRepo, InMemoryExitRepo
from tests.livestock_support import FakeRelationRepository, operation_context

ONTEM = datetime.now(UTC) - timedelta(days=1)


class InMemoryEventRepo(TransformationEventRepositoryPort):
    def __init__(self) -> None:
        self.events: dict[str, TransformationEvent] = {}

    def save(self, event: TransformationEvent) -> None:
        self.events[event.event_id.value.hex] = event

    def get_by_id(self, event_id: TypedId) -> TransformationEvent | None:
        return self.events.get(event_id.value.hex)

    def get_correction_of(self, event_id: TypedId) -> TransformationEvent | None:
        for event in self.events.values():
            if (
                event.corrects_transformation_id is not None
                and event.corrects_transformation_id.value == event_id.value
            ):
                return event
        return None


class InMemoryItemRepo(TraceableItemRepositoryPort):
    def __init__(self) -> None:
        self.items: dict[str, TraceableItem] = {}

    def save(self, item: TraceableItem) -> None:
        self.items[item.item_id.value.hex] = item

    def get_by_id(self, item_id: TypedId) -> TraceableItem | None:
        return self.items.get(item_id.value.hex)


class _BuscavelPorId(Protocol):
    """Qualquer fake com `get_by_id(TypedId) -> objeto | None` serve.

    Vários testes usam fakes de animal diferentes (`InMemoryAnimalRepo` aqui,
    `InMemoryAnimalRepository` em outros módulos) — o lock fake não precisa da
    identidade exata da classe, só da forma.
    """

    def get_by_id(self, entity_id: TypedId) -> object | None: ...


class InMemoryLockPort(TransformationLockPort):
    """Fake sem concorrência real: só espelha o contrato existe/não-existe.

    Testes de domínio/aplicação rodam em um único thread contra repositórios
    em memória — o bloqueio pessimista de verdade (SELECT ... FOR UPDATE) só
    faz sentido contra Postgres real (ver
    tests/integration/test_transformation_locking_postgresql.py).
    """

    def __init__(
        self,
        events: _BuscavelPorId,
        items: _BuscavelPorId,
        animals: _BuscavelPorId,
    ) -> None:
        self.events = events
        self.items = items
        self.animals = animals

    def lock_transformation_event(self, event_id: TypedId) -> bool:
        return self.events.get_by_id(event_id) is not None

    def lock_traceable_item(self, item_id: TypedId) -> bool:
        return self.items.get_by_id(item_id) is not None

    def lock_animal(self, animal_id: TypedId) -> bool:
        return self.animals.get_by_id(animal_id) is not None


class InMemoryPropertyRepo:
    def __init__(self) -> None:
        self.properties: dict[str, RuralProperty] = {}

    def save(self, property: RuralProperty) -> None:
        self.properties[property.property_id.value.hex] = property

    def get_by_id(self, property_id: TypedId) -> RuralProperty | None:
        return self.properties.get(property_id.value.hex)

    def get_by_code(self, organization_id: OrganizationId, code: str) -> RuralProperty | None:
        return None

    def list_by_organization(
        self, organization_id: OrganizationId, limit: int = 50, offset: int = 0
    ) -> list[RuralProperty]:
        return [
            item for item in self.properties.values() if item.organization_id == organization_id
        ]


class Cenario:
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
        self.service = SlaughterService(
            event_repository=self.events,
            item_repository=self.items,
            animal_repository=self.animals,
            exit_repository=self.exits,
            property_repository=self.properties,
            relation_service=RelationService(repository=self.relations),
            recorder=recorder,
            lock_port=InMemoryLockPort(self.events, self.items, self.animals),
        )
        self.animal_id = self._novo_animal()
        self.facility_id = self._nova_propriedade()

    def _novo_animal(self) -> TypedId:
        animal = Animal(
            animal_id=TypedId.new("animal"),
            organization_id=self.organization_id,
            birth_property_id=TypedId.new("rural_property"),
            sex=AnimalSex.MALE,
        )
        self.animals.save(animal)
        return animal.animal_id

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

    def abater(
        self, animal_id: TypedId | None = None, exit_type: ExitType = ExitType.ABATE
    ) -> None:
        self.exits.save(
            AnimalExit(
                exit_id=TypedId.new("animal_exit"),
                organization_id=self.organization_id,
                animal_id=animal_id or self.animal_id,
                exit_type=exit_type,
                occurred_at=ONTEM,
            )
        )

    def outputs(self, quantidade: int = 2) -> tuple[TransformationOutputSpec, ...]:
        return tuple(
            TransformationOutputSpec(
                item_type=TraceableItemType.HALF_CARCASS,
                quantity=Decimal("110.5"),
                unit="kg",
                measurement_basis="peso líquido pós-sangria",
                label=f"HC-{indice}",
            )
            for indice in range(quantidade)
        )


def test_registra_slaughter_com_fan_out(
    recorder: LivestockEventRecorder,
    event_log: FakeEventLog,
    context: LivestockOperationContext,
) -> None:
    cenario = Cenario(recorder, context)
    cenario.abater()

    resultado = cenario.service.register_slaughter(
        context=context,
        animal_id=cenario.animal_id,
        facility_property_id=cenario.facility_id,
        occurred_at=ONTEM + timedelta(hours=1),
        outputs=cenario.outputs(2),
    )

    assert len(resultado.created_items) == 2
    assert resultado.event.inputs[0].subject_reference.target_id == cenario.animal_id
    for item in resultado.created_items:
        assert item.created_by_transformation_id == resultado.event.event_id
        assert cenario.items.get_by_id(item.item_id) is not None

    evento = event_log.only(TRANSFORMATION_EVENT_RECORDED)
    assert evento.aggregate_reference.target_id == resultado.event.event_id

    # Projeção: uma relação input_of e duas output_of.
    entradas = cenario.relations.list_outgoing(cenario.organization_id, cenario.animal_id)
    assert len(entradas) == 1
    assert entradas[0].relation_type == "transformation.input_of"
    for item in resultado.created_items:
        saidas = cenario.relations.list_outgoing(cenario.organization_id, item.item_id)
        assert len(saidas) == 1
        assert saidas[0].relation_type == "transformation.output_of"


def test_recusa_fan_out_menor_que_dois(
    recorder: LivestockEventRecorder, context: LivestockOperationContext
) -> None:
    cenario = Cenario(recorder, context)
    cenario.abater()

    with pytest.raises(ValueError, match="ao menos 2 saídas"):
        cenario.service.register_slaughter(
            context=context,
            animal_id=cenario.animal_id,
            facility_property_id=cenario.facility_id,
            occurred_at=ONTEM + timedelta(hours=1),
            outputs=cenario.outputs(1),
        )


def test_recusa_sem_saida_por_abate_registrada(
    recorder: LivestockEventRecorder, context: LivestockOperationContext
) -> None:
    cenario = Cenario(recorder, context)

    with pytest.raises(AnimalNaoAbatido, match="ABATE"):
        cenario.service.register_slaughter(
            context=context,
            animal_id=cenario.animal_id,
            facility_property_id=cenario.facility_id,
            occurred_at=ONTEM + timedelta(hours=1),
            outputs=cenario.outputs(2),
        )


def test_recusa_saida_por_venda_em_vez_de_abate(
    recorder: LivestockEventRecorder, context: LivestockOperationContext
) -> None:
    cenario = Cenario(recorder, context)
    cenario.abater(exit_type=ExitType.VENDA)

    with pytest.raises(AnimalNaoAbatido, match="ABATE"):
        cenario.service.register_slaughter(
            context=context,
            animal_id=cenario.animal_id,
            facility_property_id=cenario.facility_id,
            occurred_at=ONTEM + timedelta(hours=1),
            outputs=cenario.outputs(2),
        )


def test_recusa_transformacao_anterior_a_saida(
    recorder: LivestockEventRecorder, context: LivestockOperationContext
) -> None:
    cenario = Cenario(recorder, context)
    cenario.abater()

    with pytest.raises(ValueError, match="anterior à saída"):
        cenario.service.register_slaughter(
            context=context,
            animal_id=cenario.animal_id,
            facility_property_id=cenario.facility_id,
            occurred_at=ONTEM - timedelta(hours=1),
            outputs=cenario.outputs(2),
        )


def test_animal_nao_pode_ser_transformado_duas_vezes(
    recorder: LivestockEventRecorder, context: LivestockOperationContext
) -> None:
    cenario = Cenario(recorder, context)
    cenario.abater()
    cenario.service.register_slaughter(
        context=context,
        animal_id=cenario.animal_id,
        facility_property_id=cenario.facility_id,
        occurred_at=ONTEM + timedelta(hours=1),
        outputs=cenario.outputs(2),
    )

    with pytest.raises(AnimalJaTransformado, match="já foi utilizado"):
        cenario.service.register_slaughter(
            context=context,
            animal_id=cenario.animal_id,
            facility_property_id=cenario.facility_id,
            occurred_at=ONTEM + timedelta(hours=2),
            outputs=cenario.outputs(2),
        )


def test_animal_de_outra_organizacao_nao_e_alcancado(
    recorder: LivestockEventRecorder, context: LivestockOperationContext
) -> None:
    cenario = Cenario(recorder, context)
    cenario.abater()
    intruso = operation_context(OrganizationId.new())

    with pytest.raises(KeyError, match="não encontrado"):
        cenario.service.register_slaughter(
            context=intruso,
            animal_id=cenario.animal_id,
            facility_property_id=cenario.facility_id,
            occurred_at=ONTEM + timedelta(hours=1),
            outputs=cenario.outputs(2),
        )


def test_propriedade_de_outra_organizacao_nao_e_alcancada(
    recorder: LivestockEventRecorder, context: LivestockOperationContext
) -> None:
    cenario = Cenario(recorder, context)
    cenario.abater()
    outra_organizacao_propriedade = RuralProperty(
        property_id=TypedId.new("rural_property"),
        organization_id=OrganizationId.new(),
        code="FORA-001",
        name="Fora",
        municipality="Outra Cidade",
        state_code="MG",
    )
    cenario.properties.save(outra_organizacao_propriedade)

    with pytest.raises(KeyError, match="não encontrada"):
        cenario.service.register_slaughter(
            context=context,
            animal_id=cenario.animal_id,
            facility_property_id=outra_organizacao_propriedade.property_id,
            occurred_at=ONTEM + timedelta(hours=1),
            outputs=cenario.outputs(2),
        )


def test_evento_gravado_tem_participantes_com_papeis_corretos(
    recorder: LivestockEventRecorder, context: LivestockOperationContext
) -> None:
    cenario = Cenario(recorder, context)
    cenario.abater()

    resultado = cenario.service.register_slaughter(
        context=context,
        animal_id=cenario.animal_id,
        facility_property_id=cenario.facility_id,
        occurred_at=ONTEM + timedelta(hours=1),
        outputs=cenario.outputs(2),
    )

    persistido = cenario.events.get_by_id(resultado.event.event_id)
    assert persistido is not None
    assert all(p.role is ParticipantRole.INPUT for p in persistido.inputs)
    assert all(p.role is ParticipantRole.OUTPUT for p in persistido.outputs)


def test_sem_peso_de_entrada_o_balanco_persistido_e_not_assessed(
    recorder: LivestockEventRecorder, context: LivestockOperationContext
) -> None:
    """ADR-0046, Passo 11.4: ausência de peso nunca vira zero por omissão."""
    cenario = Cenario(recorder, context)
    cenario.abater()

    resultado = cenario.service.register_slaughter(
        context=context,
        animal_id=cenario.animal_id,
        facility_property_id=cenario.facility_id,
        occurred_at=ONTEM + timedelta(hours=1),
        outputs=cenario.outputs(2),
    )

    persistido = cenario.events.get_by_id(resultado.event.event_id)
    assert persistido is not None
    assert persistido.balance is not None
    assert persistido.balance.status is BalanceStatus.NOT_ASSESSED


def test_com_peso_de_entrada_o_balanco_calculado_e_persistido(
    recorder: LivestockEventRecorder, context: LivestockOperationContext
) -> None:
    cenario = Cenario(recorder, context)
    cenario.abater()
    saidas = (
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
    )

    resultado = cenario.service.register_slaughter(
        context=context,
        animal_id=cenario.animal_id,
        facility_property_id=cenario.facility_id,
        occurred_at=ONTEM + timedelta(hours=1),
        outputs=saidas,
        input_quantity=Decimal("300"),
        input_unit="kg",
        input_measurement_basis="peso liquido",
    )

    assert resultado.event.balance is not None
    assert resultado.event.balance.status is BalanceStatus.ASSESSED
    assert resultado.event.balance.result is BalanceResult.BALANCED

    persistido = cenario.events.get_by_id(resultado.event.event_id)
    assert persistido is not None
    assert persistido.balance is not None
    assert persistido.balance.result is BalanceResult.BALANCED
    assert persistido.balance.output_total == Decimal("300")


class TestCorrecaoDeSlaughter:
    """ADR-0047, Passo 11.7: correção de TransformationEvent(SLAUGHTER) publicado."""

    def test_corrige_reafirmando_a_mesma_entrada(
        self, recorder: LivestockEventRecorder, context: LivestockOperationContext
    ) -> None:
        cenario = Cenario(recorder, context)
        cenario.abater()
        original = cenario.service.register_slaughter(
            context=context,
            animal_id=cenario.animal_id,
            facility_property_id=cenario.facility_id,
            occurred_at=ONTEM + timedelta(hours=1),
            outputs=cenario.outputs(2),
        )

        correcao = cenario.service.correct_slaughter(
            context=context,
            corrects_transformation_id=original.event.event_id,
            correction_reason="Peso de saída lançado errado no apontamento original.",
            animal_id=cenario.animal_id,
            facility_property_id=cenario.facility_id,
            occurred_at=ONTEM + timedelta(hours=1),
            outputs=cenario.outputs(2),
        )

        assert correcao.event.corrects_transformation_id == original.event.event_id
        assert correcao.event.correction_reason
        # O evento original nunca é editado — continua consultável integralmente.
        assert cenario.events.get_by_id(original.event.event_id) == original.event

        assert (
            operational_status_now(cenario.events, original.event.event_id)
            is TransformationStatus.SUPERSEDED
        )
        assert (
            operational_status_now(cenario.events, correcao.event.event_id)
            is TransformationStatus.CURRENT
        )

    def test_recusa_corrigir_evento_que_ja_nao_e_o_leaf(
        self, recorder: LivestockEventRecorder, context: LivestockOperationContext
    ) -> None:
        cenario = Cenario(recorder, context)
        cenario.abater()
        original = cenario.service.register_slaughter(
            context=context,
            animal_id=cenario.animal_id,
            facility_property_id=cenario.facility_id,
            occurred_at=ONTEM + timedelta(hours=1),
            outputs=cenario.outputs(2),
        )
        cenario.service.correct_slaughter(
            context=context,
            corrects_transformation_id=original.event.event_id,
            correction_reason="Primeira correção.",
            animal_id=cenario.animal_id,
            facility_property_id=cenario.facility_id,
            occurred_at=ONTEM + timedelta(hours=1),
            outputs=cenario.outputs(2),
        )

        with pytest.raises(AlvoDeCorrecaoNaoEhVigente, match="leaf atual"):
            cenario.service.correct_slaughter(
                context=context,
                corrects_transformation_id=original.event.event_id,
                correction_reason="Tentativa de bifurcar a cadeia.",
                animal_id=cenario.animal_id,
                facility_property_id=cenario.facility_id,
                occurred_at=ONTEM + timedelta(hours=1),
                outputs=cenario.outputs(2),
            )

    def test_reafirmar_entrada_nao_dispara_animal_ja_transformado(
        self, recorder: LivestockEventRecorder, context: LivestockOperationContext
    ) -> None:
        """ADR-0047, item 7: a correção reclama a mesma entrada do evento corrigido."""
        cenario = Cenario(recorder, context)
        cenario.abater()
        original = cenario.service.register_slaughter(
            context=context,
            animal_id=cenario.animal_id,
            facility_property_id=cenario.facility_id,
            occurred_at=ONTEM + timedelta(hours=1),
            outputs=cenario.outputs(2),
        )

        # Não levanta AnimalJaTransformado mesmo o animal já constando como
        # entrada do evento original.
        correcao = cenario.service.correct_slaughter(
            context=context,
            corrects_transformation_id=original.event.event_id,
            correction_reason="Corrige rótulo das saídas.",
            animal_id=cenario.animal_id,
            facility_property_id=cenario.facility_id,
            occurred_at=ONTEM + timedelta(hours=1),
            outputs=cenario.outputs(2),
        )
        assert correcao.event.inputs[0].subject_reference.target_id == cenario.animal_id

    def test_recusa_corrigir_evento_de_outro_process_type(
        self, recorder: LivestockEventRecorder, context: LivestockOperationContext
    ) -> None:
        cenario = Cenario(recorder, context)
        desossa = TransformationEvent(
            event_id=TypedId.new("transformation_event"),
            organization_id=cenario.organization_id,
            process_type=ProcessType.DEBONING,
            occurred_at=ONTEM,
            facility_reference=UniversalReference(
                target_id=cenario.facility_id,
                organization_id=cenario.organization_id,
                contract_version=1,
            ),
            inputs=(
                TransformationParticipant(
                    subject_reference=UniversalReference(
                        target_id=TypedId.new("traceable_item"),
                        organization_id=cenario.organization_id,
                        contract_version=1,
                    ),
                    role=ParticipantRole.INPUT,
                ),
            ),
            outputs=(
                TransformationParticipant(
                    subject_reference=UniversalReference(
                        target_id=TypedId.new("traceable_item"),
                        organization_id=cenario.organization_id,
                        contract_version=1,
                    ),
                    role=ParticipantRole.OUTPUT,
                ),
            ),
            created_at=ONTEM,
        )
        cenario.events.save(desossa)

        with pytest.raises(ValueError, match="mudança de process_type"):
            cenario.service.correct_slaughter(
                context=context,
                corrects_transformation_id=desossa.event_id,
                correction_reason="Tentativa inválida.",
                animal_id=cenario.animal_id,
                facility_property_id=cenario.facility_id,
                occurred_at=ONTEM + timedelta(hours=1),
                outputs=cenario.outputs(2),
            )
