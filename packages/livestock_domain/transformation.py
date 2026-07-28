"""Transformação industrial e itens rastreáveis (ADR-0046, Passo 11.2).

Primeira vez que a vertical modela o que acontece **depois** de `AnimalExit`.
Até aqui o ciclo do animal terminava apontando para um `destination_counterparty_id`
e nada mais era registrado — a cadeia deixava de ser rastreável no exato momento
em que ela mais importa comercialmente. `TransformationEvent` é a fonte
autoritativa do que foi produzido; `UniversalRelation` é só a projeção navegável
que o Passo 7.1 já sabe percorrer (ver `packages.livestock_application.
transformation_service` para quem grava a projeção).

**`TransformationParticipant` carrega `INPUT` e `OUTPUT` na mesma forma, mas as
regras não são simétricas.** Ver `__post_init__`: `OUTPUT` nunca declara
`consumption_mode` (o conceito não existe para quem está sendo criado), e é o
serviço de aplicação — não este módulo — quem garante que todo `OUTPUT`
referencia um `TraceableItem` recém-criado (invariante 3 da ADR).

`TransformationEvent` só valida o que é seu: forma estrutural, fronteira de
Organization, e as duas listas não-vazias. Regras específicas de processo (que
subject pode ser entrada em `SLAUGHTER`) pertencem ao serviço, porque são
decisão do perfil de negócio, não do formato (ADR item 6).
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from packages.shared_kernel import OrganizationId, TypedId, UniversalReference
from packages.shared_kernel.temporal import require_utc


class ProcessType(StrEnum):
    """O processo observado. Só `SLAUGHTER` está implementado neste incremento.

    `DEBONING` já existe no vocabulário porque o contrato (item 3 da ADR) já a
    prevê como o evento seguinte de uma cadeia de abate — mas nenhum serviço a
    constrói ainda.
    """

    SLAUGHTER = "SLAUGHTER"
    DEBONING = "DEBONING"


class ParticipantRole(StrEnum):
    INPUT = "INPUT"
    OUTPUT = "OUTPUT"


class ConsumptionMode(StrEnum):
    """Só se aplica a `INPUT`; `OUTPUT` nunca declara este campo."""

    FULL = "FULL"
    PARTIAL = "PARTIAL"
    REFERENCE_ONLY = "REFERENCE_ONLY"


class TraceableItemType(StrEnum):
    """Ilustrativo, sujeito ao vocabulário real do primeiro frigorífico-alvo
    (ADR-0046, item 4). `PALLET` foi deliberadamente excluído: é unidade
    logística de agregação, não material resultante de transformação.
    """

    CARCASS = "CARCASS"
    HALF_CARCASS = "HALF_CARCASS"
    HIDE = "HIDE"
    OFFAL_BATCH = "OFFAL_BATCH"
    CUT_BATCH = "CUT_BATCH"
    TRIM_BATCH = "TRIM_BATCH"
    PACKAGED_PRODUCT = "PACKAGED_PRODUCT"


class BalanceStatus(StrEnum):
    NOT_ASSESSED = "NOT_ASSESSED"
    DECLARED = "DECLARED"
    ASSESSED = "ASSESSED"
    INDETERMINATE = "INDETERMINATE"


class BalanceResult(StrEnum):
    BALANCED = "BALANCED"
    WITHIN_TOLERANCE = "WITHIN_TOLERANCE"
    OUTSIDE_TOLERANCE = "OUTSIDE_TOLERANCE"
    INDETERMINATE = "INDETERMINATE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class TransformationStatus(StrEnum):
    """Estado derivado de um `TransformationEvent`, nunca armazenado (ADR-0047, item 3).

    Relativo a um instante de referência — `now` para guardas de escrita,
    `known_until` para reconstrução histórica (invariante 5). O cálculo em si
    (existe outro evento cujo `corrects_transformation_id` aponta para este?)
    vive em `packages.livestock_application.transformation_service`, porque
    depende de consulta ao repositório — este módulo só nomeia os dois estados.
    """

    CURRENT = "CURRENT"
    SUPERSEDED = "SUPERSEDED"


@dataclass(frozen=True, slots=True)
class TransformationBalance:
    """Estrutura já fixada pela ADR-0046; nenhum serviço a computa ainda (Passo 11.4).

    Ausência de balanço não é zero nem `BALANCED` por omissão — é `None` no
    evento, ou este objeto com `status=NOT_ASSESSED`. `declared_loss` (perda
    conhecida) e `unaccounted_quantity` (diferença ainda não explicada) nunca se
    somam silenciosamente: são conceitos distintos.
    """

    status: BalanceStatus
    result: BalanceResult
    measurement_basis: str | None = None
    input_total: Decimal | None = None
    output_total: Decimal | None = None
    declared_loss: Decimal | None = None
    unaccounted_quantity: Decimal | None = None
    tolerance: Decimal | None = None
    reasons: tuple[str, ...] = ()
    evidence_references: tuple[UniversalReference, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.status, BalanceStatus):
            raise TypeError("status deve ser um BalanceStatus.")
        if not isinstance(self.result, BalanceResult):
            raise TypeError("result deve ser um BalanceResult.")
        for label, valor in (
            ("input_total", self.input_total),
            ("output_total", self.output_total),
            ("declared_loss", self.declared_loss),
            ("unaccounted_quantity", self.unaccounted_quantity),
            ("tolerance", self.tolerance),
        ):
            if isinstance(valor, float):
                raise TypeError(f"{label} não aceita float; utilize Decimal.")
            if valor is not None and not isinstance(valor, Decimal):
                raise TypeError(f"{label} deve ser Decimal ou None.")


@dataclass(frozen=True, slots=True)
class TransformationParticipant:
    """Um input ou output de uma transformação — nunca os dois ao mesmo tempo.

    `role` decide regras que a forma compartilhada não deixa óbvias: todo
    `OUTPUT` cria um `TraceableItem` novo (a criação em si é responsabilidade do
    serviço, não deste construtor) e nunca declara `consumption_mode`; todo
    `INPUT` referencia um sujeito preexistente e sempre declara `consumption_mode`
    (default `FULL`).
    """

    subject_reference: UniversalReference
    role: ParticipantRole
    quantity: Decimal | None = None
    unit: str = ""
    measurement_basis: str | None = None
    consumption_mode: ConsumptionMode | None = None
    lot_or_batch_reference: UniversalReference | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.subject_reference, UniversalReference):
            raise TypeError("subject_reference deve ser UniversalReference.")
        if not isinstance(self.role, ParticipantRole):
            raise TypeError("role deve ser ParticipantRole.")
        if isinstance(self.quantity, float):
            raise TypeError("quantity não aceita float; utilize Decimal.")
        if self.quantity is not None and not isinstance(self.quantity, Decimal):
            raise TypeError("quantity deve ser Decimal ou None.")
        if self.quantity is not None and self.quantity < 0:
            raise ValueError("quantity não pode ser negativa.")
        if self.quantity is not None and not self.unit.strip():
            raise ValueError("Toda quantidade exige unidade declarada.")
        if self.lot_or_batch_reference is not None and not isinstance(
            self.lot_or_batch_reference, UniversalReference
        ):
            raise TypeError("lot_or_batch_reference deve ser UniversalReference ou None.")

        if self.role is ParticipantRole.OUTPUT:
            if self.consumption_mode is not None:
                raise ValueError(
                    "consumption_mode não se aplica a OUTPUT: o conceito de 'quanto foi "
                    "consumido' não existe para um sujeito que está sendo criado."
                )
        else:
            if self.consumption_mode is not None and not isinstance(
                self.consumption_mode, ConsumptionMode
            ):
                raise TypeError("consumption_mode deve ser ConsumptionMode ou None.")


@dataclass(frozen=True, slots=True)
class TraceableItem:
    """Um sujeito rastreável criado por uma transformação.

    Nome provisório (ADR-0046, item 4): não pressupõe produto comercial, só que
    a saída precisa continuar rastreada com identidade própria.
    """

    item_id: TypedId
    organization_id: OrganizationId
    item_type: TraceableItemType
    created_by_transformation_id: TypedId | None
    created_at: datetime
    label: str | None = None

    def __post_init__(self) -> None:
        if self.item_id.entity_type != "traceable_item":
            raise ValueError(
                f"item_id deve ter entity_type 'traceable_item', recebido "
                f"'{self.item_id.entity_type}'."
            )
        if not isinstance(self.organization_id, OrganizationId):
            raise TypeError("organization_id deve ser OrganizationId.")
        if not isinstance(self.item_type, TraceableItemType):
            raise TypeError("item_type deve ser TraceableItemType.")
        if (
            self.created_by_transformation_id is not None
            and self.created_by_transformation_id.entity_type != "transformation_event"
        ):
            raise ValueError(
                "created_by_transformation_id deve ter entity_type 'transformation_event'."
            )
        if self.label is not None and not self.label.strip():
            raise ValueError("label, quando informado, não pode ser vazio.")
        require_utc(self.created_at, field_name="created_at")


@dataclass(frozen=True, slots=True)
class TransformationEvent:
    """O fato autoritativo de que uma transformação industrial ocorreu.

    Apesar do nome "Event", representa um fato persistente do domínio — um
    agregado com identidade própria, consultável e referenciável — e não um
    `DomainEvent` do mecanismo de log append-only do Core
    (`packages/core_infrastructure/persistence/events.py`). São dois conceitos
    homônimos por convenção EPCIS, não pelo mecanismo do Titan; registrar este
    evento também produz, adicionalmente, um `DomainEvent` de auditoria (como
    qualquer outra escrita relevante), mas ele próprio não é um.
    """

    event_id: TypedId
    organization_id: OrganizationId
    process_type: ProcessType
    occurred_at: datetime
    facility_reference: UniversalReference
    inputs: tuple[TransformationParticipant, ...]
    outputs: tuple[TransformationParticipant, ...]
    created_at: datetime
    operator_reference: UniversalReference | None = None
    source_artifact_references: tuple[UniversalReference, ...] = field(default_factory=tuple)
    balance: TransformationBalance | None = None
    evidence_references: tuple[UniversalReference, ...] = field(default_factory=tuple)
    corrects_transformation_id: TypedId | None = None
    correction_reason: str | None = None

    def __post_init__(self) -> None:
        if self.event_id.entity_type != "transformation_event":
            raise ValueError(
                "event_id deve ter entity_type 'transformation_event', recebido "
                f"'{self.event_id.entity_type}'."
            )
        if not isinstance(self.organization_id, OrganizationId):
            raise TypeError("organization_id deve ser OrganizationId.")
        if not isinstance(self.process_type, ProcessType):
            raise TypeError("process_type deve ser ProcessType.")
        require_utc(self.occurred_at, field_name="occurred_at")
        require_utc(self.created_at, field_name="created_at")

        # Invariante 1: pelo menos uma entrada e uma saída.
        if not self.inputs:
            raise ValueError("TransformationEvent exige ao menos uma entrada.")
        if not self.outputs:
            raise ValueError("TransformationEvent exige ao menos uma saída.")

        for participante in self.inputs:
            if not isinstance(participante, TransformationParticipant):
                raise TypeError("inputs deve conter apenas TransformationParticipant.")
            if participante.role is not ParticipantRole.INPUT:
                raise ValueError("Todo participante de 'inputs' deve ter role=INPUT.")
        for participante in self.outputs:
            if not isinstance(participante, TransformationParticipant):
                raise TypeError("outputs deve conter apenas TransformationParticipant.")
            if participante.role is not ParticipantRole.OUTPUT:
                raise ValueError("Todo participante de 'outputs' deve ter role=OUTPUT.")

        # Invariante 5: um sujeito não pode ser input e output do mesmo evento.
        entradas = {p.subject_reference.target_id for p in self.inputs}
        saidas = {p.subject_reference.target_id for p in self.outputs}
        if entradas & saidas:
            raise ValueError("Um sujeito não pode ser input e output do mesmo TransformationEvent.")

        # Invariante 11: nenhuma referência atravessa a fronteira de Organization.
        self._guard_same_organization("facility_reference", self.facility_reference)
        if self.operator_reference is not None:
            self._guard_same_organization("operator_reference", self.operator_reference)
        for referencia in self.source_artifact_references:
            self._guard_same_organization("source_artifact_references", referencia)
        for referencia in self.evidence_references:
            self._guard_same_organization("evidence_references", referencia)
        for participante in (*self.inputs, *self.outputs):
            self._guard_same_organization("subject_reference", participante.subject_reference)
            if participante.lot_or_batch_reference is not None:
                self._guard_same_organization(
                    "lot_or_batch_reference", participante.lot_or_batch_reference
                )

        if self.balance is not None and not isinstance(self.balance, TransformationBalance):
            raise TypeError("balance deve ser TransformationBalance ou None.")

        # ADR-0047, item 1: correção é um TransformationEvent completo novo, nunca
        # um patch — corrects_transformation_id só referencia outro evento, jamais
        # a si mesmo, e correction_reason é obrigatório exatamente quando há correção.
        if self.corrects_transformation_id is not None:
            if self.corrects_transformation_id.entity_type != "transformation_event":
                raise ValueError(
                    "corrects_transformation_id deve ter entity_type "
                    "'transformation_event', recebido "
                    f"'{self.corrects_transformation_id.entity_type}'."
                )
            if self.corrects_transformation_id == self.event_id:
                raise ValueError(
                    "TransformationEvent não pode corrigir a si mesmo "
                    "(corrects_transformation_id == event_id)."
                )
            if self.correction_reason is None or not self.correction_reason.strip():
                raise ValueError(
                    "correction_reason é obrigatório quando corrects_transformation_id "
                    "está definido (ADR-0047, item 1)."
                )
        elif self.correction_reason is not None:
            raise ValueError(
                "correction_reason só se aplica quando corrects_transformation_id "
                "está definido."
            )

    def _guard_same_organization(self, label: str, reference: UniversalReference) -> None:
        if (
            reference.organization_id is not None
            and reference.organization_id != self.organization_id
        ):
            raise ValueError(
                f"{label} pertence a outra Organization: TransformationEvent não "
                "atravessa a fronteira entre tenants (ADR-0046, item 9)."
            )
