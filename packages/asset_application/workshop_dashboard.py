"""Projecao de leitura da fila de oficina — Titan Asset A6.

`WorkshopDashboard` nao e agregado nem fonte de verdade. Ele organiza
`WorkOrder`s abertas para responder "o que a oficina faz a seguir", preservando
prioridade explicavel e bloqueios operacionais derivados.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType
from typing import Protocol

from packages.asset_domain.work_order import WorkOrder, WorkOrderState
from packages.shared_kernel import TypedId


@dataclass(frozen=True, slots=True)
class WorkshopDashboardSnapshot:
    work_order: WorkOrder
    reserved_qty_by_part: Mapping[TypedId, Decimal]


@dataclass(frozen=True, slots=True)
class WorkshopDashboardLine:
    work_order_id: TypedId
    vehicle_ref: TypedId
    site_ref: TypedId
    workshop_ref: TypedId | None
    state: WorkOrderState
    priority_score: int
    priority_breakdown: Mapping[str, int]
    priority_evaluation_ref: TypedId | None
    blockers: tuple[str, ...]
    next_action: str


@dataclass(frozen=True, slots=True)
class WorkshopDashboard:
    site_ref: TypedId
    workshop_ref: TypedId | None
    lines: tuple[WorkshopDashboardLine, ...]


class WorkshopDashboardRepositoryPort(Protocol):
    def list_open_by_site(
        self, *, site_ref: TypedId, workshop_ref: TypedId | None = None
    ) -> tuple[WorkshopDashboardSnapshot, ...]: ...


def _material_blockers(snapshot: WorkshopDashboardSnapshot) -> tuple[str, ...]:
    blockers: list[str] = []
    for demand in snapshot.work_order.material_demands:
        reserved = snapshot.reserved_qty_by_part.get(demand.part_ref, Decimal(0))
        if reserved < demand.qty:
            blockers.append(f"MATERIAL_PENDENTE:{demand.part_ref.value}:{reserved}/{demand.qty}")
    return tuple(blockers)


def _blockers(snapshot: WorkshopDashboardSnapshot) -> tuple[str, ...]:
    work_order = snapshot.work_order
    blockers: list[str] = []
    if work_order.priority is None:
        blockers.append("PRIORIDADE_NAO_CALCULADA")
    if not work_order.tasks:
        blockers.append("SEM_TAREFA")
    if not work_order.material_demands:
        blockers.append("SEM_DEMANDA_DE_MATERIAL")
    blockers.extend(_material_blockers(snapshot))
    if work_order.state is WorkOrderState.WAITING_AUTHORIZATION:
        blockers.append("AGUARDANDO_AUTORIZACAO")
    if work_order.state is WorkOrderState.WAITING_MATERIAL:
        blockers.append("AGUARDANDO_MATERIAL")
    if work_order.state is WorkOrderState.TECHNICALLY_COMPLETE:
        blockers.append("VALIDACAO_POS_MANUTENCAO_PENDENTE")
    return tuple(blockers)


def _next_action(state: WorkOrderState, blockers: tuple[str, ...]) -> str:
    if "AGUARDANDO_AUTORIZACAO" in blockers:
        return "resolver_autorizacao"
    if any(blocker.startswith("MATERIAL_PENDENTE:") for blocker in blockers):
        return "resolver_material"
    if "VALIDACAO_POS_MANUTENCAO_PENDENTE" in blockers:
        return "validar_manutencao"
    match state:
        case WorkOrderState.DRAFT:
            return "planejar_ordem"
        case WorkOrderState.PLANNED:
            return "marcar_pronta_ou_aguardar_material"
        case WorkOrderState.READY:
            return "agendar_execucao"
        case WorkOrderState.SCHEDULED | WorkOrderState.WAITING_TECHNICIAN:
            return "iniciar_execucao"
        case WorkOrderState.IN_PROGRESS:
            return "executar_tarefas"
        case WorkOrderState.VALIDATION:
            return "concluir_validacao"
        case WorkOrderState.INTERRUPTED:
            return "retomar_execucao"
        case _:
            return "acompanhar"


def _line(snapshot: WorkshopDashboardSnapshot) -> WorkshopDashboardLine:
    work_order = snapshot.work_order
    priority_score = work_order.priority.score if work_order.priority is not None else 0
    priority_breakdown: Mapping[str, int]
    priority_breakdown = (
        MappingProxyType(dict(work_order.priority.breakdown))
        if work_order.priority is not None
        else MappingProxyType({})
    )
    blockers = _blockers(snapshot)
    return WorkshopDashboardLine(
        work_order_id=work_order.work_order_id,
        vehicle_ref=work_order.vehicle_ref,
        site_ref=work_order.site_ref,
        workshop_ref=work_order.workshop_ref,
        state=work_order.state,
        priority_score=priority_score,
        priority_breakdown=priority_breakdown,
        priority_evaluation_ref=(
            work_order.priority.evaluation_ref if work_order.priority is not None else None
        ),
        blockers=blockers,
        next_action=_next_action(work_order.state, blockers),
    )


@dataclass(frozen=True, slots=True)
class WorkshopDashboardService:
    repository: WorkshopDashboardRepositoryPort

    def get_dashboard(
        self, *, site_ref: TypedId, workshop_ref: TypedId | None = None
    ) -> WorkshopDashboard:
        snapshots = tuple(
            snapshot
            for snapshot in self.repository.list_open_by_site(
                site_ref=site_ref, workshop_ref=workshop_ref
            )
            if not snapshot.work_order.is_terminal
        )
        lines = tuple(sorted((_line(snapshot) for snapshot in snapshots), key=_sort_key))
        return WorkshopDashboard(site_ref=site_ref, workshop_ref=workshop_ref, lines=lines)


def _sort_key(line: WorkshopDashboardLine) -> tuple[int, str]:
    return (-line.priority_score, str(line.work_order_id.value))
