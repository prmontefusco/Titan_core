"""Testes do `WorkOrderService` — Titan Asset (A4)."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from packages.asset_application.event_recorder import AssetEventRecorder, AssetOperationContext
from packages.asset_application.inventory_service import (
    InventoryService,
    StockPositionRepositoryPort,
    StockReservationRepositoryPort,
    StockTransferRepositoryPort,
)
from packages.asset_application.sustainment_contract_service import SLIContractRepositoryPort
from packages.asset_application.vehicle_service import VehicleRepositoryPort, VehicleService
from packages.asset_application.work_order_service import (
    WorkOrderRepositoryPort,
    WorkOrderService,
)
from packages.asset_domain.events import (
    SUSTAINMENT_MATERIAL_RESERVED,
    SUSTAINMENT_POST_MAINTENANCE_VALIDATED,
    SUSTAINMENT_WORK_ORDER_CANCELLED,
    SUSTAINMENT_WORK_ORDER_COMPLETED,
    SUSTAINMENT_WORK_ORDER_OPENED,
    VEHICLE_RETURNED_TO_SERVICE,
)
from packages.asset_domain.inventory import (
    ReservationState,
    StockOwnership,
    StockPosition,
    StockPurpose,
    StockQuantities,
    StockReservation,
    StockTransfer,
)
from packages.asset_domain.sustainment_contract import (
    ContractVersion,
    KnownValidInterval,
    SLIContract,
)
from packages.asset_domain.vehicle import (
    AssetOwnership,
    Vehicle,
    VehicleIdentifiers,
    VehicleLifecycleState,
)
from packages.asset_domain.work_order import (
    FailureRecord,
    MaterialReservadoExcedeDemanda,
    WorkOrder,
    WorkOrderState,
)
from packages.shared_kernel import TypedId
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
    def __init__(self) -> None:
        self.items: dict[str, SLIContract] = {}

    def save(self, contract: SLIContract) -> None:
        self.items[contract.contract_id.value.hex] = contract

    def update(self, contract: SLIContract) -> None:
        self.items[contract.contract_id.value.hex] = contract

    def get_by_id(self, contract_id: TypedId) -> SLIContract | None:
        return self.items.get(contract_id.value.hex)


class InMemoryVehicleRepository(VehicleRepositoryPort):
    def __init__(self) -> None:
        self.items: dict[str, Vehicle] = {}

    def save(self, vehicle: Vehicle) -> None:
        self.items[vehicle.vehicle_id.value.hex] = vehicle

    def update(self, vehicle: Vehicle) -> None:
        self.items[vehicle.vehicle_id.value.hex] = vehicle

    def get_by_id(self, vehicle_id: TypedId) -> Vehicle | None:
        return self.items.get(vehicle_id.value.hex)


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


def _build_service(recorder: AssetEventRecorder) -> tuple[WorkOrderService, VehicleService]:
    vehicle_service = VehicleService(repository=InMemoryVehicleRepository(), recorder=recorder)
    inventory_service = InventoryService(
        stock_position_repository=InMemoryStockPositionRepository(),
        stock_reservation_repository=InMemoryStockReservationRepository(),
        stock_transfer_repository=InMemoryStockTransferRepository(),
        recorder=recorder,
    )
    work_order_service = WorkOrderService(
        repository=InMemoryWorkOrderRepository(),
        sli_contract_repository=InMemorySLIContractRepository(),
        vehicle_service=vehicle_service,
        inventory_service=inventory_service,
        recorder=recorder,
    )
    return work_order_service, vehicle_service


def _open_contract_and_vehicle(
    work_order_service: WorkOrderService,
    vehicle_service: VehicleService,
    context: AssetOperationContext,
) -> tuple[TypedId, TypedId]:
    vehicle = vehicle_service.register_vehicle(
        context,
        model_ref=TypedId.new("vehicle_model"),
        identifiers=VehicleIdentifiers(serial_number="SN-WO-1"),
        ownership=AssetOwnership.COMPANY,
    )
    contract = SLIContract(
        contract_id=TypedId.new("sli_contract"),
        organization_id=context.organization_id,
        customer_ref=TypedId.new("customer"),
        versions=(
            ContractVersion(
                version_no=1,
                effective=KnownValidInterval(
                    valid_from=datetime(2026, 1, 1, tzinfo=UTC),
                    known_at=datetime(2026, 1, 1, tzinfo=UTC),
                ),
            ),
        ),
    )
    work_order_service.sli_contract_repository.save(contract)
    return vehicle.vehicle_id, contract.contract_id


def test_full_lifecycle_open_to_close(
    recorder: AssetEventRecorder, context: AssetOperationContext, event_log: FakeEventLog
) -> None:
    work_order_service, vehicle_service = _build_service(recorder)
    vehicle_id, contract_id = _open_contract_and_vehicle(
        work_order_service, vehicle_service, context
    )
    part_ref = TypedId.new("part")
    site_ref = TypedId.new("customer_site")

    work_order = work_order_service.open_work_order(
        context,
        vehicle_ref=vehicle_id,
        site_ref=site_ref,
        contract_ref=contract_id,
        failure=FailureRecord(mode="Vazamento hidráulico", reported_at=OCCURRED_AT),
        at_instant=OCCURRED_AT,
        occurred_at=OCCURRED_AT,
    )
    assert work_order.state is WorkOrderState.DRAFT
    assert work_order.contract_context.contract_version_no == 1
    event_log.only(SUSTAINMENT_WORK_ORDER_OPENED)

    with_task = work_order_service.add_task(
        context,
        work_order.work_order_id,
        description="Trocar retentor",
        mandatory=True,
        occurred_at=OCCURRED_AT,
    )
    task_id = with_task.tasks[0].task_id

    with_demand = work_order_service.demand_material(
        context,
        work_order.work_order_id,
        part_ref=part_ref,
        qty=Decimal(2),
        task_id=task_id,
        occurred_at=OCCURRED_AT,
    )
    assert len(with_demand.material_demands) == 1

    position = work_order_service.inventory_service.open_stock_position(
        context,
        part_ref=part_ref,
        location_ref=TypedId.new("stock_location"),
        purpose=StockPurpose.SERVICE_SLI,
        ownership=StockOwnership.COMPANY_OWNED,
        quantities=StockQuantities(on_hand=Decimal(10)),
        occurred_at=OCCURRED_AT,
    )

    with_reservation = work_order_service.reserve_material_for_work_order(
        context,
        work_order.work_order_id,
        stock_position_id=position.stock_position_id,
        part_ref=part_ref,
        qty=Decimal(2),
        priority=1,
        occurred_at=OCCURRED_AT,
    )
    assert len(with_reservation.material_reservations) == 1
    event_log.only(SUSTAINMENT_MATERIAL_RESERVED)

    planned = work_order_service.mark_planned(
        context, work_order.work_order_id, occurred_at=OCCURRED_AT
    )
    ready = work_order_service.mark_ready(context, planned.work_order_id, occurred_at=OCCURRED_AT)
    assert ready.state is WorkOrderState.READY

    scheduled = work_order_service.schedule(
        context,
        ready.work_order_id,
        technician_and_workshop_allocated=True,
        occurred_at=OCCURRED_AT,
    )
    in_progress = work_order_service.start_progress(
        context, scheduled.work_order_id, vehicle_in_maintenance=True, occurred_at=OCCURRED_AT
    )
    assert in_progress.state is WorkOrderState.IN_PROGRESS

    started = work_order_service.start_task(
        context, in_progress.work_order_id, task_id=task_id, occurred_at=OCCURRED_AT
    )
    completed_task = work_order_service.complete_task(
        context, started.work_order_id, task_id=task_id, labor_entry="2h", occurred_at=OCCURRED_AT
    )

    technically_complete = work_order_service.complete_technically(
        context,
        completed_task.work_order_id,
        diagnosis="Retentor rompido",
        root_cause="Desgaste",
        resolution="Substituído",
        occurred_at=OCCURRED_AT,
    )
    in_validation = work_order_service.send_to_validation(
        context, technically_complete.work_order_id, occurred_at=OCCURRED_AT
    )
    assert in_validation.state is WorkOrderState.VALIDATION

    # Vehicle precisa estar IN_MAINTENANCE para return_to_service (I-VEH-3).
    vehicle_service.transition_lifecycle(
        context,
        vehicle_id,
        new_state=VehicleLifecycleState.MAINTENANCE_PLANNED,
        occurred_at=OCCURRED_AT,
    )
    vehicle_service.transition_lifecycle(
        context, vehicle_id, new_state=VehicleLifecycleState.IN_MAINTENANCE, occurred_at=OCCURRED_AT
    )

    closed = work_order_service.close_work_order(
        context,
        in_validation.work_order_id,
        validator_ref=TypedId.new("user"),
        occurred_at=OCCURRED_AT,
    )
    assert closed.state is WorkOrderState.COMPLETED
    event_log.only(SUSTAINMENT_WORK_ORDER_COMPLETED)
    event_log.only(VEHICLE_RETURNED_TO_SERVICE)
    validated_events = event_log.of_type(SUSTAINMENT_POST_MAINTENANCE_VALIDATED)
    assert len(validated_events) == 1

    reloaded_vehicle = vehicle_service.get_vehicle(vehicle_id)
    assert reloaded_vehicle is not None
    assert reloaded_vehicle.lifecycle_state is VehicleLifecycleState.AVAILABLE


def test_reserve_material_beyond_demand_raises(
    recorder: AssetEventRecorder, context: AssetOperationContext
) -> None:
    work_order_service, vehicle_service = _build_service(recorder)
    vehicle_id, contract_id = _open_contract_and_vehicle(
        work_order_service, vehicle_service, context
    )
    part_ref = TypedId.new("part")

    work_order = work_order_service.open_work_order(
        context,
        vehicle_ref=vehicle_id,
        site_ref=TypedId.new("customer_site"),
        contract_ref=contract_id,
        failure=FailureRecord(mode="Falha", reported_at=OCCURRED_AT),
        at_instant=OCCURRED_AT,
        occurred_at=OCCURRED_AT,
    )
    with_task = work_order_service.add_task(
        context,
        work_order.work_order_id,
        description="Trocar peça",
        mandatory=True,
        occurred_at=OCCURRED_AT,
    )
    task_id = with_task.tasks[0].task_id
    work_order_service.demand_material(
        context,
        work_order.work_order_id,
        part_ref=part_ref,
        qty=Decimal(2),
        task_id=task_id,
        occurred_at=OCCURRED_AT,
    )
    position = work_order_service.inventory_service.open_stock_position(
        context,
        part_ref=part_ref,
        location_ref=TypedId.new("stock_location"),
        purpose=StockPurpose.SERVICE_SLI,
        ownership=StockOwnership.COMPANY_OWNED,
        quantities=StockQuantities(on_hand=Decimal(10)),
        occurred_at=OCCURRED_AT,
    )

    with pytest.raises(MaterialReservadoExcedeDemanda):
        work_order_service.reserve_material_for_work_order(
            context,
            work_order.work_order_id,
            stock_position_id=position.stock_position_id,
            part_ref=part_ref,
            qty=Decimal(3),
            priority=1,
            occurred_at=OCCURRED_AT,
        )


def test_cancel_releases_material_reservations(
    recorder: AssetEventRecorder, context: AssetOperationContext, event_log: FakeEventLog
) -> None:
    work_order_service, vehicle_service = _build_service(recorder)
    vehicle_id, contract_id = _open_contract_and_vehicle(
        work_order_service, vehicle_service, context
    )
    part_ref = TypedId.new("part")

    work_order = work_order_service.open_work_order(
        context,
        vehicle_ref=vehicle_id,
        site_ref=TypedId.new("customer_site"),
        contract_ref=contract_id,
        failure=FailureRecord(mode="Falha", reported_at=OCCURRED_AT),
        at_instant=OCCURRED_AT,
        occurred_at=OCCURRED_AT,
    )
    with_task = work_order_service.add_task(
        context,
        work_order.work_order_id,
        description="Trocar peça",
        mandatory=True,
        occurred_at=OCCURRED_AT,
    )
    task_id = with_task.tasks[0].task_id
    work_order_service.demand_material(
        context,
        work_order.work_order_id,
        part_ref=part_ref,
        qty=Decimal(2),
        task_id=task_id,
        occurred_at=OCCURRED_AT,
    )
    position = work_order_service.inventory_service.open_stock_position(
        context,
        part_ref=part_ref,
        location_ref=TypedId.new("stock_location"),
        purpose=StockPurpose.SERVICE_SLI,
        ownership=StockOwnership.COMPANY_OWNED,
        quantities=StockQuantities(on_hand=Decimal(10)),
        occurred_at=OCCURRED_AT,
    )
    reserved = work_order_service.reserve_material_for_work_order(
        context,
        work_order.work_order_id,
        stock_position_id=position.stock_position_id,
        part_ref=part_ref,
        qty=Decimal(2),
        priority=1,
        occurred_at=OCCURRED_AT,
    )
    reservation_id = reserved.material_reservations[0]

    cancelled = work_order_service.cancel_work_order(
        context,
        work_order.work_order_id,
        reason="Cliente desistiu do reparo.",
        occurred_at=OCCURRED_AT,
    )
    assert cancelled.state is WorkOrderState.CANCELLED
    event_log.only(SUSTAINMENT_WORK_ORDER_CANCELLED)

    released_reservation = work_order_service.inventory_service.get_reservation(reservation_id)
    assert released_reservation is not None
    assert released_reservation.state is ReservationState.RELEASED


def test_fail_validation_returns_to_technically_complete(
    recorder: AssetEventRecorder, context: AssetOperationContext
) -> None:
    work_order_service, vehicle_service = _build_service(recorder)
    vehicle_id, contract_id = _open_contract_and_vehicle(
        work_order_service, vehicle_service, context
    )

    work_order = work_order_service.open_work_order(
        context,
        vehicle_ref=vehicle_id,
        site_ref=TypedId.new("customer_site"),
        contract_ref=contract_id,
        failure=FailureRecord(mode="Falha", reported_at=OCCURRED_AT),
        at_instant=OCCURRED_AT,
        occurred_at=OCCURRED_AT,
    )
    with_task = work_order_service.add_task(
        context,
        work_order.work_order_id,
        description="Trocar peça",
        mandatory=True,
        occurred_at=OCCURRED_AT,
    )
    task_id = with_task.tasks[0].task_id
    part_ref = TypedId.new("part")
    work_order_service.demand_material(
        context,
        work_order.work_order_id,
        part_ref=part_ref,
        qty=Decimal(1),
        task_id=task_id,
        occurred_at=OCCURRED_AT,
    )
    position = work_order_service.inventory_service.open_stock_position(
        context,
        part_ref=part_ref,
        location_ref=TypedId.new("stock_location"),
        purpose=StockPurpose.SERVICE_SLI,
        ownership=StockOwnership.COMPANY_OWNED,
        quantities=StockQuantities(on_hand=Decimal(10)),
        occurred_at=OCCURRED_AT,
    )
    work_order_service.reserve_material_for_work_order(
        context,
        work_order.work_order_id,
        stock_position_id=position.stock_position_id,
        part_ref=part_ref,
        qty=Decimal(1),
        priority=1,
        occurred_at=OCCURRED_AT,
    )
    planned = work_order_service.mark_planned(
        context, work_order.work_order_id, occurred_at=OCCURRED_AT
    )
    ready = work_order_service.mark_ready(context, planned.work_order_id, occurred_at=OCCURRED_AT)
    scheduled = work_order_service.schedule(
        context,
        ready.work_order_id,
        technician_and_workshop_allocated=True,
        occurred_at=OCCURRED_AT,
    )
    in_progress = work_order_service.start_progress(
        context, scheduled.work_order_id, vehicle_in_maintenance=True, occurred_at=OCCURRED_AT
    )
    started = work_order_service.start_task(
        context, in_progress.work_order_id, task_id=task_id, occurred_at=OCCURRED_AT
    )
    completed_task = work_order_service.complete_task(
        context, started.work_order_id, task_id=task_id, occurred_at=OCCURRED_AT
    )
    technically_complete = work_order_service.complete_technically(
        context,
        completed_task.work_order_id,
        diagnosis="d",
        root_cause="r",
        resolution="s",
        occurred_at=OCCURRED_AT,
    )
    in_validation = work_order_service.send_to_validation(
        context, technically_complete.work_order_id, occurred_at=OCCURRED_AT
    )

    reproved = work_order_service.perform_post_maintenance_validation(
        context,
        in_validation.work_order_id,
        validator_ref=TypedId.new("user"),
        reason="Vazamento persiste.",
        occurred_at=OCCURRED_AT,
    )
    assert reproved.state is WorkOrderState.TECHNICALLY_COMPLETE
