"""Testes unitários de domínio para `WorkOrder` (A2, módulo `sustainment`).

Cobre as 17 transições (T1‑T17) da máquina de estados fixada em
`docs/asset/adr/draft-20260910-primeiro-slice-titan-asset-sustainment.md` §2 e
os invariantes I‑WO‑1..5 de `docs/asset/07_INVARIANTS.md`.
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from packages.asset_domain.work_order import (
    ContractContext,
    FailureRecord,
    MaterialDemand,
    MaterialReservadoExcedeDemanda,
    ObrigacaoAbertaImpedeFechamento,
    PostMaintenanceValidation,
    PriorityScore,
    RemovedComponentDisposition,
    TarefaNaoEncontrada,
    TransicaoDeWorkOrderInvalida,
    ValidationResult,
    WorkOrder,
    WorkOrderState,
    WorkTask,
    WorkTaskState,
    all_material_fully_reserved,
    require_reservations_do_not_exceed_demand,
)
from packages.shared_kernel import OrganizationId, TypedId

MOMENTO = datetime(2026, 9, 11, tzinfo=UTC)


def _contract_context() -> ContractContext:
    return ContractContext(
        contract_ref=TypedId.new("sli_contract"), contract_version_no=1, resolved_at=MOMENTO
    )


def _work_order(**overrides: object) -> WorkOrder:
    defaults: dict[str, object] = dict(
        work_order_id=TypedId.new("work_order"),
        organization_id=OrganizationId(uuid4()),
        vehicle_ref=TypedId.new("vehicle"),
        site_ref=TypedId.new("customer_site"),
        contract_context=_contract_context(),
        failure=FailureRecord(mode="Vazamento hidráulico", reported_at=MOMENTO),
    )
    defaults.update(overrides)
    return WorkOrder(**defaults)  # type: ignore[arg-type]


def _task(*, mandatory: bool = True) -> WorkTask:
    return WorkTask(
        task_id=TypedId.new("work_task"), description="Trocar retentor", mandatory=mandatory
    )


def _planned_work_order() -> WorkOrder:
    task = _task()
    wo = _work_order().add_task(task)
    wo = wo.demand_material(
        MaterialDemand(part_ref=TypedId.new("part"), qty=Decimal(2), task_id=task.task_id)
    )
    return wo.mark_planned()


def _ready_work_order() -> WorkOrder:
    return _planned_work_order().mark_ready(material_fully_reserved=True)


def _scheduled_work_order() -> WorkOrder:
    return _ready_work_order().schedule(technician_and_workshop_allocated=True)


def _in_progress_work_order() -> WorkOrder:
    return _scheduled_work_order().start_progress(vehicle_in_maintenance=True)


# --- construção -----------------------------------------------------------------------


def test_work_order_starts_in_draft() -> None:
    wo = _work_order()
    assert wo.state is WorkOrderState.DRAFT
    assert wo.is_terminal is False


def test_material_demand_must_reference_existing_task() -> None:
    with pytest.raises(TarefaNaoEncontrada):
        _work_order(
            material_demands=(
                MaterialDemand(
                    part_ref=TypedId.new("part"), qty=Decimal(1), task_id=TypedId.new("work_task")
                ),
            )
        )


# --- T1 (abertura, é a construção) + T2 (DRAFT -> PLANNED) -----------------------------


def test_t2_mark_planned_requires_task_and_demand() -> None:
    with pytest.raises(ValueError, match="ao menos uma tarefa"):
        _work_order().mark_planned()


def test_t2_mark_planned_requires_material_demand() -> None:
    wo = _work_order().add_task(_task())
    with pytest.raises(ValueError, match="demanda de material"):
        wo.mark_planned()


def test_t2_mark_planned_succeeds_with_task_and_demand() -> None:
    wo = _planned_work_order()
    assert wo.state is WorkOrderState.PLANNED


# --- T3/T4: PLANNED <-> WAITING_MATERIAL (I-WO-4) ---------------------------------------


def test_t3_t4_waiting_material_round_trip() -> None:
    wo = _planned_work_order().enter_waiting_material()
    assert wo.state is WorkOrderState.WAITING_MATERIAL
    wo = wo.exit_waiting_material()
    assert wo.state is WorkOrderState.PLANNED


def test_enter_waiting_material_rejected_outside_planned() -> None:
    with pytest.raises(TransicaoDeWorkOrderInvalida):
        _work_order().enter_waiting_material()


# --- T5: PLANNED -> READY (I-WO-2) -------------------------------------------------------


def test_t5_mark_ready_requires_material_fully_reserved() -> None:
    wo = _planned_work_order()
    with pytest.raises(ValueError, match="todo material demandado reservado"):
        wo.mark_ready(material_fully_reserved=False)


def test_t5_mark_ready_succeeds() -> None:
    assert _ready_work_order().state is WorkOrderState.READY


# --- T6/T7: PLANNED|READY <-> WAITING_AUTHORIZATION (motivo obrigatório) ----------------


def test_t6_require_authorization_from_planned_remembers_origin() -> None:
    wo = _planned_work_order().require_authorization(reason="Entitlement DENIED.")
    assert wo.state is WorkOrderState.WAITING_AUTHORIZATION
    assert wo.pre_wait_authorization_state is WorkOrderState.PLANNED


def test_t6_require_authorization_from_ready_remembers_origin() -> None:
    wo = _ready_work_order().require_authorization(reason="Exceção de peça excluída.")
    assert wo.pre_wait_authorization_state is WorkOrderState.READY


def test_t6_requires_reason() -> None:
    with pytest.raises(ValueError, match="reason é obrigatório"):
        _planned_work_order().require_authorization(reason="  ")


def test_t7_resolve_authorization_returns_to_remembered_state() -> None:
    wo = _ready_work_order().require_authorization(reason="motivo")
    resolved = wo.resolve_authorization(
        reason="Autorizado pelo gestor.", decision_ref=TypedId.new("decision")
    )
    assert resolved.state is WorkOrderState.READY
    assert resolved.pre_wait_authorization_state is None


def test_t7_requires_reason() -> None:
    wo = _planned_work_order().require_authorization(reason="motivo")
    with pytest.raises(ValueError, match="reason é obrigatório"):
        wo.resolve_authorization(reason="", decision_ref=TypedId.new("decision"))


# --- T8: READY -> SCHEDULED ---------------------------------------------------------------


def test_t8_schedule_requires_allocation() -> None:
    wo = _ready_work_order()
    with pytest.raises(ValueError, match="técnico e oficina alocados"):
        wo.schedule(technician_and_workshop_allocated=False)


def test_t8_schedule_succeeds() -> None:
    assert _scheduled_work_order().state is WorkOrderState.SCHEDULED


# --- T9: SCHEDULED -> WAITING_TECHNICIAN ----------------------------------------------------


def test_t9_mark_waiting_technician() -> None:
    wo = _scheduled_work_order().mark_waiting_technician()
    assert wo.state is WorkOrderState.WAITING_TECHNICIAN


# --- T10: SCHEDULED|WAITING_TECHNICIAN -> IN_PROGRESS -----------------------------------------


def test_t10_start_progress_requires_vehicle_in_maintenance() -> None:
    wo = _scheduled_work_order()
    with pytest.raises(ValueError, match="IN_MAINTENANCE"):
        wo.start_progress(vehicle_in_maintenance=False)


def test_t10_start_progress_from_scheduled_or_waiting_technician() -> None:
    assert (
        _scheduled_work_order().start_progress(vehicle_in_maintenance=True).state
        is WorkOrderState.IN_PROGRESS
    )
    waiting = _scheduled_work_order().mark_waiting_technician()
    assert waiting.start_progress(vehicle_in_maintenance=True).state is WorkOrderState.IN_PROGRESS


# --- T11/T12: IN_PROGRESS <-> INTERRUPTED (motivo obrigatório) ---------------------------------


def test_t11_interrupt_requires_reason() -> None:
    with pytest.raises(ValueError, match="reason é obrigatório"):
        _in_progress_work_order().interrupt(reason="")


def test_t11_t12_interrupt_and_resume() -> None:
    wo = _in_progress_work_order().interrupt(reason="Falta de peça descoberta em campo.")
    assert wo.state is WorkOrderState.INTERRUPTED
    resumed = wo.resume()
    assert resumed.state is WorkOrderState.IN_PROGRESS


# --- tarefas durante IN_PROGRESS ---------------------------------------------------------------


def test_start_and_complete_task_only_during_in_progress() -> None:
    wo = _planned_work_order()
    task_id = wo.tasks[0].task_id
    with pytest.raises(TransicaoDeWorkOrderInvalida):
        wo.start_task(task_id)


def test_start_and_complete_task_lifecycle() -> None:
    wo = _in_progress_work_order()
    task_id = wo.tasks[0].task_id
    wo = wo.start_task(task_id)
    assert wo.tasks[0].state is WorkTaskState.IN_PROGRESS
    wo = wo.complete_task(task_id, labor_entry="2h - técnico A")
    assert wo.tasks[0].state is WorkTaskState.DONE
    assert wo.tasks[0].labor_entries == ("2h - técnico A",)


def test_record_removed_component_requires_in_progress() -> None:
    wo = _planned_work_order()
    with pytest.raises(TransicaoDeWorkOrderInvalida):
        wo.record_removed_component(
            RemovedComponentDisposition(part_ref=TypedId.new("part"), disposition="SCRAP")
        )


# --- T13: IN_PROGRESS -> TECHNICALLY_COMPLETE (I-WO-1) ------------------------------------------


def test_t13_rejects_open_mandatory_task() -> None:
    wo = _in_progress_work_order()
    with pytest.raises(ObrigacaoAbertaImpedeFechamento):
        wo.complete_technically(diagnosis="d", root_cause="r", resolution="s")


def test_t13_requires_diagnosis_root_cause_resolution() -> None:
    wo = _in_progress_work_order()
    task_id = wo.tasks[0].task_id
    wo = wo.start_task(task_id).complete_task(task_id)
    with pytest.raises(ValueError, match="diagnosis"):
        wo.complete_technically(diagnosis="", root_cause="r", resolution="s")


def test_t13_succeeds_when_all_mandatory_tasks_done() -> None:
    wo = _in_progress_work_order()
    task_id = wo.tasks[0].task_id
    wo = wo.start_task(task_id).complete_task(task_id)
    wo = wo.complete_technically(
        diagnosis="Retentor rompido", root_cause="Desgaste", resolution="Substituído"
    )
    assert wo.state is WorkOrderState.TECHNICALLY_COMPLETE


def test_t13_ignores_non_mandatory_open_tasks() -> None:
    optional = _task(mandatory=False)
    wo = _in_progress_work_order().add_task(optional)
    task_id = wo.tasks[0].task_id  # a mandatória original
    wo = wo.start_task(task_id).complete_task(task_id)
    # optional segue PENDING, mas não bloqueia porque não é mandatory.
    wo = wo.complete_technically(diagnosis="d", root_cause="r", resolution="s")
    assert wo.state is WorkOrderState.TECHNICALLY_COMPLETE


def _technically_complete_work_order() -> WorkOrder:
    wo = _in_progress_work_order()
    task_id = wo.tasks[0].task_id
    wo = wo.start_task(task_id).complete_task(task_id)
    return wo.complete_technically(diagnosis="d", root_cause="r", resolution="s")


# --- T14/T15: TECHNICALLY_COMPLETE <-> VALIDATION -------------------------------------------------


def test_t14_send_to_validation() -> None:
    wo = _technically_complete_work_order().send_to_validation()
    assert wo.state is WorkOrderState.VALIDATION


def test_t15_fail_validation_requires_reason_and_fail_result() -> None:
    wo = _technically_complete_work_order().send_to_validation()
    passing = PostMaintenanceValidation(
        validated_at=MOMENTO, validator_ref=TypedId.new("user"), result=ValidationResult.PASS_
    )
    with pytest.raises(ValueError, match="result == FAIL"):
        wo.fail_validation(reason="motivo", validation=passing)


def test_t15_fail_validation_returns_to_technically_complete() -> None:
    wo = _technically_complete_work_order().send_to_validation()
    failing = PostMaintenanceValidation(
        validated_at=MOMENTO, validator_ref=TypedId.new("user"), result=ValidationResult.FAIL
    )
    reproved = wo.fail_validation(reason="Vazamento persiste.", validation=failing)
    assert reproved.state is WorkOrderState.TECHNICALLY_COMPLETE
    assert reproved.validation is failing


# --- T16: VALIDATION -> COMPLETED (I-WO-1) -----------------------------------------------------


def test_t16_close_requires_passing_validation() -> None:
    wo = _technically_complete_work_order().send_to_validation()
    failing = PostMaintenanceValidation(
        validated_at=MOMENTO, validator_ref=TypedId.new("user"), result=ValidationResult.FAIL
    )
    with pytest.raises(ObrigacaoAbertaImpedeFechamento):
        wo.close(validation=failing)


def test_t16_close_succeeds_with_passing_validation() -> None:
    wo = _technically_complete_work_order().send_to_validation()
    passing = PostMaintenanceValidation(
        validated_at=MOMENTO, validator_ref=TypedId.new("user"), result=ValidationResult.PASS_
    )
    closed = wo.close(validation=passing)
    assert closed.state is WorkOrderState.COMPLETED
    assert closed.is_terminal is True


def test_completed_work_order_cannot_add_task() -> None:
    wo = _technically_complete_work_order().send_to_validation()
    passing = PostMaintenanceValidation(
        validated_at=MOMENTO, validator_ref=TypedId.new("user"), result=ValidationResult.PASS_
    )
    closed = wo.close(validation=passing)
    with pytest.raises(TransicaoDeWorkOrderInvalida):
        closed.add_task(_task())


# --- T17: qualquer não-terminal -> CANCELLED (motivo obrigatório) -------------------------------


@pytest.mark.parametrize(
    "make_work_order",
    [
        _work_order,
        _planned_work_order,
        _ready_work_order,
        _scheduled_work_order,
        _in_progress_work_order,
        _technically_complete_work_order,
    ],
)
def test_t17_cancel_from_any_non_terminal_state(make_work_order) -> None:  # type: ignore[no-untyped-def]
    wo = make_work_order().cancel(reason="Cliente desistiu do reparo.")
    assert wo.state is WorkOrderState.CANCELLED
    assert wo.is_terminal is True


def test_t17_cancel_requires_reason() -> None:
    with pytest.raises(ValueError, match="reason é obrigatório"):
        _planned_work_order().cancel(reason="")


def test_t17_cancel_rejected_from_terminal_state() -> None:
    cancelled = _work_order().cancel(reason="motivo")
    with pytest.raises(TransicaoDeWorkOrderInvalida):
        cancelled.cancel(reason="outro motivo")


def test_cancel_clears_pending_authorization_wait() -> None:
    wo = _ready_work_order().require_authorization(reason="motivo")
    cancelled = wo.cancel(reason="Cancelada durante espera de autorização.")
    assert cancelled.state is WorkOrderState.CANCELLED
    assert cancelled.pre_wait_authorization_state is None


# --- prioridade (I-WO-5) ------------------------------------------------------------------------


def test_priority_score_breakdown_must_sum_to_score() -> None:
    with pytest.raises(ValueError, match="deve ser igual a score"):
        PriorityScore(score=50, breakdown={"a": 30, "b": 10})


def test_recalculate_priority() -> None:
    score = PriorityScore(score=55, breakdown={"criticidade": 30, "sla": 25})
    wo = _work_order().recalculate_priority(score)
    assert wo.priority is score


# --- I-WO-2 (cross-agregado) ---------------------------------------------------------------------


def test_require_reservations_do_not_exceed_demand_accepts_within_limit() -> None:
    part_ref = TypedId.new("part")
    wo = _work_order().add_task(_task())
    wo = wo.demand_material(
        MaterialDemand(part_ref=part_ref, qty=Decimal(5), task_id=wo.tasks[0].task_id)
    )
    require_reservations_do_not_exceed_demand(wo, {part_ref: Decimal(5)})


def test_require_reservations_do_not_exceed_demand_rejects_excess() -> None:
    part_ref = TypedId.new("part")
    wo = _work_order().add_task(_task())
    wo = wo.demand_material(
        MaterialDemand(part_ref=part_ref, qty=Decimal(2), task_id=wo.tasks[0].task_id)
    )
    with pytest.raises(MaterialReservadoExcedeDemanda):
        require_reservations_do_not_exceed_demand(wo, {part_ref: Decimal(3)})


def test_all_material_fully_reserved_true_only_when_every_part_covered() -> None:
    part_ref = TypedId.new("part")
    wo = _work_order().add_task(_task())
    wo = wo.demand_material(
        MaterialDemand(part_ref=part_ref, qty=Decimal(3), task_id=wo.tasks[0].task_id)
    )
    assert all_material_fully_reserved(wo, {part_ref: Decimal(2)}) is False
    assert all_material_fully_reserved(wo, {part_ref: Decimal(3)}) is True
