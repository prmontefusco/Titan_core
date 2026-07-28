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
    TransformationStatus,
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

    def get_correction_of(self, event_id: TypedId) -> TransformationEvent | None:
        """O evento cujo `corrects_transformation_id` aponta para `event_id`, se existir.

        A UNIQUE de banco (ADR-0047, item 1/invariante 7) garante no máximo um
        resultado — a busca nunca precisa desempatar.
        """
        ...


class TransformationLockPort(Protocol):
    """Bloqueio transacional de linhas (ADR-0047, item 5), isolado de propósito.

    Não é mais um método nos ports de leitura/escrita já existentes
    (`TraceableItemRepositoryPort`, `TransformationEventRepositoryPort`,
    `AnimalRepositoryPort`) porque esses ports têm dezenas de fakes em testes
    que não têm nenhum motivo para conhecer bloqueio pessimista — só quem
    grava uma nova transformação ou uma correção precisa disto. Cada método
    executa um `SELECT ... FOR UPDATE` na mesma conexão/transação que depois
    revalida e escreve; devolve `False` quando a linha não existe (nada a
    bloquear) em vez de lançar, porque "não existe" já é tratado por guardas
    de domínio específicas de cada chamador (ex.: `AnimalNaoAbatido`).
    """

    def lock_transformation_event(self, event_id: TypedId) -> bool: ...

    def lock_traceable_item(self, item_id: TypedId) -> bool: ...

    def lock_animal(self, animal_id: TypedId) -> bool: ...


class AnimalNaoAbatido(ValueError):
    """`TransformationEvent(SLAUGHTER)` exige `AnimalExit(ABATE)` já registrada."""


class AnimalJaTransformado(ValueError):
    """O animal já foi consumido como entrada de uma transformação anterior."""


class ItemDeTipoInvalido(ValueError):
    """O item não é de um tipo aceito como entrada por este perfil de processo."""


class ItemJaConsumido(ValueError):
    """O item já foi consumido como entrada de uma transformação anterior."""


class AlvoDeCorrecaoNaoEhVigente(ValueError):
    """Só o leaf atual de uma cadeia de correção pode ser corrigido (ADR-0047, item 4).

    Corrigir um evento já `SUPERSEDED` bifurcaria a cadeia; quem chama precisa
    apontar a correção para o evento que já o corrigiu.
    """


class SaidaConsumidaAJusante(ValueError):
    """Uma saída do evento a corrigir já foi consumida por transformação vigente.

    ADR-0047, item 9: a correção só olha o próprio leaf; se uma saída dele já
    virou entrada de outro `TransformationEvent` ainda `CURRENT`, corrigir a
    origem invalidaria silenciosamente um fato já construído sobre ela.
    """


def operational_status_now(
    event_repository: TransformationEventRepositoryPort, event_id: TypedId
) -> TransformationStatus:
    """`operational_status_now` da ADR-0047, item 3: instante de referência = agora.

    SUPERSEDED sse existe outro `TransformationEvent` cujo
    `corrects_transformation_id` aponta para `event_id` — a mesma pesquisa
    reversa de `_superseded_map` (Marco 9), só que resolvida direto no
    repositório em vez de varrer uma lista em memória, porque a UNIQUE de
    banco já garante no máximo um resultado.
    """
    correction = event_repository.get_correction_of(event_id)
    if correction is not None:
        return TransformationStatus.SUPERSEDED
    return TransformationStatus.CURRENT


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
    *,
    excluding_event_id: TypedId | None = None,
) -> bool:
    """Um sujeito só é consumido como entrada uma vez.

    Lê a projeção já gravada em vez de um repositório dedicado — a mesma
    trilha que o Passo 7.1 já sustenta, sem tabela nova.

    `excluding_event_id` existe para a correção (ADR-0047, item 7): reafirmar,
    numa correção, a mesma entrada que o evento corrigido já reivindicava não
    pode ser lida como "já em uso" — a única relação `input_of` a ignorar é
    exatamente a que aponta para o evento sendo corrigido.
    """
    existentes = relation_service.list_outgoing_at(
        organization_id=organization_id, source_reference=subject_reference
    )
    return any(
        relacao.relation_type == TRANSFORMATION_INPUT_OF
        and (excluding_event_id is None or relacao.target_reference.target_id != excluding_event_id)
        for relacao in existentes
    )


def _guard_occurred_at_no_futuro(occurred_at: datetime) -> None:
    require_utc(occurred_at, field_name="occurred_at")
    if occurred_at > datetime.now(UTC):
        raise ValueError("occurred_at não pode ser no futuro.")


def _guard_saida_nao_consumida_a_jusante(
    event_repository: TransformationEventRepositoryPort,
    relation_service: RelationService,
    organization_id: OrganizationId,
    output_participant: TransformationParticipant,
) -> None:
    """ADR-0047, item 9: "consumida a jusante" olha só o leaf do evento a corrigir.

    Compartilhada entre `SlaughterService` e `DeboningService` pelo mesmo
    motivo de `_ja_usado_como_entrada` — nenhum dos dois serviços tem estado
    que o outro precise, e a regra não depende de qual processo produziu a
    saída, só de quem a consome agora.
    """
    relacoes = relation_service.list_outgoing_at(
        organization_id=organization_id,
        source_reference=output_participant.subject_reference,
    )
    for relacao in relacoes:
        if relacao.relation_type != TRANSFORMATION_INPUT_OF:
            continue
        consumidor_id = relacao.target_reference.target_id
        if operational_status_now(event_repository, consumidor_id) is TransformationStatus.CURRENT:
            raise SaidaConsumidaAJusante(
                f"A saída '{output_participant.subject_reference.target_id.value}' já foi "
                "consumida por uma transformação vigente; corrigir a origem invalidaria um "
                "fato já construído sobre ela (ADR-0047, item 9)."
            )


@dataclass(frozen=True, slots=True)
class SlaughterService:
    event_repository: TransformationEventRepositoryPort
    item_repository: TraceableItemRepositoryPort
    animal_repository: AnimalRepositoryPort
    exit_repository: AnimalExitRepositoryPort
    property_repository: RuralPropertyRepositoryPort
    relation_service: RelationService
    recorder: LivestockEventRecorder
    lock_port: TransformationLockPort

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
        return self._persist(
            context,
            animal_id=animal_id,
            facility_property_id=facility_property_id,
            occurred_at=occurred_at,
            outputs=outputs,
            evidence_references=evidence_references,
            input_quantity=input_quantity,
            input_unit=input_unit,
            input_measurement_basis=input_measurement_basis,
            declared_loss=declared_loss,
            tolerance=tolerance,
            corrects_transformation_id=None,
            correction_reason=None,
        )

    def correct_slaughter(
        self,
        context: LivestockOperationContext,
        corrects_transformation_id: TypedId,
        correction_reason: str,
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
        """Corrige um `TransformationEvent(SLAUGHTER)` publicado (ADR-0047).

        Cria um evento completo novo — reafirma entradas, saídas, balanço e
        evidências; nunca é um patch parcial (item 1). `animal_id` tipicamente
        repete a entrada original: o guard de "já usado como entrada" ignora
        especificamente a reivindicação do próprio evento corrigido (item 7).
        """
        return self._persist(
            context,
            animal_id=animal_id,
            facility_property_id=facility_property_id,
            occurred_at=occurred_at,
            outputs=outputs,
            evidence_references=evidence_references,
            input_quantity=input_quantity,
            input_unit=input_unit,
            input_measurement_basis=input_measurement_basis,
            declared_loss=declared_loss,
            tolerance=tolerance,
            corrects_transformation_id=corrects_transformation_id,
            correction_reason=correction_reason,
        )

    def _persist(
        self,
        context: LivestockOperationContext,
        *,
        animal_id: TypedId,
        facility_property_id: TypedId,
        occurred_at: datetime,
        outputs: Sequence[TransformationOutputSpec],
        evidence_references: tuple[UniversalReference, ...],
        input_quantity: Decimal | None,
        input_unit: str,
        input_measurement_basis: str | None,
        declared_loss: Decimal | None,
        tolerance: Decimal | None,
        corrects_transformation_id: TypedId | None,
        correction_reason: str | None,
    ) -> SlaughterResult:
        organization_id = context.organization_id
        _guard_occurred_at_no_futuro(occurred_at)
        if len(outputs) < FAN_OUT_MINIMO:
            raise ValueError(
                f"SLAUGHTER exige ao menos {FAN_OUT_MINIMO} saídas rastreáveis "
                "(fan-out real, ADR-0046 item 1)."
            )

        original: TransformationEvent | None = None
        if corrects_transformation_id is not None:
            # Ordem determinística de bloqueio (ADR-0047, item 5.2): o alvo
            # da correção primeiro, antes de qualquer entrada/saída.
            self.lock_port.lock_transformation_event(corrects_transformation_id)
            original = self.event_repository.get_by_id(corrects_transformation_id)
            if original is None or original.organization_id != organization_id:
                raise KeyError(
                    f"TransformationEvent '{corrects_transformation_id.value}' não encontrado."
                )
            if original.process_type is not ProcessType.SLAUGHTER:
                raise ValueError(
                    "correct_slaughter só corrige TransformationEvent(SLAUGHTER); mudança de "
                    "process_type não é correção (ADR-0047, item 11)."
                )

        # Entradas, em seguida (item 5.2) — SLAUGHTER tem uma única entrada.
        self.lock_port.lock_animal(animal_id)

        if original is not None:
            # Saídas do evento sendo corrigido, por último e em ordem
            # determinística — necessárias para a checagem de "consumida a
            # jusante" (item 9).
            for output_id in sorted(
                (p.subject_reference.target_id for p in original.outputs),
                key=lambda i: str(i.value),
            ):
                self.lock_port.lock_traceable_item(output_id)

        # ---- revalidação: única leitura, já com os bloqueios adquiridos ----
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

        if original is not None and corrects_transformation_id is not None:
            if (
                operational_status_now(self.event_repository, corrects_transformation_id)
                is not TransformationStatus.CURRENT
            ):
                raise AlvoDeCorrecaoNaoEhVigente(
                    "Só o leaf atual de uma cadeia de correção pode ser corrigido: aponte a "
                    "correção para o evento que já corrigiu este (ADR-0047, item 4)."
                )
            for participant in original.outputs:
                _guard_saida_nao_consumida_a_jusante(
                    self.event_repository, self.relation_service, organization_id, participant
                )

        animal_reference = UniversalReference(
            target_id=animal_id,
            organization_id=organization_id,
            contract_version=AGGREGATE_CONTRACT_VERSION,
        )
        if _ja_usado_como_entrada(
            self.relation_service,
            organization_id,
            animal_reference,
            excluding_event_id=corrects_transformation_id,
        ):
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
            corrects_transformation_id=corrects_transformation_id,
            correction_reason=correction_reason,
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
    lock_port: TransformationLockPort

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
        return self._persist(
            context,
            facility_property_id=facility_property_id,
            occurred_at=occurred_at,
            inputs=inputs,
            outputs=outputs,
            evidence_references=evidence_references,
            declared_loss=declared_loss,
            tolerance=tolerance,
            corrects_transformation_id=None,
            correction_reason=None,
        )

    def correct_deboning(
        self,
        context: LivestockOperationContext,
        corrects_transformation_id: TypedId,
        correction_reason: str,
        facility_property_id: TypedId,
        occurred_at: datetime,
        inputs: Sequence[DeboningInputSpec],
        outputs: Sequence[TransformationOutputSpec],
        evidence_references: tuple[UniversalReference, ...] = (),
        declared_loss: Decimal | None = None,
        tolerance: Decimal | None = None,
    ) -> DeboningResult:
        """Corrige um `TransformationEvent(DEBONING)` publicado (ADR-0047)."""
        return self._persist(
            context,
            facility_property_id=facility_property_id,
            occurred_at=occurred_at,
            inputs=inputs,
            outputs=outputs,
            evidence_references=evidence_references,
            declared_loss=declared_loss,
            tolerance=tolerance,
            corrects_transformation_id=corrects_transformation_id,
            correction_reason=correction_reason,
        )

    def _persist(
        self,
        context: LivestockOperationContext,
        *,
        facility_property_id: TypedId,
        occurred_at: datetime,
        inputs: Sequence[DeboningInputSpec],
        outputs: Sequence[TransformationOutputSpec],
        evidence_references: tuple[UniversalReference, ...],
        declared_loss: Decimal | None,
        tolerance: Decimal | None,
        corrects_transformation_id: TypedId | None,
        correction_reason: str | None,
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

        original: TransformationEvent | None = None
        if corrects_transformation_id is not None:
            # Ordem determinística de bloqueio (ADR-0047, item 5.2): alvo primeiro.
            self.lock_port.lock_transformation_event(corrects_transformation_id)
            original = self.event_repository.get_by_id(corrects_transformation_id)
            if original is None or original.organization_id != organization_id:
                raise KeyError(
                    f"TransformationEvent '{corrects_transformation_id.value}' não encontrado."
                )
            if original.process_type is not ProcessType.DEBONING:
                raise ValueError(
                    "correct_deboning só corrige TransformationEvent(DEBONING); mudança de "
                    "process_type não é correção (ADR-0047, item 11)."
                )

        # Entradas, em ordem determinística (item 5.2).
        for input_id in sorted((spec.item_id for spec in inputs), key=lambda i: str(i.value)):
            self.lock_port.lock_traceable_item(input_id)

        if original is not None:
            # Saídas do evento sendo corrigido, por último — checagem de
            # "consumida a jusante" (item 9).
            for output_id in sorted(
                (p.subject_reference.target_id for p in original.outputs),
                key=lambda i: str(i.value),
            ):
                self.lock_port.lock_traceable_item(output_id)

        # ---- revalidação: única leitura, já com os bloqueios adquiridos ----
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

        if original is not None and corrects_transformation_id is not None:
            if (
                operational_status_now(self.event_repository, corrects_transformation_id)
                is not TransformationStatus.CURRENT
            ):
                raise AlvoDeCorrecaoNaoEhVigente(
                    "Só o leaf atual de uma cadeia de correção pode ser corrigido: aponte a "
                    "correção para o evento que já corrigiu este (ADR-0047, item 4)."
                )
            for participant in original.outputs:
                _guard_saida_nao_consumida_a_jusante(
                    self.event_repository, self.relation_service, organization_id, participant
                )

        input_references = tuple(
            UniversalReference(
                target_id=item.item_id,
                organization_id=organization_id,
                contract_version=AGGREGATE_CONTRACT_VERSION,
            )
            for item in itens_de_entrada
        )
        for reference in input_references:
            if _ja_usado_como_entrada(
                self.relation_service,
                organization_id,
                reference,
                excluding_event_id=corrects_transformation_id,
            ):
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
            corrects_transformation_id=corrects_transformation_id,
            correction_reason=correction_reason,
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
