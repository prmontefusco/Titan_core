"""Recalculador de `WAITING_MATERIAL` — Titan Asset A6.

Reavalia I-WO-4 depois de eventos de inventário. Este serviço não consome
broker nem cria worker; ele é a unidade de aplicação que um handler de evento
pode chamar quando receber `stock_reserved`, `stock_reservation_released`,
`stock_consumed` ou `transfer_received`.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from packages.asset_application.event_recorder import AssetOperationContext
from packages.asset_application.inventory_service import InventoryService
from packages.asset_application.work_order_service import WorkOrderService
from packages.asset_domain.inventory import DemandKind, ReservationState
from packages.asset_domain.work_order import WorkOrder, WorkOrderState, all_material_fully_reserved
from packages.shared_kernel import TypedId


class MaterialReadinessRecalculationOutcome(StrEnum):
    ENTERED_WAITING_MATERIAL = "ENTERED_WAITING_MATERIAL"
    EXITED_WAITING_MATERIAL = "EXITED_WAITING_MATERIAL"
    UNCHANGED = "UNCHANGED"
    NO_WORK_ORDER_DEMAND = "NO_WORK_ORDER_DEMAND"


@dataclass(frozen=True, slots=True)
class MaterialReadinessRecalculation:
    work_order_id: TypedId | None
    outcome: MaterialReadinessRecalculationOutcome
    material_fully_reserved: bool | None = None


@dataclass(frozen=True, slots=True)
class MaterialReadinessRecalculator:
    work_order_service: WorkOrderService
    inventory_service: InventoryService

    def recalculate_for_reservation(
        self,
        context: AssetOperationContext,
        reservation_id: TypedId,
        *,
        occurred_at: datetime,
    ) -> MaterialReadinessRecalculation:
        reservation = self.inventory_service.get_reservation(reservation_id)
        if reservation is None or reservation.demand.kind is not DemandKind.WORK_ORDER:
            return MaterialReadinessRecalculation(
                work_order_id=None,
                outcome=MaterialReadinessRecalculationOutcome.NO_WORK_ORDER_DEMAND,
            )
        return self.recalculate_for_work_order(
            context, reservation.demand.ref, occurred_at=occurred_at
        )

    def recalculate_for_transfer(
        self,
        context: AssetOperationContext,
        transfer_id: TypedId,
        *,
        occurred_at: datetime,
    ) -> MaterialReadinessRecalculation:
        transfer = self.inventory_service.get_transfer(transfer_id)
        if transfer is None or transfer.linked_reservation_ref is None:
            return MaterialReadinessRecalculation(
                work_order_id=None,
                outcome=MaterialReadinessRecalculationOutcome.NO_WORK_ORDER_DEMAND,
            )
        return self.recalculate_for_reservation(
            context, transfer.linked_reservation_ref, occurred_at=occurred_at
        )

    def recalculate_for_work_order(
        self,
        context: AssetOperationContext,
        work_order_id: TypedId,
        *,
        occurred_at: datetime,
    ) -> MaterialReadinessRecalculation:
        work_order = self.work_order_service.get_work_order(work_order_id)
        if work_order is None:
            return MaterialReadinessRecalculation(
                work_order_id=work_order_id,
                outcome=MaterialReadinessRecalculationOutcome.NO_WORK_ORDER_DEMAND,
            )
        fully_reserved = all_material_fully_reserved(
            work_order, self._reserved_qty_by_part(work_order)
        )
        if work_order.state is WorkOrderState.PLANNED and not fully_reserved:
            updated = self.work_order_service.enter_waiting_material(
                context, work_order_id, occurred_at=occurred_at
            )
            return MaterialReadinessRecalculation(
                work_order_id=updated.work_order_id,
                outcome=MaterialReadinessRecalculationOutcome.ENTERED_WAITING_MATERIAL,
                material_fully_reserved=False,
            )
        if work_order.state is WorkOrderState.WAITING_MATERIAL and fully_reserved:
            updated = self.work_order_service.exit_waiting_material(
                context, work_order_id, occurred_at=occurred_at
            )
            return MaterialReadinessRecalculation(
                work_order_id=updated.work_order_id,
                outcome=MaterialReadinessRecalculationOutcome.EXITED_WAITING_MATERIAL,
                material_fully_reserved=True,
            )
        return MaterialReadinessRecalculation(
            work_order_id=work_order.work_order_id,
            outcome=MaterialReadinessRecalculationOutcome.UNCHANGED,
            material_fully_reserved=fully_reserved,
        )

    def _reserved_qty_by_part(self, work_order: WorkOrder) -> dict[TypedId, Decimal]:
        totals: dict[TypedId, Decimal] = {}
        for reservation_id in work_order.material_reservations:
            reservation = self.inventory_service.get_reservation(reservation_id)
            if reservation is None or reservation.state is ReservationState.RELEASED:
                continue
            position = self.inventory_service.get_stock_position(reservation.stock_position_ref)
            if position is None:
                continue
            totals[position.part_ref] = totals.get(position.part_ref, Decimal(0)) + reservation.qty
        return totals
