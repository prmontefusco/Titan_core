"""Testes unitários de domínio para `StockPosition`, `StockReservation` e
`StockTransfer` (A2).

Cobre I‑INV‑1 (disponível calculado, ≥ 0), I‑INV‑2 (propósito incompatível
exige decision_ref), I‑INV‑3 (buckets não‑negativos, ajuste nomeado) e I‑INV‑4
(transferência conserva quantidade). `docs/asset/07_INVARIANTS.md`.
"""

from decimal import Decimal
from uuid import uuid4

import pytest

from packages.asset_domain.inventory import (
    AvailabilityBreakdown,
    DemandKind,
    DemandRef,
    DisponibilidadeInsuficiente,
    PropositoIncompativel,
    RecebimentoExcedeDespacho,
    ReservationState,
    StockLocation,
    StockLocationKind,
    StockOwnership,
    StockPosition,
    StockPurpose,
    StockQuantities,
    StockReservation,
    StockReservationLine,
    StockTransfer,
    TransferState,
    TransicaoDeReservaInvalida,
    TransicaoDeTransferenciaInvalida,
)
from packages.shared_kernel import OrganizationId, TypedId


def _location(**overrides: object) -> StockLocation:
    defaults: dict[str, object] = dict(
        location_id=TypedId.new("stock_location"),
        organization_id=OrganizationId(uuid4()),
        kind=StockLocationKind.WORKSHOP,
        code="WS-01",
        display_name="Oficina Central",
    )
    defaults.update(overrides)
    return StockLocation(**defaults)  # type: ignore[arg-type]


def _position(**overrides: object) -> StockPosition:
    defaults: dict[str, object] = dict(
        stock_position_id=TypedId.new("stock_position"),
        organization_id=OrganizationId(uuid4()),
        part_ref=TypedId.new("part"),
        location_ref=TypedId.new("stock_location"),
        purpose=StockPurpose.SERVICE_SLI,
        ownership=StockOwnership.COMPANY_OWNED,
        quantities=StockQuantities(on_hand=Decimal(10)),
    )
    defaults.update(overrides)
    return StockPosition(**defaults)  # type: ignore[arg-type]


def _line(
    qty: str = "3", *, purpose_lock: StockPurpose = StockPurpose.SERVICE_SLI
) -> StockReservationLine:
    return StockReservationLine(
        reservation_id=TypedId.new("stock_reservation"),
        demand_ref=TypedId.new("work_order"),
        qty=Decimal(qty),
        priority=50,
        purpose_lock=purpose_lock,
    )


def test_location_code_cannot_be_blank() -> None:
    with pytest.raises(ValueError, match="code não pode ser vazio"):
        _location(code="  ")


# --- I-INV-0 (peça sem estoque implícito) -----------------------------------------


def test_part_has_no_quantity_field() -> None:
    """I-INV-0 é estrutural: Part (part.py) não tem nenhum campo de
    quantidade. Este teste documenta a garantia por ausência de atributo."""
    from packages.asset_domain.part import Part

    assert not hasattr(Part, "quantities")
    assert not hasattr(Part, "on_hand")


# --- I-INV-1 -----------------------------------------------------------------------


def test_available_is_calculated_never_stored() -> None:
    position = _position(quantities=StockQuantities(on_hand=Decimal(10)))
    assert position.available == Decimal(10)

    held = position.hold(_line("3"))
    assert held.available == Decimal(7)
    assert position.available == Decimal(10)  # o original não muda


def test_availability_breakdown_exposes_each_bucket() -> None:
    position = _position(
        quantities=StockQuantities(
            on_hand=Decimal(10), quarantine=Decimal(1), inspection=Decimal(1), damaged=Decimal(0)
        )
    ).hold(_line("2"))
    breakdown = position.availability_breakdown()
    assert isinstance(breakdown, AvailabilityBreakdown)
    assert breakdown.reserved == Decimal(2)
    assert breakdown.available == Decimal(10) - Decimal(2) - Decimal(1) - Decimal(1)


def test_hold_rejects_qty_exceeding_available() -> None:
    position = _position(quantities=StockQuantities(on_hand=Decimal(2)))
    with pytest.raises(DisponibilidadeInsuficiente):
        position.hold(_line("5"))


def test_construction_rejects_reservations_exceeding_headroom() -> None:
    with pytest.raises(DisponibilidadeInsuficiente):
        _position(
            quantities=StockQuantities(on_hand=Decimal(2)),
            reservations=(_line("5"),),
        )


def test_release_frees_up_availability() -> None:
    line = _line("3")
    position = _position(quantities=StockQuantities(on_hand=Decimal(10))).hold(line)
    assert position.available == Decimal(7)
    released = position.release(line.reservation_id)
    assert released.available == Decimal(10)


def test_release_unknown_reservation_raises() -> None:
    position = _position()
    with pytest.raises(KeyError):
        position.release(TypedId.new("stock_reservation"))


# --- I-INV-2 -------------------------------------------------------------------------


def test_hold_rejects_purpose_mismatch_without_decision() -> None:
    position = _position(purpose=StockPurpose.SERVICE_SLI)
    cross_purpose_line = _line("2", purpose_lock=StockPurpose.PRODUCTION)
    with pytest.raises(PropositoIncompativel):
        position.hold(cross_purpose_line)


def test_hold_allows_purpose_mismatch_with_decision_ref() -> None:
    position = _position(purpose=StockPurpose.SERVICE_SLI)
    cross_purpose_line = _line("2", purpose_lock=StockPurpose.PRODUCTION)
    held = position.hold(cross_purpose_line, cross_purpose_decision_ref=TypedId.new("decision"))
    assert held.available == Decimal(8)


# --- I-INV-3 -------------------------------------------------------------------------


def test_stock_quantities_rejects_negative_buckets() -> None:
    with pytest.raises(ValueError, match="não pode ser negativo"):
        StockQuantities(on_hand=Decimal(-1))


def test_adjust_quantities_targets_named_bucket() -> None:
    position = _position(quantities=StockQuantities(on_hand=Decimal(10)))
    adjusted = position.adjust_quantities(on_hand=Decimal(5))
    assert adjusted.quantities.on_hand == Decimal(15)
    assert position.quantities.on_hand == Decimal(10)


def test_adjust_quantities_rejects_result_below_zero() -> None:
    position = _position(quantities=StockQuantities(on_hand=Decimal(2)))
    with pytest.raises(ValueError, match="não pode ser negativo"):
        position.adjust_quantities(on_hand=Decimal(-5))


def test_adjust_quantities_rejects_unknown_bucket() -> None:
    position = _position()
    with pytest.raises(ValueError, match="desconhecido"):
        position.adjust_quantities(nao_existe=Decimal(1))


def test_consume_reduces_on_hand_and_reservation() -> None:
    line = _line("5")
    position = _position(quantities=StockQuantities(on_hand=Decimal(10))).hold(line)
    consumed = position.consume(line.reservation_id, Decimal(5))
    assert consumed.quantities.on_hand == Decimal(5)
    assert consumed.reservations == ()


def test_partial_consume_leaves_remaining_reservation() -> None:
    line = _line("5")
    position = _position(quantities=StockQuantities(on_hand=Decimal(10))).hold(line)
    consumed = position.consume(line.reservation_id, Decimal(2))
    remaining_line = consumed.reservations[0]
    assert remaining_line.qty == Decimal(3)
    assert consumed.quantities.on_hand == Decimal(8)


def test_consume_rejects_qty_above_reserved() -> None:
    line = _line("2")
    position = _position(quantities=StockQuantities(on_hand=Decimal(10))).hold(line)
    with pytest.raises(ValueError, match="excede a quantidade reservada"):
        position.consume(line.reservation_id, Decimal(3))


# --- StockReservation (agregado próprio) --------------------------------------------


def _reservation(**overrides: object) -> StockReservation:
    defaults: dict[str, object] = dict(
        reservation_id=TypedId.new("stock_reservation"),
        organization_id=OrganizationId(uuid4()),
        stock_position_ref=TypedId.new("stock_position"),
        demand=DemandRef(kind=DemandKind.WORK_ORDER, ref=TypedId.new("work_order")),
        qty=Decimal(3),
        purpose=StockPurpose.SERVICE_SLI,
        priority=50,
    )
    defaults.update(overrides)
    return StockReservation(**defaults)  # type: ignore[arg-type]


def test_reservation_lifecycle_held_to_consumed() -> None:
    reservation = _reservation()
    assert reservation.state is ReservationState.HELD
    allocated = reservation.allocate()
    assert allocated.state is ReservationState.ALLOCATED
    consumed = allocated.consume()
    assert consumed.state is ReservationState.CONSUMED


def test_reservation_cannot_be_consumed_directly_from_held() -> None:
    reservation = _reservation()
    with pytest.raises(TransicaoDeReservaInvalida):
        reservation.consume()


def test_reservation_release_from_held_or_allocated() -> None:
    assert _reservation().release().state is ReservationState.RELEASED
    assert _reservation().allocate().release().state is ReservationState.RELEASED


def test_reservation_cannot_be_released_twice() -> None:
    released = _reservation().release()
    with pytest.raises(TransicaoDeReservaInvalida):
        released.release()


def test_reservation_to_line_projects_correctly() -> None:
    reservation = _reservation()
    line = reservation.to_line()
    assert line.reservation_id == reservation.reservation_id
    assert line.qty == reservation.qty
    assert line.purpose_lock == reservation.purpose


# --- I-INV-4 (StockTransfer) ---------------------------------------------------------


def _transfer(**overrides: object) -> StockTransfer:
    defaults: dict[str, object] = dict(
        transfer_id=TypedId.new("stock_transfer"),
        organization_id=OrganizationId(uuid4()),
        part_ref=TypedId.new("part"),
        from_location_ref=TypedId.new("stock_location"),
        to_location_ref=TypedId.new("stock_location"),
        qty=Decimal(5),
    )
    defaults.update(overrides)
    return StockTransfer(**defaults)  # type: ignore[arg-type]


def test_transfer_rejects_same_origin_and_destination() -> None:
    location = TypedId.new("stock_location")
    with pytest.raises(ValueError, match="não podem ser a mesma localização"):
        _transfer(from_location_ref=location, to_location_ref=location)


def test_transfer_full_cycle() -> None:
    transfer = _transfer(qty=Decimal(5))
    dispatched = transfer.dispatch()
    assert dispatched.state is TransferState.IN_TRANSIT

    partial = dispatched.receive(Decimal(3))
    assert partial.state is TransferState.PARTIALLY_RECEIVED
    assert partial.qty_received == Decimal(3)

    full = partial.receive(Decimal(2))
    assert full.state is TransferState.RECEIVED
    assert full.qty_received == Decimal(5)


def test_transfer_receive_cannot_exceed_dispatched_qty() -> None:
    transfer = _transfer(qty=Decimal(5)).dispatch()
    with pytest.raises(RecebimentoExcedeDespacho):
        transfer.receive(Decimal(6))


def test_transfer_receive_requires_in_transit_or_partially_received() -> None:
    transfer = _transfer()
    with pytest.raises(TransicaoDeTransferenciaInvalida):
        transfer.receive(Decimal(1))


def test_transfer_dispatch_requires_requested_state() -> None:
    transfer = _transfer().dispatch()
    with pytest.raises(TransicaoDeTransferenciaInvalida):
        transfer.dispatch()


def test_transfer_construction_rejects_received_above_dispatched() -> None:
    with pytest.raises(RecebimentoExcedeDespacho):
        _transfer(qty=Decimal(5), qty_received=Decimal(6))


def test_no_unit_exists_in_two_places_at_once_across_the_cycle() -> None:
    """I-INV-4: enquanto IN_TRANSIT, a soma (origem.on_hand + destino.on_hand)
    não conta a unidade — este teste prova a aritmética do agregado de
    transferência isoladamente; a coordenação real com StockPosition.on_hand
    é responsabilidade da aplicação (A4), que decrementa a origem no dispatch
    e incrementa o destino no receive."""
    transfer = _transfer(qty=Decimal(5)).dispatch().receive(Decimal(5))
    assert transfer.qty_received == transfer.qty
    assert transfer.state is TransferState.RECEIVED
