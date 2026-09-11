"""Agregado `WorkOrder` — Titan Asset & Sustainment (A2, módulo `sustainment`).

O coração transacional do slice (`docs/asset/05_DOMAIN_MODEL.md` §2.4). Máquina
de estados **T1‑T17** fixada em
`docs/asset/adr/draft-20260910-primeiro-slice-titan-asset-sustainment.md` §2 —
não copiada de outro produto (constituição §16). Cada método de transição aqui
é a metade "estados de origem permitidos · destino · pré‑requisito verificável
localmente" da definição de transição da constituição §16; ator/permissão são
`AssetOperationContext`/aplicação (A4), e evento/auditoria são responsabilidade
de quem consome o retorno deste método (a aplicação decide o `event_type` de
`08_DOMAIN_EVENTS.md` a partir do `(from_state, to_state)`).

Invariantes (`docs/asset/07_INVARIANTS.md`): I‑WO‑1 (não fecha com obrigação
aberta nem sem validação), I‑WO‑2 (reservado ≤ demandado — cross‑agregado,
`require_reservations_do_not_exceed_demand`), I‑WO‑3 (toda transição audita;
motivo obrigatório nos pontos marcados na tabela T1‑T17), I‑WO‑4
(`WAITING_MATERIAL` é condição, não estado decorativo — a aplicação decide
quando chamar `enter_waiting_material`/`exit_waiting_material`, este módulo só
garante que a transição de estado é legal), I‑WO‑5 (`PriorityScore`
determinístico — a `Rule` que o calcula é do Core/GOV; aqui só o VO).

Onde uma transição da tabela exige um fato externo (técnico alocado, veículo
em manutenção, decisão de exceção), o método pede essa evidência como
parâmetro explícito — o mesmo padrão de `vehicle.py` `return_to_service` — em
vez de confiar silenciosamente na ordem de chamadas.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum

from packages.shared_kernel import OrganizationId, TypedId
from packages.shared_kernel.temporal import require_utc


class WorkOrderState(StrEnum):
    DRAFT = "DRAFT"
    PLANNED = "PLANNED"
    WAITING_MATERIAL = "WAITING_MATERIAL"
    READY = "READY"
    WAITING_AUTHORIZATION = "WAITING_AUTHORIZATION"
    SCHEDULED = "SCHEDULED"
    WAITING_TECHNICIAN = "WAITING_TECHNICIAN"
    IN_PROGRESS = "IN_PROGRESS"
    INTERRUPTED = "INTERRUPTED"
    TECHNICALLY_COMPLETE = "TECHNICALLY_COMPLETE"
    VALIDATION = "VALIDATION"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


TERMINAL_STATES = frozenset({WorkOrderState.COMPLETED, WorkOrderState.CANCELLED})
WAITING_STATES = frozenset(
    {
        WorkOrderState.WAITING_MATERIAL,
        WorkOrderState.WAITING_AUTHORIZATION,
        WorkOrderState.WAITING_TECHNICIAN,
    }
)


class WorkTaskState(StrEnum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"


class ValidationResult(StrEnum):
    PASS_ = "PASS"
    FAIL = "FAIL"


class TransicaoDeWorkOrderInvalida(ValueError):
    """Transição fora da tabela T1‑T17 (`docs/asset/adr/...` §2)."""


class ObrigacaoAbertaImpedeFechamento(ValueError):
    """`WorkOrder` não fecha com tarefa obrigatória aberta ou sem validação (I‑WO‑1)."""


class MaterialReservadoExcedeDemanda(ValueError):
    """`Σ reservado > Σ demandado` para alguma peça (I‑WO‑2)."""


class TarefaNaoEncontrada(KeyError):
    """`WorkTask` referenciada não existe nesta `WorkOrder`."""


def _require_reason(reason: str, *, transition: str) -> None:
    if not reason or not reason.strip():
        raise ValueError(f"reason é obrigatório na transição {transition} (I-WO-3).")


@dataclass(frozen=True, slots=True)
class ContractContext:
    """VO — congelado na abertura da WO (I‑SLI‑1). `05_DOMAIN_MODEL.md` §2.4."""

    contract_ref: TypedId
    contract_version_no: int
    resolved_at: datetime

    def __post_init__(self) -> None:
        if self.contract_ref.entity_type != "sli_contract":
            raise ValueError(
                "contract_ref deve ter entity_type 'sli_contract', recebido "
                f"'{self.contract_ref.entity_type}'."
            )
        if self.contract_version_no < 1:
            raise ValueError("contract_version_no deve ser >= 1.")
        require_utc(self.resolved_at, field_name="resolved_at")


@dataclass(frozen=True, slots=True)
class FailureRecord:
    """VO leve — `05_DOMAIN_MODEL.md` §2.4."""

    mode: str
    reported_at: datetime
    affected_position: str | None = None

    def __post_init__(self) -> None:
        if not self.mode or not self.mode.strip():
            raise ValueError("mode não pode ser vazio.")
        require_utc(self.reported_at, field_name="reported_at")


@dataclass(frozen=True, slots=True)
class MaterialDemand:
    """VO — `05_DOMAIN_MODEL.md` §2.4."""

    part_ref: TypedId
    qty: Decimal
    task_id: TypedId

    def __post_init__(self) -> None:
        if self.part_ref.entity_type != "part":
            raise ValueError(
                f"part_ref deve ter entity_type 'part', recebido '{self.part_ref.entity_type}'."
            )
        if self.qty <= 0:
            raise ValueError("qty deve ser > 0.")
        if self.task_id.entity_type != "work_task":
            raise ValueError(
                f"task_id deve ter entity_type 'work_task', recebido '{self.task_id.entity_type}'."
            )


@dataclass(frozen=True, slots=True)
class WorkTask:
    """Entidade interna. `05_DOMAIN_MODEL.md` §2.4. `mandatory` é factual — não
    derivado (constituição §42: sem booleano derivado sem derivação; aqui o
    booleano é um dado de entrada legítimo, não um estado calculado)."""

    task_id: TypedId
    description: str
    mandatory: bool
    state: WorkTaskState = WorkTaskState.PENDING
    labor_entries: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.task_id.entity_type != "work_task":
            raise ValueError(
                f"task_id deve ter entity_type 'work_task', recebido '{self.task_id.entity_type}'."
            )
        if not self.description or not self.description.strip():
            raise ValueError("description não pode ser vazia.")

    def start(self) -> "WorkTask":
        if self.state is not WorkTaskState.PENDING:
            raise TransicaoDeWorkOrderInvalida(
                f"start só é válido a partir de PENDING, tarefa está '{self.state.value}'."
            )
        return replace(self, state=WorkTaskState.IN_PROGRESS)

    def complete(self, *, labor_entry: str | None = None) -> "WorkTask":
        if self.state is not WorkTaskState.IN_PROGRESS:
            raise TransicaoDeWorkOrderInvalida(
                f"complete só é válido a partir de IN_PROGRESS, tarefa está '{self.state.value}'."
            )
        entries = self.labor_entries + (labor_entry,) if labor_entry else self.labor_entries
        return replace(self, state=WorkTaskState.DONE, labor_entries=entries)


@dataclass(frozen=True, slots=True)
class RemovedComponentDisposition:
    """VO — `05_DOMAIN_MODEL.md` §2.4."""

    part_ref: TypedId
    disposition: str
    serial: str | None = None

    def __post_init__(self) -> None:
        if self.part_ref.entity_type != "part":
            raise ValueError(
                f"part_ref deve ter entity_type 'part', recebido '{self.part_ref.entity_type}'."
            )
        if not self.disposition or not self.disposition.strip():
            raise ValueError("disposition não pode ser vazia.")


@dataclass(frozen=True, slots=True)
class PostMaintenanceValidation:
    """VO — obrigatória antes de `COMPLETED` (I‑WO‑1)."""

    validated_at: datetime
    validator_ref: TypedId
    result: ValidationResult
    notes: str | None = None

    def __post_init__(self) -> None:
        require_utc(self.validated_at, field_name="validated_at")


@dataclass(frozen=True, slots=True)
class PriorityScore:
    """VO — `05_DOMAIN_MODEL.md` §2.4/§4; I‑WO‑5. `breakdown` é o fator→pontos
    que sustenta o `score` (constituição §22) — nunca só o número. O cálculo em
    si é uma `Rule` governada do Core; este VO só guarda o resultado + o
    rastro."""

    score: int
    breakdown: Mapping[str, int]
    evaluation_ref: TypedId | None = None

    def __post_init__(self) -> None:
        if not (0 <= self.score <= 100):
            raise ValueError("score deve estar entre 0 e 100.")
        if sum(self.breakdown.values()) != self.score:
            raise ValueError(
                f"Σ breakdown ({sum(self.breakdown.values())}) deve ser igual a score "
                f"({self.score}) — a resposta é sempre explicável, nunca só o número."
            )


@dataclass(frozen=True, slots=True)
class WorkOrder:
    """Raiz de agregado. `05_DOMAIN_MODEL.md` §2.4. Não é "God Aggregate"
    (constituição §15): referencia `Vehicle`/`SLIContract`/`StockReservation`
    por id, nunca os compõe."""

    work_order_id: TypedId
    organization_id: OrganizationId
    vehicle_ref: TypedId
    site_ref: TypedId
    contract_context: ContractContext
    failure: FailureRecord
    workshop_ref: TypedId | None = None
    tasks: tuple[WorkTask, ...] = ()
    material_demands: tuple[MaterialDemand, ...] = ()
    material_reservations: tuple[TypedId, ...] = ()
    state: WorkOrderState = WorkOrderState.DRAFT
    pre_wait_authorization_state: WorkOrderState | None = None
    priority: PriorityScore | None = None
    diagnosis: str | None = None
    root_cause: str | None = None
    resolution: str | None = None
    removed_components: tuple[RemovedComponentDisposition, ...] = ()
    validation: PostMaintenanceValidation | None = None
    version: int = 1
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        require_utc(self.created_at, field_name="created_at")
        if self.work_order_id.entity_type != "work_order":
            raise ValueError(
                "work_order_id deve ter entity_type 'work_order', recebido "
                f"'{self.work_order_id.entity_type}'."
            )
        if self.vehicle_ref.entity_type != "vehicle":
            raise ValueError(
                f"vehicle_ref deve ter entity_type 'vehicle', recebido "
                f"'{self.vehicle_ref.entity_type}'."
            )
        if self.site_ref.entity_type != "customer_site":
            raise ValueError(
                "site_ref deve ter entity_type 'customer_site', recebido "
                f"'{self.site_ref.entity_type}'."
            )
        task_ids = [task.task_id for task in self.tasks]
        if len(set(task_ids)) != len(task_ids):
            raise ValueError("tasks não pode repetir o mesmo task_id.")
        known_tasks = set(task_ids)
        for demand in self.material_demands:
            if demand.task_id not in known_tasks:
                raise TarefaNaoEncontrada(
                    f"MaterialDemand referencia task_id '{demand.task_id.value}' inexistente."
                )

    # --- consultas -----------------------------------------------------------------

    def _get_task(self, task_id: TypedId) -> WorkTask:
        for task in self.tasks:
            if task.task_id == task_id:
                return task
        raise TarefaNaoEncontrada(f"Tarefa '{task_id.value}' não encontrada nesta WorkOrder.")

    @property
    def all_mandatory_tasks_done(self) -> bool:
        return all(task.state is WorkTaskState.DONE for task in self.tasks if task.mandatory)

    @property
    def is_terminal(self) -> bool:
        return self.state in TERMINAL_STATES

    # --- tarefas e demanda (não mudam o estado da WO) -------------------------------

    def add_task(self, task: WorkTask) -> "WorkOrder":
        if self.is_terminal:
            raise TransicaoDeWorkOrderInvalida("Não é possível adicionar tarefa a uma WO terminal.")
        if any(existing.task_id == task.task_id for existing in self.tasks):
            raise ValueError(f"Tarefa '{task.task_id.value}' já existe nesta WorkOrder.")
        return replace(self, tasks=self.tasks + (task,), version=self.version + 1)

    def demand_material(self, demand: MaterialDemand) -> "WorkOrder":
        if self.is_terminal:
            raise TransicaoDeWorkOrderInvalida("Não é possível demandar material numa WO terminal.")
        self._get_task(demand.task_id)
        return replace(
            self, material_demands=self.material_demands + (demand,), version=self.version + 1
        )

    def start_task(self, task_id: TypedId) -> "WorkOrder":
        if self.state is not WorkOrderState.IN_PROGRESS:
            raise TransicaoDeWorkOrderInvalida(
                f"Tarefas só iniciam com a WO em IN_PROGRESS, estado atual '{self.state.value}'."
            )
        updated = tuple(task.start() if task.task_id == task_id else task for task in self.tasks)
        if updated == self.tasks:
            raise TarefaNaoEncontrada(f"Tarefa '{task_id.value}' não encontrada.")
        return replace(self, tasks=updated, version=self.version + 1)

    def complete_task(self, task_id: TypedId, *, labor_entry: str | None = None) -> "WorkOrder":
        if self.state is not WorkOrderState.IN_PROGRESS:
            raise TransicaoDeWorkOrderInvalida(
                f"Tarefas só completam com a WO em IN_PROGRESS, estado atual '{self.state.value}'."
            )
        task = self._get_task(task_id)
        updated = tuple(
            task.complete(labor_entry=labor_entry) if t.task_id == task_id else t
            for t in self.tasks
        )
        return replace(self, tasks=updated, version=self.version + 1)

    def record_removed_component(self, disposition: RemovedComponentDisposition) -> "WorkOrder":
        if self.state is not WorkOrderState.IN_PROGRESS:
            raise TransicaoDeWorkOrderInvalida(
                "Remoção de componente só é registrada com a WO em IN_PROGRESS, estado atual "
                f"'{self.state.value}'."
            )
        return replace(
            self,
            removed_components=self.removed_components + (disposition,),
            version=self.version + 1,
        )

    def recalculate_priority(self, priority: PriorityScore) -> "WorkOrder":
        return replace(self, priority=priority, version=self.version + 1)

    # --- T2: DRAFT -> PLANNED --------------------------------------------------------

    def mark_planned(self) -> "WorkOrder":
        if self.state is not WorkOrderState.DRAFT:
            raise TransicaoDeWorkOrderInvalida(
                f"mark_planned só é válido a partir de DRAFT, estado atual '{self.state.value}'."
            )
        if not self.tasks:
            raise ValueError("PLANNED exige ao menos uma tarefa (T2).")
        if not self.material_demands:
            raise ValueError("PLANNED exige ao menos uma demanda de material registrada (T2).")
        return replace(self, state=WorkOrderState.PLANNED, version=self.version + 1)

    # --- T3/T4: PLANNED <-> WAITING_MATERIAL (I-WO-4, "sistema") ---------------------

    def enter_waiting_material(self) -> "WorkOrder":
        if self.state is not WorkOrderState.PLANNED:
            raise TransicaoDeWorkOrderInvalida(
                "enter_waiting_material só é válido a partir de PLANNED, estado atual "
                f"'{self.state.value}'."
            )
        return replace(self, state=WorkOrderState.WAITING_MATERIAL, version=self.version + 1)

    def exit_waiting_material(self) -> "WorkOrder":
        if self.state is not WorkOrderState.WAITING_MATERIAL:
            raise TransicaoDeWorkOrderInvalida(
                "exit_waiting_material só é válido a partir de WAITING_MATERIAL, estado atual "
                f"'{self.state.value}'."
            )
        return replace(self, state=WorkOrderState.PLANNED, version=self.version + 1)

    # --- T5: PLANNED -> READY ---------------------------------------------------------

    def mark_ready(self, *, material_fully_reserved: bool) -> "WorkOrder":
        if self.state is not WorkOrderState.PLANNED:
            raise TransicaoDeWorkOrderInvalida(
                f"mark_ready só é válido a partir de PLANNED, estado atual '{self.state.value}'."
            )
        if not material_fully_reserved:
            raise ValueError(
                "READY exige todo material demandado reservado (I-WO-2) — a aplicação deve "
                "confirmar isso antes de chamar mark_ready."
            )
        return replace(self, state=WorkOrderState.READY, version=self.version + 1)

    # --- T6/T7: PLANNED|READY <-> WAITING_AUTHORIZATION -------------------------------

    def require_authorization(self, *, reason: str) -> "WorkOrder":
        if self.state not in (WorkOrderState.PLANNED, WorkOrderState.READY):
            raise TransicaoDeWorkOrderInvalida(
                "require_authorization só é válido a partir de PLANNED/READY, estado atual "
                f"'{self.state.value}'."
            )
        _require_reason(reason, transition="T6 (WAITING_AUTHORIZATION)")
        return replace(
            self,
            state=WorkOrderState.WAITING_AUTHORIZATION,
            pre_wait_authorization_state=self.state,
            version=self.version + 1,
        )

    def resolve_authorization(self, *, reason: str, decision_ref: TypedId) -> "WorkOrder":
        if self.state is not WorkOrderState.WAITING_AUTHORIZATION:
            raise TransicaoDeWorkOrderInvalida(
                "resolve_authorization só é válido a partir de WAITING_AUTHORIZATION, estado "
                f"atual '{self.state.value}'."
            )
        _require_reason(reason, transition="T7 (retorno de WAITING_AUTHORIZATION)")
        if self.pre_wait_authorization_state is None:
            raise ValueError("WorkOrder sem estado anterior registrado — dado inconsistente.")
        return replace(
            self,
            state=self.pre_wait_authorization_state,
            pre_wait_authorization_state=None,
            version=self.version + 1,
        )

    # --- T8: READY -> SCHEDULED --------------------------------------------------------

    def schedule(self, *, technician_and_workshop_allocated: bool) -> "WorkOrder":
        if self.state is not WorkOrderState.READY:
            raise TransicaoDeWorkOrderInvalida(
                f"schedule só é válido a partir de READY, estado atual '{self.state.value}'."
            )
        if not technician_and_workshop_allocated:
            raise ValueError("SCHEDULED exige técnico e oficina alocados (T8).")
        return replace(self, state=WorkOrderState.SCHEDULED, version=self.version + 1)

    # --- T9: SCHEDULED -> WAITING_TECHNICIAN --------------------------------------------

    def mark_waiting_technician(self) -> "WorkOrder":
        if self.state is not WorkOrderState.SCHEDULED:
            raise TransicaoDeWorkOrderInvalida(
                "mark_waiting_technician só é válido a partir de SCHEDULED, estado atual "
                f"'{self.state.value}'."
            )
        return replace(self, state=WorkOrderState.WAITING_TECHNICIAN, version=self.version + 1)

    # --- T10: SCHEDULED|WAITING_TECHNICIAN -> IN_PROGRESS ---------------------------------

    def start_progress(self, *, vehicle_in_maintenance: bool) -> "WorkOrder":
        if self.state not in (WorkOrderState.SCHEDULED, WorkOrderState.WAITING_TECHNICIAN):
            raise TransicaoDeWorkOrderInvalida(
                "start_progress só é válido a partir de SCHEDULED/WAITING_TECHNICIAN, estado "
                f"atual '{self.state.value}'."
            )
        if not vehicle_in_maintenance:
            raise ValueError(
                "IN_PROGRESS exige o veículo em IN_MAINTENANCE (T10) — coordenar com "
                "Vehicle.transition_lifecycle antes de chamar start_progress."
            )
        return replace(self, state=WorkOrderState.IN_PROGRESS, version=self.version + 1)

    # --- T11/T12: IN_PROGRESS <-> INTERRUPTED ---------------------------------------------

    def interrupt(self, *, reason: str) -> "WorkOrder":
        if self.state is not WorkOrderState.IN_PROGRESS:
            raise TransicaoDeWorkOrderInvalida(
                f"interrupt só é válido a partir de IN_PROGRESS, estado atual '{self.state.value}'."
            )
        _require_reason(reason, transition="T11 (INTERRUPTED)")
        return replace(self, state=WorkOrderState.INTERRUPTED, version=self.version + 1)

    def resume(self) -> "WorkOrder":
        if self.state is not WorkOrderState.INTERRUPTED:
            raise TransicaoDeWorkOrderInvalida(
                f"resume só é válido a partir de INTERRUPTED, estado atual '{self.state.value}'."
            )
        return replace(self, state=WorkOrderState.IN_PROGRESS, version=self.version + 1)

    # --- T13: IN_PROGRESS -> TECHNICALLY_COMPLETE (I-WO-1) --------------------------------

    def complete_technically(
        self, *, diagnosis: str, root_cause: str, resolution: str
    ) -> "WorkOrder":
        if self.state is not WorkOrderState.IN_PROGRESS:
            raise TransicaoDeWorkOrderInvalida(
                "complete_technically só é válido a partir de IN_PROGRESS, estado atual "
                f"'{self.state.value}'."
            )
        if not self.all_mandatory_tasks_done:
            raise ObrigacaoAbertaImpedeFechamento(
                "Há tarefa obrigatória não concluída — TECHNICALLY_COMPLETE exige todas DONE "
                "(I-WO-1)."
            )
        for field_name, value in (
            ("diagnosis", diagnosis),
            ("root_cause", root_cause),
            ("resolution", resolution),
        ):
            if not value or not value.strip():
                raise ValueError(f"{field_name} é obrigatório em TECHNICALLY_COMPLETE (I-WO-1).")
        return replace(
            self,
            state=WorkOrderState.TECHNICALLY_COMPLETE,
            diagnosis=diagnosis,
            root_cause=root_cause,
            resolution=resolution,
            version=self.version + 1,
        )

    # --- T14/T15: TECHNICALLY_COMPLETE <-> VALIDATION -------------------------------------

    def send_to_validation(self) -> "WorkOrder":
        if self.state is not WorkOrderState.TECHNICALLY_COMPLETE:
            raise TransicaoDeWorkOrderInvalida(
                "send_to_validation só é válido a partir de TECHNICALLY_COMPLETE, estado atual "
                f"'{self.state.value}'."
            )
        return replace(self, state=WorkOrderState.VALIDATION, version=self.version + 1)

    def fail_validation(self, *, reason: str, validation: PostMaintenanceValidation) -> "WorkOrder":
        if self.state is not WorkOrderState.VALIDATION:
            raise TransicaoDeWorkOrderInvalida(
                f"fail_validation só é válido a partir de VALIDATION, estado atual "
                f"'{self.state.value}'."
            )
        if validation.result is not ValidationResult.FAIL:
            raise ValueError("fail_validation exige validation.result == FAIL.")
        _require_reason(reason, transition="T15 (validação reprovada)")
        return replace(
            self,
            state=WorkOrderState.TECHNICALLY_COMPLETE,
            validation=validation,
            version=self.version + 1,
        )

    # --- T16: VALIDATION -> COMPLETED (I-WO-1) --------------------------------------------

    def close(self, *, validation: PostMaintenanceValidation) -> "WorkOrder":
        if self.state is not WorkOrderState.VALIDATION:
            raise TransicaoDeWorkOrderInvalida(
                f"close só é válido a partir de VALIDATION, estado atual '{self.state.value}'."
            )
        if validation.result is not ValidationResult.PASS_:
            raise ObrigacaoAbertaImpedeFechamento("close exige validation.result == PASS (I-WO-1).")
        if not self.all_mandatory_tasks_done:
            # Defesa em profundidade: T13 já garante isto, mas COMPLETED nunca
            # deve depender só de um estado intermediário não ter sido violado.
            raise ObrigacaoAbertaImpedeFechamento(
                "Há tarefa obrigatória não concluída — COMPLETED exige todas DONE (I-WO-1)."
            )
        return replace(
            self,
            state=WorkOrderState.COMPLETED,
            validation=validation,
            version=self.version + 1,
        )

    # --- T17: qualquer não-terminal -> CANCELLED -------------------------------------------

    def cancel(self, *, reason: str) -> "WorkOrder":
        if self.is_terminal:
            raise TransicaoDeWorkOrderInvalida(
                f"cancel não é válido a partir de um estado terminal ('{self.state.value}')."
            )
        _require_reason(reason, transition="T17 (CANCELLED)")
        return replace(
            self,
            state=WorkOrderState.CANCELLED,
            pre_wait_authorization_state=None,
            version=self.version + 1,
        )


def require_reservations_do_not_exceed_demand(
    work_order: WorkOrder, reserved_qty_by_part: Mapping[TypedId, Decimal]
) -> None:
    """I‑WO‑2. `reserved_qty_by_part` é a soma de `StockReservation.qty` ativas
    vinculadas a esta WO, por peça, que a aplicação monta consultando o
    repositório — cross‑agregado, mesmo padrão de `configuration.py`/
    `sustainment_contract.py`."""
    demanded_by_part: dict[TypedId, Decimal] = {}
    for demand in work_order.material_demands:
        demanded_by_part[demand.part_ref] = (
            demanded_by_part.get(demand.part_ref, Decimal(0)) + demand.qty
        )
    for part_ref, reserved in reserved_qty_by_part.items():
        demanded = demanded_by_part.get(part_ref, Decimal(0))
        if reserved > demanded:
            raise MaterialReservadoExcedeDemanda(
                f"Peça '{part_ref.value}': reservado ({reserved}) excede demandado ({demanded})."
            )


def all_material_fully_reserved(
    work_order: WorkOrder, reserved_qty_by_part: Mapping[TypedId, Decimal]
) -> bool:
    """Fato que a aplicação computa e passa para `WorkOrder.mark_ready`
    (T5) — reservado == demandado para toda peça demandada."""
    demanded_by_part: dict[TypedId, Decimal] = {}
    for demand in work_order.material_demands:
        demanded_by_part[demand.part_ref] = (
            demanded_by_part.get(demand.part_ref, Decimal(0)) + demand.qty
        )
    return all(
        reserved_qty_by_part.get(part_ref, Decimal(0)) >= demanded
        for part_ref, demanded in demanded_by_part.items()
    )
