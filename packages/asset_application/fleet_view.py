"""Projecao de leitura da frota — Titan Asset A6.

`FleetView` nao altera `Vehicle` nem `WorkOrder`; ele organiza sinais ja
existentes para responder "como esta a frota" por site.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from packages.asset_domain.vehicle import Vehicle, VehicleLifecycleState
from packages.asset_domain.work_order import WorkOrder, WorkOrderState
from packages.shared_kernel import TypedId


class FleetOperationalState(StrEnum):
    AVAILABLE = "AVAILABLE"
    DEGRADED = "DEGRADED"
    MAINTENANCE = "MAINTENANCE"
    WAITING_MATERIAL = "WAITING_MATERIAL"
    SLA_RISK = "SLA_RISK"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class FleetViewSnapshot:
    vehicle: Vehicle
    open_work_orders: tuple[WorkOrder, ...] = ()


@dataclass(frozen=True, slots=True)
class FleetViewLine:
    vehicle_id: TypedId
    site_ref: TypedId | None
    lifecycle_state: VehicleLifecycleState
    operational_state: FleetOperationalState
    open_work_order_refs: tuple[TypedId, ...]
    signals: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FleetView:
    site_ref: TypedId | None
    lines: tuple[FleetViewLine, ...]
    counts_by_state: dict[FleetOperationalState, int]


class FleetViewRepositoryPort(Protocol):
    def list_fleet(self, *, site_ref: TypedId | None = None) -> tuple[FleetViewSnapshot, ...]: ...


def _has_waiting_material(work_orders: tuple[WorkOrder, ...]) -> bool:
    return any(work_order.state is WorkOrderState.WAITING_MATERIAL for work_order in work_orders)


def _has_sla_risk(work_orders: tuple[WorkOrder, ...]) -> bool:
    return any(
        work_order.priority is not None and work_order.priority.score >= 80
        for work_order in work_orders
    )


def _operational_state(snapshot: FleetViewSnapshot) -> FleetOperationalState:
    if _has_waiting_material(snapshot.open_work_orders):
        return FleetOperationalState.WAITING_MATERIAL
    if _has_sla_risk(snapshot.open_work_orders):
        return FleetOperationalState.SLA_RISK
    match snapshot.vehicle.lifecycle_state:
        case VehicleLifecycleState.AVAILABLE:
            return FleetOperationalState.AVAILABLE
        case VehicleLifecycleState.DEGRADED:
            return FleetOperationalState.DEGRADED
        case VehicleLifecycleState.MAINTENANCE_PLANNED | VehicleLifecycleState.IN_MAINTENANCE:
            return FleetOperationalState.MAINTENANCE
        case VehicleLifecycleState.UNAVAILABLE:
            return FleetOperationalState.UNAVAILABLE


def _signals(
    snapshot: FleetViewSnapshot, operational_state: FleetOperationalState
) -> tuple[str, ...]:
    signals: list[str] = [f"VEHICLE:{snapshot.vehicle.lifecycle_state.value}"]
    if any(
        work_order.state is WorkOrderState.WAITING_MATERIAL
        for work_order in snapshot.open_work_orders
    ):
        signals.append("WORK_ORDER:WAITING_MATERIAL")
    if any(
        work_order.priority is not None and work_order.priority.score >= 80
        for work_order in snapshot.open_work_orders
    ):
        signals.append("WORK_ORDER:SLA_RISK")
    signals.append(f"OPERATIONAL:{operational_state.value}")
    return tuple(signals)


def _line(snapshot: FleetViewSnapshot) -> FleetViewLine:
    operational_state = _operational_state(snapshot)
    return FleetViewLine(
        vehicle_id=snapshot.vehicle.vehicle_id,
        site_ref=snapshot.vehicle.site_ref,
        lifecycle_state=snapshot.vehicle.lifecycle_state,
        operational_state=operational_state,
        open_work_order_refs=tuple(
            work_order.work_order_id
            for work_order in snapshot.open_work_orders
            if not work_order.is_terminal
        ),
        signals=_signals(snapshot, operational_state),
    )


def _empty_counts() -> dict[FleetOperationalState, int]:
    return {state: 0 for state in FleetOperationalState}


@dataclass(frozen=True, slots=True)
class FleetViewService:
    repository: FleetViewRepositoryPort

    def get_fleet_view(self, *, site_ref: TypedId | None = None) -> FleetView:
        lines = tuple(
            sorted(
                (_line(snapshot) for snapshot in self.repository.list_fleet(site_ref=site_ref)),
                key=lambda line: str(line.vehicle_id.value),
            )
        )
        counts = _empty_counts()
        for line in lines:
            counts[line.operational_state] += 1
        return FleetView(site_ref=site_ref, lines=lines, counts_by_state=counts)
