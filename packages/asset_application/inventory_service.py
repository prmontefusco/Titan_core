"""Casos de uso de `StockPosition`, `StockReservation` e `StockTransfer` —
Titan Asset (A4).

Um serviço só, mesmo padrão de agrupamento de
`asset_infrastructure/persistence/inventory_repository.py` (A3): os três
agregados compartilham a operação de negócio "montar e reservar"
(`ASSET_VERTICAL_BOOTSTRAP_PLAN.md` §2.1). `reserve_stock`/`release_reservation`/
`consume_stock` são **operações coordenadas** — tocam `StockPosition` e
`StockReservation` na mesma chamada, porque `09_COMMAND_MODEL.md` define a
fronteira transacional de `ReserveStock`/`ReleaseStockReservation`/
`ConsumeStock` como os dois agregados juntos (cenário B1: mesma transação).

`InventoryService.reserve_stock` **não** chama `core_application` para
resolver disputa de propósito (I-INV-2) — recebe `cross_purpose_decision_ref`
já resolvido pelo chamador, como o próprio `StockPosition.hold()` já espera.
A emissão de `inventory.allocation_decided` (quando há disputa de verdade,
resolvida por uma `Decision` do Core) fica para quando um caso de uso
concreto a exercitar — este incremento cobre o caminho sem disputa.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol

from packages.asset_application.event_recorder import AssetEventRecorder, AssetOperationContext
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
    inventory_stock_adjusted_payload,
    inventory_stock_consumed_payload,
    inventory_stock_position_opened_payload,
    inventory_stock_reservation_allocated_payload,
    inventory_stock_reservation_released_payload,
    inventory_stock_reserved_payload,
    inventory_transfer_dispatched_payload,
    inventory_transfer_received_payload,
    inventory_transfer_requested_payload,
)
from packages.asset_domain.inventory import (
    DemandRef,
    StockOwnership,
    StockPosition,
    StockPurpose,
    StockQuantities,
    StockReservation,
    StockTransfer,
    TransferState,
)
from packages.shared_kernel import TypedId


class StockPositionNaoEncontrada(KeyError):
    """`stock_position_id` não corresponde a nenhuma `StockPosition` desta Organization."""


class StockReservationNaoEncontrada(KeyError):
    """`reservation_id` não corresponde a nenhuma `StockReservation` desta Organization."""


class StockTransferNaoEncontrado(KeyError):
    """`transfer_id` não corresponde a nenhum `StockTransfer` desta Organization."""


class StockPositionRepositoryPort(Protocol):
    def save(self, position: StockPosition) -> None: ...

    def update(self, position: StockPosition) -> None: ...

    def get_by_id(self, stock_position_id: TypedId) -> StockPosition | None: ...


class StockReservationRepositoryPort(Protocol):
    def save(self, reservation: StockReservation) -> None: ...

    def update(self, reservation: StockReservation) -> None: ...

    def get_by_id(self, reservation_id: TypedId) -> StockReservation | None: ...


class StockTransferRepositoryPort(Protocol):
    def save(self, transfer: StockTransfer) -> None: ...

    def update(self, transfer: StockTransfer) -> None: ...

    def get_by_id(self, transfer_id: TypedId) -> StockTransfer | None: ...


@dataclass(frozen=True, slots=True)
class InventoryService:
    stock_position_repository: StockPositionRepositoryPort
    stock_reservation_repository: StockReservationRepositoryPort
    stock_transfer_repository: StockTransferRepositoryPort
    recorder: AssetEventRecorder

    def _require_position(self, stock_position_id: TypedId) -> StockPosition:
        position = self.stock_position_repository.get_by_id(stock_position_id)
        if position is None:
            raise StockPositionNaoEncontrada(
                f"StockPosition '{stock_position_id.value}' não encontrada."
            )
        return position

    def _require_reservation(self, reservation_id: TypedId) -> StockReservation:
        reservation = self.stock_reservation_repository.get_by_id(reservation_id)
        if reservation is None:
            raise StockReservationNaoEncontrada(
                f"StockReservation '{reservation_id.value}' não encontrada."
            )
        return reservation

    def _require_transfer(self, transfer_id: TypedId) -> StockTransfer:
        transfer = self.stock_transfer_repository.get_by_id(transfer_id)
        if transfer is None:
            raise StockTransferNaoEncontrado(f"StockTransfer '{transfer_id.value}' não encontrado.")
        return transfer

    # -- StockPosition ---------------------------------------------------

    def open_stock_position(
        self,
        context: AssetOperationContext,
        *,
        part_ref: TypedId,
        location_ref: TypedId,
        purpose: StockPurpose,
        ownership: StockOwnership,
        quantities: StockQuantities | None = None,
        lot: str | None = None,
        serial: str | None = None,
        occurred_at: datetime,
    ) -> StockPosition:
        position = StockPosition(
            stock_position_id=TypedId.new("stock_position"),
            organization_id=context.organization_id,
            part_ref=part_ref,
            location_ref=location_ref,
            purpose=purpose,
            ownership=ownership,
            quantities=quantities if quantities is not None else StockQuantities(),
            lot=lot,
            serial=serial,
        )
        self.stock_position_repository.save(position)
        self.recorder.record(
            context=context,
            aggregate_id=position.stock_position_id,
            event_type=INVENTORY_STOCK_POSITION_OPENED,
            payload=inventory_stock_position_opened_payload(
                stock_position_id=position.stock_position_id,
                part_ref=part_ref,
                location_ref=location_ref,
                purpose=purpose.value,
                ownership=ownership.value,
            ),
            occurred_at=occurred_at,
        )
        return position

    def adjust_stock(
        self,
        context: AssetOperationContext,
        stock_position_id: TypedId,
        *,
        deltas: dict[str, Decimal],
        reason: str,
        actor_ref: TypedId,
        occurred_at: datetime,
    ) -> StockPosition:
        if not reason or not reason.strip():
            raise ValueError("reason é obrigatório para ajustar estoque (I-INV-3).")
        position = self._require_position(stock_position_id)
        updated = position.adjust_quantities(**deltas)
        self.stock_position_repository.update(updated)
        self.recorder.record(
            context=context,
            aggregate_id=updated.stock_position_id,
            event_type=INVENTORY_STOCK_ADJUSTED,
            payload=inventory_stock_adjusted_payload(
                stock_position_id=updated.stock_position_id,
                delta_by_status=deltas,
                reason=reason,
                actor_ref=actor_ref,
            ),
            occurred_at=occurred_at,
        )
        return updated

    # -- StockReservation (coordenado com StockPosition) ------------------

    def reserve_stock(
        self,
        context: AssetOperationContext,
        stock_position_id: TypedId,
        *,
        demand: DemandRef,
        qty: Decimal,
        purpose: StockPurpose,
        priority: int,
        cross_purpose_decision_ref: TypedId | None = None,
        occurred_at: datetime,
    ) -> tuple[StockPosition, StockReservation]:
        position = self._require_position(stock_position_id)
        reservation = StockReservation(
            reservation_id=TypedId.new("stock_reservation"),
            organization_id=context.organization_id,
            stock_position_ref=stock_position_id,
            demand=demand,
            qty=qty,
            purpose=purpose,
            priority=priority,
            decision_ref=cross_purpose_decision_ref,
        )
        updated_position = position.hold(
            reservation.to_line(), cross_purpose_decision_ref=cross_purpose_decision_ref
        )
        self.stock_reservation_repository.save(reservation)
        self.stock_position_repository.update(updated_position)
        self.recorder.record(
            context=context,
            aggregate_id=reservation.reservation_id,
            event_type=INVENTORY_STOCK_RESERVED,
            payload=inventory_stock_reserved_payload(
                reservation_id=reservation.reservation_id,
                stock_position_ref=stock_position_id,
                demand_kind=demand.kind.value,
                demand_ref=demand.ref,
                qty=qty,
                purpose=purpose.value,
                priority=priority,
                decision_ref=cross_purpose_decision_ref,
            ),
            occurred_at=occurred_at,
        )
        return updated_position, reservation

    def release_reservation(
        self,
        context: AssetOperationContext,
        reservation_id: TypedId,
        *,
        reason: str,
        occurred_at: datetime,
    ) -> tuple[StockPosition, StockReservation]:
        reservation = self._require_reservation(reservation_id)
        position = self._require_position(reservation.stock_position_ref)
        updated_reservation = reservation.release()
        updated_position = position.release(reservation_id)
        self.stock_reservation_repository.update(updated_reservation)
        self.stock_position_repository.update(updated_position)
        self.recorder.record(
            context=context,
            aggregate_id=reservation_id,
            event_type=INVENTORY_STOCK_RESERVATION_RELEASED,
            payload=inventory_stock_reservation_released_payload(
                reservation_id=reservation_id, reason=reason
            ),
            occurred_at=occurred_at,
        )
        return updated_position, updated_reservation

    def allocate_reservation(
        self,
        context: AssetOperationContext,
        reservation_id: TypedId,
        *,
        occurred_at: datetime,
    ) -> StockReservation:
        reservation = self._require_reservation(reservation_id)
        updated = reservation.allocate()
        self.stock_reservation_repository.update(updated)
        self.recorder.record(
            context=context,
            aggregate_id=reservation_id,
            event_type=INVENTORY_STOCK_RESERVATION_ALLOCATED,
            payload=inventory_stock_reservation_allocated_payload(reservation_id=reservation_id),
            occurred_at=occurred_at,
        )
        return updated

    def consume_stock(
        self,
        context: AssetOperationContext,
        reservation_id: TypedId,
        *,
        work_order_ref: TypedId,
        qty: Decimal,
        occurred_at: datetime,
    ) -> tuple[StockPosition, StockReservation]:
        reservation = self._require_reservation(reservation_id)
        position = self._require_position(reservation.stock_position_ref)
        updated_reservation = reservation.consume()
        updated_position = position.consume(reservation_id, qty)
        self.stock_reservation_repository.update(updated_reservation)
        self.stock_position_repository.update(updated_position)
        self.recorder.record(
            context=context,
            aggregate_id=reservation_id,
            event_type=INVENTORY_STOCK_CONSUMED,
            payload=inventory_stock_consumed_payload(
                reservation_id=reservation_id,
                work_order_ref=work_order_ref,
                qty=qty,
                lot=updated_position.lot,
                serial=updated_position.serial,
            ),
            occurred_at=occurred_at,
        )
        return updated_position, updated_reservation

    # -- StockTransfer ------------------------------------------------------

    def request_transfer(
        self,
        context: AssetOperationContext,
        *,
        part_ref: TypedId,
        from_location_ref: TypedId,
        to_location_ref: TypedId,
        qty: Decimal,
        linked_reservation_ref: TypedId | None = None,
        occurred_at: datetime,
    ) -> StockTransfer:
        transfer = StockTransfer(
            transfer_id=TypedId.new("stock_transfer"),
            organization_id=context.organization_id,
            part_ref=part_ref,
            from_location_ref=from_location_ref,
            to_location_ref=to_location_ref,
            qty=qty,
            linked_reservation_ref=linked_reservation_ref,
        )
        self.stock_transfer_repository.save(transfer)
        self.recorder.record(
            context=context,
            aggregate_id=transfer.transfer_id,
            event_type=INVENTORY_TRANSFER_REQUESTED,
            payload=inventory_transfer_requested_payload(
                transfer_id=transfer.transfer_id,
                part_ref=part_ref,
                from_location_ref=from_location_ref,
                to_location_ref=to_location_ref,
                qty=qty,
                linked_reservation_ref=linked_reservation_ref,
            ),
            occurred_at=occurred_at,
        )
        return transfer

    def dispatch_transfer(
        self,
        context: AssetOperationContext,
        transfer_id: TypedId,
        *,
        occurred_at: datetime,
    ) -> StockTransfer:
        transfer = self._require_transfer(transfer_id)
        updated = transfer.dispatch()
        self.stock_transfer_repository.update(updated)
        self.recorder.record(
            context=context,
            aggregate_id=transfer_id,
            event_type=INVENTORY_TRANSFER_DISPATCHED,
            payload=inventory_transfer_dispatched_payload(
                transfer_id=transfer_id,
                qty=updated.qty,
                from_location_ref=updated.from_location_ref,
            ),
            occurred_at=occurred_at,
        )
        return updated

    def receive_transfer(
        self,
        context: AssetOperationContext,
        transfer_id: TypedId,
        *,
        qty_this_receipt: Decimal,
        occurred_at: datetime,
    ) -> StockTransfer:
        transfer = self._require_transfer(transfer_id)
        updated = transfer.receive(qty_this_receipt)
        self.stock_transfer_repository.update(updated)
        self.recorder.record(
            context=context,
            aggregate_id=transfer_id,
            event_type=INVENTORY_TRANSFER_RECEIVED,
            payload=inventory_transfer_received_payload(
                transfer_id=transfer_id,
                qty_received=updated.qty_received,
                to_location_ref=updated.to_location_ref,
                partial=updated.state is TransferState.PARTIALLY_RECEIVED,
            ),
            occurred_at=occurred_at,
        )
        return updated

    # -- Consultas ------------------------------------------------------------

    def get_stock_position(self, stock_position_id: TypedId) -> StockPosition | None:
        return self.stock_position_repository.get_by_id(stock_position_id)

    def get_reservation(self, reservation_id: TypedId) -> StockReservation | None:
        return self.stock_reservation_repository.get_by_id(reservation_id)

    def get_transfer(self, transfer_id: TypedId) -> StockTransfer | None:
        return self.stock_transfer_repository.get_by_id(transfer_id)
