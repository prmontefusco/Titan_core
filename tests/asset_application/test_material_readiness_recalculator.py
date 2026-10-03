"""Testes do `MaterialReadinessRecalculator` — Titan Asset A6."""

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

from packages.asset_application.event_recorder import AssetEventRecorder, AssetOperationContext
from packages.asset_application.inventory_service import (
    InventoryService,
    StockPositionRepositoryPort,
    StockReservationRepositoryPort,
    StockTransferRepositoryPort,
)
from packages.asset_application.material_readiness_recalculator import (
    MaterialReadinessRecalculationOutcome,
    MaterialReadinessRecalculator,
)
from packages.asset_application.part_service import PartRepositoryPort
from packages.asset_application.sustainment_contract_service import SLIContractRepositoryPort
from packages.asset_application.vehicle_service import VehicleRepositoryPort, VehicleService
from packages.asset_application.work_order_service import WorkOrderRepositoryPort, WorkOrderService
from packages.asset_domain.inventory import (
    DemandKind,
    DemandRef,
    ReservationState,
    StockOwnership,
    StockPosition,
    StockPurpose,
    StockQuantities,
    StockReservation,
    StockTransfer,
)
from packages.asset_domain.part import Part
from packages.asset_domain.sustainment_contract import SLIContract
from packages.asset_domain.vehicle import Vehicle
from packages.asset_domain.work_order import (
    ContractContext,
    FailureRecord,
    MaterialDemand,
    WorkOrder,
    WorkOrderState,
    WorkTask,
)
from packages.shared_kernel import OrganizationId, TypedId
from tests.asset_support import FakeEventLog

OCCURRED_AT = datetime(2026, 9, 11, tzinfo=UTC)


class InMemoryWorkOrderRepository(WorkOrderRepositoryPort):
    def __init__(self) -> None:
        self.items: dict[str, WorkOrder] = {}

    def save(self, work_order: WorkOrder) -> None:
        self.items[work_order.work_order_id.value.hex] = work_order

    def update(self, work_order: WorkOrder) -> None:
        self.items[work_order.work_order_id.value.hex] = work_order

    def get_by_id(self, work_order_id: TypedId) -> WorkOrder | None:
        return self.items.get(work_order_id.value.hex)


class InMemorySLIContractRepository(SLIContractRepositoryPort):
    def save(self, contract: SLIContract) -> None: ...

    def update(self, contract: SLIContract) -> None: ...

    def get_by_id(self, contract_id: TypedId) -> SLIContract | None:
        return None


class InMemoryPartRepository(PartRepositoryPort):
    def save(self, part: Part) -> None: ...

    def update(self, part: Part) -> None: ...

    def get_by_id(self, part_id: TypedId) -> Part | None:
        return None


class InMemoryVehicleRepository(VehicleRepositoryPort):
    def save(self, vehicle: Vehicle) -> None: ...

    def update(self, vehicle: Vehicle) -> None: ...

    def get_by_id(self, vehicle_id: TypedId) -> Vehicle | None:
        return None


class InMemoryStockPositionRepository(StockPositionRepositoryPort):
    def __init__(self) -> None:
        self.items: dict[str, StockPosition] = {}

    def save(self, position: StockPosition) -> None:
        self.items[position.stock_position_id.value.hex] = position

    def update(self, position: StockPosition) -> None:
        self.items[position.stock_position_id.value.hex] = position

    def get_by_id(self, stock_position_id: TypedId) -> StockPosition | None:
        return self.items.get(stock_position_id.value.hex)


class InMemoryStockReservationRepository(StockReservationRepositoryPort):
    def __init__(self) -> None:
        self.items: dict[str, StockReservation] = {}

    def save(self, reservation: StockReservation) -> None:
        self.items[reservation.reservation_id.value.hex] = reservation

    def update(self, reservation: StockReservation) -> None:
        self.items[reservation.reservation_id.value.hex] = reservation

    def get_by_id(self, reservation_id: TypedId) -> StockReservation | None:
        return self.items.get(reservation_id.value.hex)


class InMemoryStockTransferRepository(StockTransferRepositoryPort):
    def __init__(self) -> None:
        self.items: dict[str, StockTransfer] = {}

    def save(self, transfer: StockTransfer) -> None:
        self.items[transfer.transfer_id.value.hex] = transfer

    def update(self, transfer: StockTransfer) -> None:
        self.items[transfer.transfer_id.value.hex] = transfer

    def get_by_id(self, transfer_id: TypedId) -> StockTransfer | None:
        return self.items.get(transfer_id.value.hex)


def _build_recalculator(
    recorder: AssetEventRecorder,
) -> tuple[
    MaterialReadinessRecalculator,
    InMemoryWorkOrderRepository,
    InMemoryStockPositionRepository,
    InMemoryStockReservationRepository,
    InMemoryStockTransferRepository,
]:
    work_order_repository = InMemoryWorkOrderRepository()
    position_repository = InMemoryStockPositionRepository()
    reservation_repository = InMemoryStockReservationRepository()
    transfer_repository = InMemoryStockTransferRepository()
    inventory_service = InventoryService(
        stock_position_repository=position_repository,
        stock_reservation_repository=reservation_repository,
        stock_transfer_repository=transfer_repository,
        recorder=recorder,
    )
    work_order_service = WorkOrderService(
        repository=work_order_repository,
        sli_contract_repository=InMemorySLIContractRepository(),
        part_repository=InMemoryPartRepository(),
        vehicle_service=VehicleService(repository=InMemoryVehicleRepository(), recorder=recorder),
        inventory_service=inventory_service,
        recorder=recorder,
    )
    return (
        MaterialReadinessRecalculator(
            work_order_service=work_order_service, inventory_service=inventory_service
        ),
        work_order_repository,
        position_repository,
        reservation_repository,
        transfer_repository,
    )


def _work_order(
    organization_id: OrganizationId,
    *,
    part_ref: TypedId,
    reservation_ref: TypedId | None = None,
    state: WorkOrderState,
    qty: Decimal = Decimal(2),
) -> WorkOrder:
    task = WorkTask(
        task_id=TypedId.new("work_task"), description="Trocar componente", mandatory=True
    )
    return WorkOrder(
        work_order_id=TypedId.new("work_order"),
        organization_id=organization_id,
        vehicle_ref=TypedId.new("vehicle"),
        site_ref=TypedId.new("customer_site"),
        contract_context=ContractContext(
            contract_ref=TypedId.new("sli_contract"),
            contract_version_no=1,
            resolved_at=OCCURRED_AT,
        ),
        failure=FailureRecord(mode="Falha", reported_at=OCCURRED_AT),
        tasks=(task,),
        material_demands=(MaterialDemand(part_ref=part_ref, qty=qty, task_id=task.task_id),),
        material_reservations=(reservation_ref,) if reservation_ref else (),
        state=state,
    )


def _position(organization_id: OrganizationId, *, part_ref: TypedId) -> StockPosition:
    return StockPosition(
        stock_position_id=TypedId.new("stock_position"),
        organization_id=organization_id,
        part_ref=part_ref,
        location_ref=TypedId.new("stock_location"),
        purpose=StockPurpose.SERVICE_SLI,
        ownership=StockOwnership.COMPANY_OWNED,
        quantities=StockQuantities(on_hand=Decimal(10)),
    )


def _reservation(
    organization_id: OrganizationId,
    *,
    work_order_id: TypedId,
    stock_position_ref: TypedId,
    qty: Decimal,
    state: ReservationState = ReservationState.HELD,
    demand_kind: DemandKind = DemandKind.WORK_ORDER,
) -> StockReservation:
    return StockReservation(
        reservation_id=TypedId.new("stock_reservation"),
        organization_id=organization_id,
        stock_position_ref=stock_position_ref,
        demand=DemandRef(kind=demand_kind, ref=work_order_id),
        qty=qty,
        purpose=StockPurpose.SERVICE_SLI,
        priority=10,
        state=state,
    )


def test_recalculator_enters_waiting_material_when_planned_work_order_lacks_material(
    recorder: AssetEventRecorder,
    context: AssetOperationContext,
) -> None:
    recalculator, work_orders, positions, reservations, _ = _build_recalculator(recorder)
    part_ref = TypedId.new("part")
    position = _position(context.organization_id, part_ref=part_ref)
    positions.save(position)
    work_order = _work_order(
        context.organization_id, part_ref=part_ref, state=WorkOrderState.PLANNED
    )
    reservation = _reservation(
        context.organization_id,
        work_order_id=work_order.work_order_id,
        stock_position_ref=position.stock_position_id,
        qty=Decimal(2),
        state=ReservationState.RELEASED,
    )
    work_order = replace(work_order, material_reservations=(reservation.reservation_id,))
    work_orders.save(work_order)
    reservations.save(reservation)

    result = recalculator.recalculate_for_reservation(
        context, reservation.reservation_id, occurred_at=OCCURRED_AT
    )

    assert result.outcome is MaterialReadinessRecalculationOutcome.ENTERED_WAITING_MATERIAL
    assert work_orders.get_by_id(work_order.work_order_id).state is WorkOrderState.WAITING_MATERIAL  # type: ignore[union-attr]


def test_recalculator_exits_waiting_material_when_all_material_is_reserved(
    recorder: AssetEventRecorder,
    context: AssetOperationContext,
    event_log: FakeEventLog,
) -> None:
    recalculator, work_orders, positions, reservations, _ = _build_recalculator(recorder)
    part_ref = TypedId.new("part")
    position = _position(context.organization_id, part_ref=part_ref)
    positions.save(position)
    work_order = _work_order(
        context.organization_id, part_ref=part_ref, state=WorkOrderState.WAITING_MATERIAL
    )
    reservation = _reservation(
        context.organization_id,
        work_order_id=work_order.work_order_id,
        stock_position_ref=position.stock_position_id,
        qty=Decimal(2),
    )
    work_order = replace(work_order, material_reservations=(reservation.reservation_id,))
    work_orders.save(work_order)
    reservations.save(reservation)

    result = recalculator.recalculate_for_reservation(
        context, reservation.reservation_id, occurred_at=OCCURRED_AT
    )

    assert result.outcome is MaterialReadinessRecalculationOutcome.EXITED_WAITING_MATERIAL
    assert result.material_fully_reserved is True
    assert work_orders.get_by_id(work_order.work_order_id).state is WorkOrderState.PLANNED  # type: ignore[union-attr]
    assert event_log.events[-1].event_type == "asset.sustainment.work_order_state_changed"


def test_recalculator_ignores_non_work_order_reservation(
    recorder: AssetEventRecorder,
    context: AssetOperationContext,
) -> None:
    recalculator, _, positions, reservations, _ = _build_recalculator(recorder)
    position = _position(context.organization_id, part_ref=TypedId.new("part"))
    positions.save(position)
    reservation = _reservation(
        context.organization_id,
        work_order_id=TypedId.new("sales_order"),
        stock_position_ref=position.stock_position_id,
        qty=Decimal(1),
        demand_kind=DemandKind.SALES_ORDER,
    )
    reservations.save(reservation)

    result = recalculator.recalculate_for_reservation(
        context, reservation.reservation_id, occurred_at=OCCURRED_AT
    )

    assert result.outcome is MaterialReadinessRecalculationOutcome.NO_WORK_ORDER_DEMAND
    assert result.work_order_id is None


def test_recalculator_resolves_work_order_from_linked_transfer(
    recorder: AssetEventRecorder,
    context: AssetOperationContext,
) -> None:
    recalculator, work_orders, positions, reservations, transfers = _build_recalculator(recorder)
    part_ref = TypedId.new("part")
    position = _position(context.organization_id, part_ref=part_ref)
    positions.save(position)
    work_order = _work_order(
        context.organization_id, part_ref=part_ref, state=WorkOrderState.WAITING_MATERIAL
    )
    reservation = _reservation(
        context.organization_id,
        work_order_id=work_order.work_order_id,
        stock_position_ref=position.stock_position_id,
        qty=Decimal(2),
    )
    transfer = StockTransfer(
        transfer_id=TypedId.new("stock_transfer"),
        organization_id=context.organization_id,
        part_ref=part_ref,
        from_location_ref=TypedId.new("stock_location"),
        to_location_ref=TypedId.new("stock_location"),
        qty=Decimal(2),
        linked_reservation_ref=reservation.reservation_id,
    )
    work_order = replace(work_order, material_reservations=(reservation.reservation_id,))
    work_orders.save(work_order)
    reservations.save(reservation)
    transfers.save(transfer)

    result = recalculator.recalculate_for_transfer(
        context, transfer.transfer_id, occurred_at=OCCURRED_AT
    )

    assert result.outcome is MaterialReadinessRecalculationOutcome.EXITED_WAITING_MATERIAL
    assert work_orders.get_by_id(work_order.work_order_id).state is WorkOrderState.PLANNED  # type: ignore[union-attr]
