"""Testes do `WorkshopDashboardService` — Titan Asset A6."""

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

from packages.asset_application.workshop_dashboard import (
    WorkshopDashboardRepositoryPort,
    WorkshopDashboardService,
    WorkshopDashboardSnapshot,
)
from packages.asset_domain.work_order import (
    ContractContext,
    FailureRecord,
    MaterialDemand,
    PriorityScore,
    WorkOrder,
    WorkOrderState,
    WorkTask,
)
from packages.shared_kernel import OrganizationId, TypedId

OCCURRED_AT = datetime(2026, 9, 11, tzinfo=UTC)


class InMemoryWorkshopDashboardRepository(WorkshopDashboardRepositoryPort):
    def __init__(self, snapshots: tuple[WorkshopDashboardSnapshot, ...]) -> None:
        self.snapshots = snapshots
        self.calls: list[tuple[TypedId, TypedId | None]] = []

    def list_open_by_site(
        self, *, site_ref: TypedId, workshop_ref: TypedId | None = None
    ) -> tuple[WorkshopDashboardSnapshot, ...]:
        self.calls.append((site_ref, workshop_ref))
        return tuple(
            snapshot
            for snapshot in self.snapshots
            if snapshot.work_order.site_ref == site_ref
            and (workshop_ref is None or snapshot.work_order.workshop_ref == workshop_ref)
        )


def _work_order(
    *,
    site_ref: TypedId,
    workshop_ref: TypedId | None = None,
    state: WorkOrderState = WorkOrderState.PLANNED,
    priority: PriorityScore | None = None,
    demand_qty: Decimal = Decimal(1),
) -> WorkOrder:
    task = WorkTask(
        task_id=TypedId.new("work_task"), description="Trocar componente", mandatory=True
    )
    part_ref = TypedId.new("part")
    return WorkOrder(
        work_order_id=TypedId.new("work_order"),
        organization_id=OrganizationId.new(),
        vehicle_ref=TypedId.new("vehicle"),
        site_ref=site_ref,
        workshop_ref=workshop_ref,
        contract_context=ContractContext(
            contract_ref=TypedId.new("sli_contract"),
            contract_version_no=1,
            resolved_at=OCCURRED_AT,
        ),
        failure=FailureRecord(mode="Falha", reported_at=OCCURRED_AT),
        tasks=(task,),
        material_demands=(MaterialDemand(part_ref=part_ref, qty=demand_qty, task_id=task.task_id),),
        state=state,
        priority=priority,
    )


def _snapshot(work_order: WorkOrder, *, reserved_qty: Decimal) -> WorkshopDashboardSnapshot:
    part_ref = work_order.material_demands[0].part_ref
    return WorkshopDashboardSnapshot(
        work_order=work_order,
        reserved_qty_by_part={part_ref: reserved_qty},
    )


def test_dashboard_orders_by_priority_and_keeps_breakdown() -> None:
    site_ref = TypedId.new("customer_site")
    low = _work_order(
        site_ref=site_ref,
        priority=PriorityScore(score=20, breakdown={"idade": 5, "sla": 15}),
    )
    high_priority = PriorityScore(
        score=80,
        breakdown={"criticidade": 50, "sla": 30},
        evaluation_ref=TypedId.new("evaluation"),
    )
    high = _work_order(
        site_ref=site_ref,
        priority=high_priority,
    )
    service = WorkshopDashboardService(
        InMemoryWorkshopDashboardRepository(
            (_snapshot(low, reserved_qty=Decimal(1)), _snapshot(high, reserved_qty=Decimal(1)))
        )
    )

    dashboard = service.get_dashboard(site_ref=site_ref)

    assert [line.work_order_id for line in dashboard.lines] == [
        high.work_order_id,
        low.work_order_id,
    ]
    first = dashboard.lines[0]
    assert first.priority_score == 80
    assert dict(first.priority_breakdown) == {"criticidade": 50, "sla": 30}
    assert first.priority_evaluation_ref == high_priority.evaluation_ref
    assert first.blockers == ()


def test_dashboard_explains_material_blocker_and_next_action() -> None:
    site_ref = TypedId.new("customer_site")
    work_order = _work_order(
        site_ref=site_ref,
        state=WorkOrderState.WAITING_MATERIAL,
        priority=PriorityScore(score=30, breakdown={"sla": 30}),
        demand_qty=Decimal(3),
    )
    service = WorkshopDashboardService(
        InMemoryWorkshopDashboardRepository((_snapshot(work_order, reserved_qty=Decimal(1)),))
    )

    line = service.get_dashboard(site_ref=site_ref).lines[0]

    assert any(blocker.startswith("MATERIAL_PENDENTE:") for blocker in line.blockers)
    assert "AGUARDANDO_MATERIAL" in line.blockers
    assert line.next_action == "resolver_material"


def test_dashboard_filters_workshop_and_ignores_terminal_work_orders() -> None:
    site_ref = TypedId.new("customer_site")
    workshop_ref = TypedId.new("workshop")
    other_workshop_ref = TypedId.new("workshop")
    selected = _work_order(
        site_ref=site_ref,
        workshop_ref=workshop_ref,
        priority=PriorityScore(score=10, breakdown={"sla": 10}),
    )
    other = _work_order(
        site_ref=site_ref,
        workshop_ref=other_workshop_ref,
        priority=PriorityScore(score=90, breakdown={"sla": 90}),
    )
    terminal = replace(
        selected, work_order_id=TypedId.new("work_order"), state=WorkOrderState.COMPLETED
    )
    repository = InMemoryWorkshopDashboardRepository(
        (
            _snapshot(selected, reserved_qty=Decimal(1)),
            _snapshot(other, reserved_qty=Decimal(1)),
            _snapshot(terminal, reserved_qty=Decimal(1)),
        )
    )
    service = WorkshopDashboardService(repository)

    dashboard = service.get_dashboard(site_ref=site_ref, workshop_ref=workshop_ref)

    assert repository.calls == [(site_ref, workshop_ref)]
    assert [line.work_order_id for line in dashboard.lines] == [selected.work_order_id]
