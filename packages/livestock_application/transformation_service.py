"""Transformação industrial — abate e desossa (ADR-0046, Passos 11.2 e 11.6).

`SlaughterService` (Passo 11.2) prova o fan-out real: um animal, já com saída
ABATE registrada, produz duas ou mais saídas rastreáveis através de um único
`TransformationEvent(SLAUGHTER)`. `DeboningService` (Passo 11.6) prova o
fan-in real: duas ou mais entradas rastreáveis (`CARCASS`/`HALF_CARCASS`, já
produzidas por um `SLAUGHTER` anterior) viram uma ou mais saídas através de um
único `TransformationEvent(DEBONING)`.

Os dois serviços compartilham a mesma projeção `UniversalRelation` (item 5 da
ADR) e a mesma guarda contra reaproveitar um sujeito como entrada duas vezes
(item 11 da fila de invariantes) — ver `_project_relations` e
`_ja_usado_como_entrada`, funções de módulo, não métodos, porque nenhum dos
dois serviços tem estado que a outra precise.

`compute_transformation_balance` aceita N entradas desde o Passo 11.6: o
fan-in soma quantidades de várias entradas do mesmo jeito que já somava
quantidades de várias saídas — a mesma regra, sem duplicar lógica.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Protocol

from packages.core_application.relation_service import RelationService
from packages.core_domain.evidence import ConfidenceLevel, ConfidenceTier
from packages.core_domain.relations import UniversalRelation
from packages.livestock_application.animal_service import AnimalRepositoryPort
from packages.livestock_application.event_recorder import (
    AGGREGATE_CONTRACT_VERSION,
    LivestockEventRecorder,
    LivestockOperationContext,
)
from packages.livestock_application.exit_service import AnimalExitRepositoryPort
from packages.livestock_application.property_service import RuralPropertyRepositoryPort
from packages.livestock_domain.events import (
    TRANSFORMATION_EVENT_RECORDED,
    transformation_event_recorded_payload,
)
from packages.livestock_domain.exit import ExitType
from packages.livestock_domain.transformation import (
    BalanceResult,
    BalanceStatus,
    ConsumptionMode,
    ParticipantRole,
    ProcessType,
    TraceableItem,
    TraceableItemType,
    TransformationBalance,
    TransformationEvent,
    TransformationParticipant,
)
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference
from packages.shared_kernel.temporal import require_utc

TRANSFORMATION_INPUT_OF = "transformation.input_of"
TRANSFORMATION_OUTPUT_OF = "transformation.output_of"

# Abate sem fan-out real não prova a decisão do Passo 11.2 (item 1 da ADR: o
# contrato aceita N=1, mas o cenário validado exige fan-out de verdade).
FAN_OUT_MINIMO = 2

# Simetricamente, desossa sem fan-in real não prova o Passo 11.6.
FAN_IN_MINIMO = 2

# Perfil do processo DEBONING (item 6 da ADR: quem pode ser entrada é decisão
# do perfil, não do Core). MIXING fica para quando houver um segundo caso de
# fan-in real que justifique generalizar o mapeamento processo→entradas.
DEBONING_ENTRADAS_PERMITIDAS = frozenset(
    {TraceableItemType.CARCASS, TraceableItemType.HALF_CARCASS}
)


class TraceableItemRepositoryPort(Protocol):
    def save(self, item: TraceableItem) -> None: ...

    def get_by_id(self, item_id: TypedId) -> TraceableItem | None: ...


class TransformationEventRepositoryPort(Protocol):
    def save(self, event: TransformationEvent) -> None: ...

    def get_by_id(self, event_id: TypedId) -> TransformationEvent | None: ...


class AnimalNaoAbatido(ValueError):
    """`TransformationEvent(SLAUGHTER)` exige `AnimalExit(ABATE)` já registrada."""


class AnimalJaTransformado(ValueError):
    """O animal já foi consumido como entrada de uma transformação anterior."""


class ItemDeTipoInvalido(ValueError):
    """O item não é de um tipo aceito como entrada por este perfil de processo."""


class ItemJaConsumido(ValueError):
    """O item já foi consumido como entrada de uma transformação anterior."""


@dataclass(frozen=True, slots=True)
class TransformationOutputSpec:
    """Uma saída declarada pelo operador, antes de virar `TraceableItem`.

    Nome genérico porque `SLAUGHTER` e `DEBONING` compartilham exatamente a
    mesma forma de saída — não há nada específico de abate aqui.
    """

    item_type: TraceableItemType
    quantity: Decimal | None = None
    unit: str = ""
    measurement_basis: str | None = None
    label: str | None = None


@dataclass(frozen=True, slots=True)
class QuantifiedAmount:
    """A quantidade de uma entrada, para o cálculo de balanço.

    Deliberadamente sem `item_type` ou `label`: o balanço não precisa saber o
    que a entrada é, só quanto ela pesa e em que base — o mesmo motivo por que
    `TransformationOutputSpec` carrega campos que o balanço ignora.
    """

    quantity: Decimal | None = None
    unit: str = ""
    measurement_basis: str | None = None


@dataclass(frozen=True, slots=True)
class SlaughterResult:
    event: TransformationEvent
    created_items: tuple[TraceableItem, ...]


@dataclass(frozen=True, slots=True)
class DeboningResult:
    event: TransformationEvent
    created_items: tuple[TraceableItem, ...]


def compute_transformation_balance(
    *,
    inputs: Sequence[QuantifiedAmount],
    outputs: Sequence[TransformationOutputSpec],
    declared_loss: Decimal | None,
    tolerance: Decimal | None,
) -> TransformationBalance:
    """Calcula o balanço mínimo de uma transformação (ADR-0046, Passo 11.4).

    Generalizado para N entradas desde o Passo 11.6 (fan-in): a soma de
    entradas segue exatamente a mesma regra que já somava saídas — nenhuma
    quantidade ausente vira zero, nenhuma base incompatível vira número.

    Ausência de peso de entrada não impede o registro do fato (mesmo princípio
    da ADR-0040): produz `NOT_ASSESSED`, nunca zero ou `BALANCED` por omissão.
    Bases de medição incompatíveis entre entradas e saídas (ex.: peso vivo vs.
    peso líquido pós-sangria) nunca são comparadas numericamente — o item 7 da
    ADR é explícito que isso produz `INDETERMINATE`, nunca um número inventado.
    `declared_loss` (perda conhecida) e `unaccounted_quantity` (diferença ainda
    não explicada) são conceitos distintos: a segunda é calculada descontando a
    primeira, nunca as duas somadas às cegas.
    """
    entradas_sem_quantidade = [amount for amount in inputs if amount.quantity is None]
    if not inputs or entradas_sem_quantidade:
        return TransformationBalance(
            status=BalanceStatus.NOT_ASSESSED,
            result=BalanceResult.NOT_APPLICABLE,
            declared_loss=declared_loss,
            reasons=("Quantidade de entrada não informada.",),
        )

    saidas_sem_quantidade = [spec for spec in outputs if spec.quantity is None]
    if saidas_sem_quantidade:
        entradas_brutas = [amount.quantity for amount in inputs if amount.quantity is not None]
        input_total_bruto = sum(entradas_brutas, start=Decimal("0"))
        return TransformationBalance(
            status=BalanceStatus.DECLARED,
            result=BalanceResult.INDETERMINATE,
            input_total=input_total_bruto,
            declared_loss=declared_loss,
            reasons=(
                f"{len(saidas_sem_quantidade)} saída(s) sem quantidade declarada — "
                "somar tratando ausência como zero inventaria dado.",
            ),
        )

    unidades = {amount.unit for amount in inputs} | {spec.unit for spec in outputs}
    if len(unidades) > 1:
        return TransformationBalance(
            status=BalanceStatus.DECLARED,
            result=BalanceResult.INDETERMINATE,
            declared_loss=declared_loss,
            reasons=(f"Unidades incompatíveis entre entradas e saídas: {sorted(unidades)}.",),
        )

    bases = {amount.measurement_basis for amount in inputs} | {
        spec.measurement_basis for spec in outputs
    }
    if len(bases) > 1:
        entradas_validas = [amount.quantity for amount in inputs if amount.quantity is not None]
        input_total_bruto = sum(entradas_validas, start=Decimal("0"))
        saidas_validas = [spec.quantity for spec in outputs if spec.quantity is not None]
        output_total_bruto = sum(saidas_validas, start=Decimal("0"))
        return TransformationBalance(
            status=BalanceStatus.DECLARED,
            result=BalanceResult.INDETERMINATE,
            input_total=input_total_bruto,
            output_total=output_total_bruto,
            declared_loss=declared_loss,
            reasons=(
                "Bases de medição incompatíveis entre entradas e saídas "
                f"({sorted(b for b in bases if b)}); comparar produziria número "
                "inventado.",
            ),
        )

    quantidades_entrada = [amount.quantity for amount in inputs if amount.quantity is not None]
    input_total = sum(quantidades_entrada, start=Decimal("0"))
    quantidades_saida = [spec.quantity for spec in outputs if spec.quantity is not None]
    output_total = sum(quantidades_saida, start=Decimal("0"))
    perda_declarada = declared_loss if declared_loss is not None else Decimal("0")
    unaccounted = input_total - output_total - perda_declarada
    tolerancia_efetiva = tolerance if tolerance is not None else Decimal("0")

    if unaccounted == 0:
        resultado = BalanceResult.BALANCED
    elif abs(unaccounted) <= tolerancia_efetiva:
        resultado = BalanceResult.WITHIN_TOLERANCE
    else:
        resultado = BalanceResult.OUTSIDE_TOLERANCE

    basis = next(iter(bases)) if bases else None
    return TransformationBalance(
        status=BalanceStatus.ASSESSED,
        result=resultado,
        measurement_basis=basis,
        input_total=input_total,
        output_total=output_total,
        declared_loss=declared_loss,
        unaccounted_quantity=unaccounted,
        tolerance=tolerance,
    )


def _build_outputs(
    organization_id: OrganizationId,
    event_id: TypedId,
    outputs: Sequence[TransformationOutputSpec],
    created_at: datetime,
) -> tuple[tuple[TraceableItem, ...], tuple[TransformationParticipant, ...]]:
    """Constrói os `TraceableItem` novos e os participantes de saída (item 3 da ADR).

    Toda saída cria um sujeito novo — nunca reaproveita identidade existente
    (invariante 3). Compartilhado entre `SLAUGHTER` e `DEBONING` porque a regra
    não depende do processo, só do papel `OUTPUT`.
    """
    created_items = tuple(
        TraceableItem(
            item_id=TypedId.new("traceable_item"),
            organization_id=organization_id,
            item_type=spec.item_type,
            created_by_transformation_id=event_id,
            created_at=created_at,
            label=spec.label,
        )
        for spec in outputs
    )
    output_participants = tuple(
        TransformationParticipant(
            subject_reference=UniversalReference(
                target_id=item.item_id,
                organization_id=organization_id,
                contract_version=AGGREGATE_CONTRACT_VERSION,
            ),
            role=ParticipantRole.OUTPUT,
            quantity=spec.quantity,
            unit=spec.unit,
            measurement_basis=spec.measurement_basis,
        )
        for item, spec in zip(created_items, outputs, strict=True)
    )
    return created_items, output_participants


def _project_relations(
    relation_service: RelationService,
    *,
    organization_id: OrganizationId,
    event_id: TypedId,
    process_type: ProcessType,
    input_references: tuple[UniversalReference, ...],
    created_items: tuple[TraceableItem, ...],
    occurred_at: datetime,
    created_by_event: TypedId,
) -> None:
    """Projeta `UniversalRelation` a partir do evento já gravado (ADR-0046, item 5).

    A relação nunca é fonte concorrente: reconstituir a transformação sempre lê
    o `TransformationEvent`, nunca estas linhas. Toda entrada e toda saída
    aponta para o mesmo nó (o evento) — nunca umas para as outras — e é
    exatamente essa forma em estrela que faz o fan-in preservar o **conjunto**
    de origens sem inventar correspondência 1:1 entre uma saída e uma origem
    específica (invariante 15): `RecallService`, sem nenhuma alteração, já
    devolve todas as entradas ao alcançar o evento a partir de qualquer saída.
    """
    transformation_reference = UniversalReference(
        target_id=event_id,
        organization_id=organization_id,
        contract_version=AGGREGATE_CONTRACT_VERSION,
    )
    confidence = ConfidenceLevel(
        tier=ConfidenceTier.DOCUMENTED,
        reason=f"Declarado pelo evento de transformação industrial ({process_type.value}).",
    )
    for reference in input_references:
        relation_service.register_relation(
            UniversalRelation.create(
                organization_id=organization_id,
                source_reference=reference,
                target_reference=transformation_reference,
                relation_type=TRANSFORMATION_INPUT_OF,
                created_at=datetime.now(UTC),
                confidence=confidence,
                valid_from=occurred_at,
                created_by_event=created_by_event,
            )
        )
    for item in created_items:
        item_reference = UniversalReference(
            target_id=item.item_id,
            organization_id=organization_id,
            contract_version=AGGREGATE_CONTRACT_VERSION,
        )
        relation_service.register_relation(
            UniversalRelation.create(
                organization_id=organization_id,
                source_reference=item_reference,
                target_reference=transformation_reference,
                relation_type=TRANSFORMATION_OUTPUT_OF,
                created_at=datetime.now(UTC),
                confidence=confidence,
                valid_from=occurred_at,
                created_by_event=created_by_event,
            )
        )


def _ja_usado_como_entrada(
    relation_service: RelationService,
    organization_id: OrganizationId,
    subject_reference: UniversalReference,
) -> bool:
    """Um sujeito só é consumido como entrada uma vez.

    Lê a projeção já gravada em vez de um repositório dedicado — a mesma
    trilha que o Passo 7.1 já sustenta, sem tabela nova.
    """
    existentes = relation_service.list_outgoing_at(
        organization_id=organization_id, source_reference=subject_reference
    )
    return any(relacao.relation_type == TRANSFORMATION_INPUT_OF for relacao in existentes)


def _guard_occurred_at_no_futuro(occurred_at: datetime) -> None:
    require_utc(occurred_at, field_name="occurred_at")
    if occurred_at > datetime.now(UTC):
        raise ValueError("occurred_at não pode ser no futuro.")


@dataclass(frozen=True, slots=True)
class SlaughterService:
    event_repository: TransformationEventRepositoryPort
    item_repository: TraceableItemRepositoryPort
    animal_repository: AnimalRepositoryPort
    exit_repository: AnimalExitRepositoryPort
    property_repository: RuralPropertyRepositoryPort
    relation_service: RelationService
    recorder: LivestockEventRecorder

    def register_slaughter(
        self,
        context: LivestockOperationContext,
        animal_id: TypedId,
        facility_property_id: TypedId,
        occurred_at: datetime,
        outputs: Sequence[TransformationOutputSpec],
        evidence_references: tuple[UniversalReference, ...] = (),
        input_quantity: Decimal | None = None,
        input_unit: str = "",
        input_measurement_basis: str | None = None,
        declared_loss: Decimal | None = None,
        tolerance: Decimal | None = None,
    ) -> SlaughterResult:
        organization_id = context.organization_id
        _guard_occurred_at_no_futuro(occurred_at)
        if len(outputs) < FAN_OUT_MINIMO:
            raise ValueError(
                f"SLAUGHTER exige ao menos {FAN_OUT_MINIMO} saídas rastreáveis "
                "(fan-out real, ADR-0046 item 1)."
            )

        animal = self.animal_repository.get_by_id(animal_id)
        if animal is None or animal.organization_id != organization_id:
            raise KeyError(f"Animal '{animal_id.value}' não encontrado.")

        facility = self.property_repository.get_by_id(facility_property_id)
        if facility is None or facility.organization_id != organization_id:
            raise KeyError(f"Propriedade '{facility_property_id.value}' não encontrada.")

        exit_record = self.exit_repository.get_by_animal(animal_id)
        if (
            exit_record is None
            or exit_record.organization_id != organization_id
            or exit_record.exit_type is not ExitType.ABATE
        ):
            raise AnimalNaoAbatido(
                "TransformationEvent(SLAUGHTER) exige que o animal já tenha saída "
                "registrada como ABATE (ADR-0046, item 8): AnimalExit sozinho não é "
                "evidência de abate, mas é pré-condição dele."
            )
        if occurred_at < exit_record.occurred_at:
            raise ValueError(
                "occurred_at da transformação não pode ser anterior à saída por abate."
            )

        animal_reference = UniversalReference(
            target_id=animal_id,
            organization_id=organization_id,
            contract_version=AGGREGATE_CONTRACT_VERSION,
        )
        if _ja_usado_como_entrada(self.relation_service, organization_id, animal_reference):
            raise AnimalJaTransformado(
                "Este animal já foi utilizado como entrada em uma transformação anterior."
            )

        event_id = TypedId.new("transformation_event")
        momento_criacao = datetime.now(UTC)
        created_items, output_participants = _build_outputs(
            organization_id, event_id, outputs, momento_criacao
        )
        input_participant = TransformationParticipant(
            subject_reference=animal_reference,
            role=ParticipantRole.INPUT,
            quantity=input_quantity,
            unit=input_unit,
            measurement_basis=input_measurement_basis,
            consumption_mode=ConsumptionMode.FULL,
        )
        facility_reference = UniversalReference(
            target_id=facility_property_id,
            organization_id=organization_id,
            contract_version=AGGREGATE_CONTRACT_VERSION,
        )
        balance = compute_transformation_balance(
            inputs=(
                QuantifiedAmount(
                    quantity=input_quantity,
                    unit=input_unit,
                    measurement_basis=input_measurement_basis,
                ),
            ),
            outputs=outputs,
            declared_loss=declared_loss,
            tolerance=tolerance,
        )

        event = TransformationEvent(
            event_id=event_id,
            organization_id=organization_id,
            process_type=ProcessType.SLAUGHTER,
            occurred_at=occurred_at,
            facility_reference=facility_reference,
            inputs=(input_participant,),
            outputs=output_participants,
            created_at=momento_criacao,
            balance=balance,
            evidence_references=evidence_references,
        )

        self.event_repository.save(event)
        for item in created_items:
            self.item_repository.save(item)

        domain_event = self.recorder.record(
            context=context,
            aggregate_id=event_id,
            event_type=TRANSFORMATION_EVENT_RECORDED,
            payload=transformation_event_recorded_payload(
                event_id=event_id,
                process_type=ProcessType.SLAUGHTER.value,
                occurred_at=occurred_at,
                facility_id=facility_property_id,
                input_subject_ids=(animal_id,),
                output_items=tuple((item.item_id, item.item_type.value) for item in created_items),
                evidence_references=evidence_references,
            ),
            occurred_at=occurred_at,
        )

        _project_relations(
            self.relation_service,
            organization_id=organization_id,
            event_id=event_id,
            process_type=ProcessType.SLAUGHTER,
            input_references=(animal_reference,),
            created_items=created_items,
            occurred_at=occurred_at,
            created_by_event=domain_event.event_id,
        )

        return SlaughterResult(event=event, created_items=created_items)


@dataclass(frozen=True, slots=True)
class DeboningInputSpec:
    """Uma entrada declarada pelo operador: qual item, e quanto dele entrou."""

    item_id: TypedId
    quantity: Decimal | None = None
    unit: str = ""
    measurement_basis: str | None = None


@dataclass(frozen=True, slots=True)
class DeboningService:
    """Registra `TransformationEvent(DEBONING)` com fan-in real (Passo 11.6).

    Duas ou mais entradas rastreáveis — já produzidas por um `SLAUGHTER`
    anterior, do tipo `CARCASS` ou `HALF_CARCASS` (item 6 da ADR: o perfil do
    processo decide quem pode ser entrada) — viram uma ou mais saídas novas.
    """

    event_repository: TransformationEventRepositoryPort
    item_repository: TraceableItemRepositoryPort
    property_repository: RuralPropertyRepositoryPort
    relation_service: RelationService
    recorder: LivestockEventRecorder

    def register_deboning(
        self,
        context: LivestockOperationContext,
        facility_property_id: TypedId,
        occurred_at: datetime,
        inputs: Sequence[DeboningInputSpec],
        outputs: Sequence[TransformationOutputSpec],
        evidence_references: tuple[UniversalReference, ...] = (),
        declared_loss: Decimal | None = None,
        tolerance: Decimal | None = None,
    ) -> DeboningResult:
        organization_id = context.organization_id
        _guard_occurred_at_no_futuro(occurred_at)
        if len(inputs) < FAN_IN_MINIMO:
            raise ValueError(
                f"DEBONING exige ao menos {FAN_IN_MINIMO} entradas rastreáveis "
                "(fan-in real, ADR-0046 item 1)."
            )
        if not outputs:
            raise ValueError("DEBONING exige ao menos uma saída rastreável.")
        if len({spec.item_id.value for spec in inputs}) != len(inputs):
            raise ValueError("Um item não pode ser entrada duplicada da mesma transformação.")

        facility = self.property_repository.get_by_id(facility_property_id)
        if facility is None or facility.organization_id != organization_id:
            raise KeyError(f"Propriedade '{facility_property_id.value}' não encontrada.")

        itens_de_entrada: list[TraceableItem] = []
        for spec in inputs:
            item = self.item_repository.get_by_id(spec.item_id)
            if item is None or item.organization_id != organization_id:
                raise KeyError(f"Item '{spec.item_id.value}' não encontrado.")
            if item.item_type not in DEBONING_ENTRADAS_PERMITIDAS:
                permitidos = sorted(tipo.value for tipo in DEBONING_ENTRADAS_PERMITIDAS)
                raise ItemDeTipoInvalido(
                    f"DEBONING não aceita '{item.item_type.value}' como entrada "
                    f"(perfil do processo aceita {permitidos})."
                )
            itens_de_entrada.append(item)

        input_references = tuple(
            UniversalReference(
                target_id=item.item_id,
                organization_id=organization_id,
                contract_version=AGGREGATE_CONTRACT_VERSION,
            )
            for item in itens_de_entrada
        )
        for reference in input_references:
            if _ja_usado_como_entrada(self.relation_service, organization_id, reference):
                raise ItemJaConsumido(
                    f"O item '{reference.target_id.value}' já foi utilizado como entrada "
                    "em uma transformação anterior."
                )

        event_id = TypedId.new("transformation_event")
        momento_criacao = datetime.now(UTC)
        created_items, output_participants = _build_outputs(
            organization_id, event_id, outputs, momento_criacao
        )
        input_participants = tuple(
            TransformationParticipant(
                subject_reference=reference,
                role=ParticipantRole.INPUT,
                quantity=spec.quantity,
                unit=spec.unit,
                measurement_basis=spec.measurement_basis,
                consumption_mode=ConsumptionMode.FULL,
            )
            for reference, spec in zip(input_references, inputs, strict=True)
        )
        facility_reference = UniversalReference(
            target_id=facility_property_id,
            organization_id=organization_id,
            contract_version=AGGREGATE_CONTRACT_VERSION,
        )
        balance = compute_transformation_balance(
            inputs=[
                QuantifiedAmount(
                    quantity=spec.quantity, unit=spec.unit, measurement_basis=spec.measurement_basis
                )
                for spec in inputs
            ],
            outputs=outputs,
            declared_loss=declared_loss,
            tolerance=tolerance,
        )

        event = TransformationEvent(
            event_id=event_id,
            organization_id=organization_id,
            process_type=ProcessType.DEBONING,
            occurred_at=occurred_at,
            facility_reference=facility_reference,
            inputs=input_participants,
            outputs=output_participants,
            created_at=momento_criacao,
            balance=balance,
            evidence_references=evidence_references,
        )

        self.event_repository.save(event)
        for item in created_items:
            self.item_repository.save(item)

        domain_event = self.recorder.record(
            context=context,
            aggregate_id=event_id,
            event_type=TRANSFORMATION_EVENT_RECORDED,
            payload=transformation_event_recorded_payload(
                event_id=event_id,
                process_type=ProcessType.DEBONING.value,
                occurred_at=occurred_at,
                facility_id=facility_property_id,
                input_subject_ids=tuple(item.item_id for item in itens_de_entrada),
                output_items=tuple((item.item_id, item.item_type.value) for item in created_items),
                evidence_references=evidence_references,
            ),
            occurred_at=occurred_at,
        )

        _project_relations(
            self.relation_service,
            organization_id=organization_id,
            event_id=event_id,
            process_type=ProcessType.DEBONING,
            input_references=input_references,
            created_items=created_items,
            occurred_at=occurred_at,
            created_by_event=domain_event.event_id,
        )

        return DeboningResult(event=event, created_items=created_items)
