"""Testes do `InventoryService` — Titan Asset (A4)."""

from datetime import UTC, datetime
from decimal import Decimal

from packages.asset_application.event_recorder import AssetEventRecorder, AssetOperationContext
from packages.asset_application.inventory_service import (
    InventoryService,
    StockPositionRepositoryPort,
    StockReservationRepositoryPort,
    StockTransferRepositoryPort,
)
from packages.asset_domain.events import (
    INVENTORY_STOCK_ADJUSTED,
    INVENTORY_STOCK_CONSUMED,
    INVENTORY_STOCK_POSITION_OPENED,
    INVENTORY_STOCK_RESERVATION_ALLOCATED,
    INVENTORY_STOCK_RESERVATION_RELEASED,
    INVENTORY_STOCK_RESERVED,
    INVENTORY_TRANSFER_DISPATCHED,
    INVENTORY_TRANSFER_RECEIVED,
    INVENTORY_TRANSFER_REQUESTED,
)
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
    TransferState,
)
from packages.shared_kernel import TypedId
from tests.asset_support import FakeEventLog

OCCURRED_AT = datetime(2026, 9, 11, tzinfo=UTC)


class InMemoryStockPositionRepository(StockPositionRepositoryPort):
    def __init__(self) -> None:
        self.positions: dict[str, StockPosition] = {}

    def save(self, position: StockPosition) -> None:
        self.positions[position.stock_position_id.value.hex] = position

    def update(self, position: StockPosition) -> None:
        self.positions[position.stock_position_id.value.hex] = position

    def get_by_id(self, stock_position_id: TypedId) -> StockPosition | None:
        return self.positions.get(stock_position_id.value.hex)


class InMemoryStockReservationRepository(StockReservationRepositoryPort):
    def __init__(self) -> None:
        self.reservations: dict[str, StockReservation] = {}

    def save(self, reservation: StockReservation) -> None:
        self.reservations[reservation.reservation_id.value.hex] = reservation

    def update(self, reservation: StockReservation) -> None:
        self.reservations[reservation.reservation_id.value.hex] = reservation

    def get_by_id(self, reservation_id: TypedId) -> StockReservation | None:
        return self.reservations.get(reservation_id.value.hex)


class InMemoryStockTransferRepository(StockTransferRepositoryPort):
    def __init__(self) -> None:
        self.transfers: dict[str, StockTransfer] = {}

    def save(self, transfer: StockTransfer) -> None:
        self.transfers[transfer.transfer_id.value.hex] = transfer

    def update(self, transfer: StockTransfer) -> None:
        self.transfers[transfer.transfer_id.value.hex] = transfer

    def get_by_id(self, transfer_id: TypedId) -> StockTransfer | None:
        return self.transfers.get(transfer_id.value.hex)


def _service(recorder: AssetEventRecorder) -> InventoryService:
    return InventoryService(
        stock_position_repository=InMemoryStockPositionRepository(),
        stock_reservation_repository=InMemoryStockReservationRepository(),
        stock_transfer_repository=InMemoryStockTransferRepository(),
        recorder=recorder,
    )


def test_open_stock_position_and_adjust(
    recorder: AssetEventRecorder, context: AssetOperationContext, event_log: FakeEventLog
) -> None:
    service = _service(recorder)
    position = service.open_stock_position(
        context,
        part_ref=TypedId.new("part"),
        location_ref=TypedId.new("stock_location"),
        purpose=StockPurpose.SERVICE_SLI,
        ownership=StockOwnership.COMPANY_OWNED,
        quantities=StockQuantities(on_hand=Decimal(10)),
        occurred_at=OCCURRED_AT,
    )
    assert position.available == Decimal(10)
    event_log.only(INVENTORY_STOCK_POSITION_OPENED)

    adjusted = service.adjust_stock(
        context,
        position.stock_position_id,
        deltas={"on_hand": Decimal(5)},
        reason="Recebimento de nota fiscal.",
        actor_ref=TypedId.new("user"),
        occurred_at=OCCURRED_AT,
    )
    assert adjusted.available == Decimal(15)
    event_log.only(INVENTORY_STOCK_ADJUSTED)


def test_reserve_release_allocate_and_consume(
    recorder: AssetEventRecorder, context: AssetOperationContext, event_log: FakeEventLog
) -> None:
    service = _service(recorder)
    position = service.open_stock_position(
        context,
        part_ref=TypedId.new("part"),
        location_ref=TypedId.new("stock_location"),
        purpose=StockPurpose.SERVICE_SLI,
        ownership=StockOwnership.COMPANY_OWNED,
        quantities=StockQuantities(on_hand=Decimal(10)),
        occurred_at=OCCURRED_AT,
    )

    updated_position, reservation = service.reserve_stock(
        context,
        position.stock_position_id,
        demand=DemandRef(kind=DemandKind.WORK_ORDER, ref=TypedId.new("work_order")),
        qty=Decimal(4),
        purpose=StockPurpose.SERVICE_SLI,
        priority=1,
        occurred_at=OCCURRED_AT,
    )
    assert updated_position.available == Decimal(6)
    assert reservation.state is ReservationState.HELD
    event_log.only(INVENTORY_STOCK_RESERVED)

    allocated = service.allocate_reservation(
        context, reservation.reservation_id, occurred_at=OCCURRED_AT
    )
    assert allocated.state is ReservationState.ALLOCATED
    event_log.only(INVENTORY_STOCK_RESERVATION_ALLOCATED)

    consumed_position, consumed_reservation = service.consume_stock(
        context,
        reservation.reservation_id,
        work_order_ref=TypedId.new("work_order"),
        qty=Decimal(4),
        occurred_at=OCCURRED_AT,
    )
    assert consumed_reservation.state is ReservationState.CONSUMED
    assert consumed_position.quantities.on_hand == Decimal(6)
    assert consumed_position.available == Decimal(6)
    event_log.only(INVENTORY_STOCK_CONSUMED)


def test_reserve_and_release(
    recorder: AssetEventRecorder, context: AssetOperationContext, event_log: FakeEventLog
) -> None:
    service = _service(recorder)
    position = service.open_stock_position(
        context,
        part_ref=TypedId.new("part"),
        location_ref=TypedId.new("stock_location"),
        purpose=StockPurpose.SERVICE_SLI,
        ownership=StockOwnership.COMPANY_OWNED,
        quantities=StockQuantities(on_hand=Decimal(10)),
        occurred_at=OCCURRED_AT,
    )
    _, reservation = service.reserve_stock(
        context,
        position.stock_position_id,
        demand=DemandRef(kind=DemandKind.WORK_ORDER, ref=TypedId.new("work_order")),
        qty=Decimal(4),
        purpose=StockPurpose.SERVICE_SLI,
        priority=1,
        occurred_at=OCCURRED_AT,
    )

    released_position, released_reservation = service.release_reservation(
        context, reservation.reservation_id, reason="Work Order cancelada.", occurred_at=OCCURRED_AT
    )
    assert released_reservation.state is ReservationState.RELEASED
    assert released_position.available == Decimal(10)
    event_log.only(INVENTORY_STOCK_RESERVATION_RELEASED)


def test_transfer_request_dispatch_and_receive(
    recorder: AssetEventRecorder, context: AssetOperationContext, event_log: FakeEventLog
) -> None:
    service = _service(recorder)
    transfer = service.request_transfer(
        context,
        part_ref=TypedId.new("part"),
        from_location_ref=TypedId.new("stock_location"),
        to_location_ref=TypedId.new("stock_location"),
        qty=Decimal(10),
        occurred_at=OCCURRED_AT,
    )
    event_log.only(INVENTORY_TRANSFER_REQUESTED)

    dispatched = service.dispatch_transfer(context, transfer.transfer_id, occurred_at=OCCURRED_AT)
    assert dispatched.state is TransferState.IN_TRANSIT
    event_log.only(INVENTORY_TRANSFER_DISPATCHED)

    received = service.receive_transfer(
        context, transfer.transfer_id, qty_this_receipt=Decimal(10), occurred_at=OCCURRED_AT
    )
    assert received.state is TransferState.RECEIVED
    assert service.get_transfer(transfer.transfer_id) == received
    event_log.only(INVENTORY_TRANSFER_RECEIVED)
