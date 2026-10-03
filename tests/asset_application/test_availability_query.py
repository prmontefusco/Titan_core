"""Testes da query `GetAvailability` — Titan Asset A5."""

from decimal import Decimal

from packages.asset_application.availability_query import (
    AvailabilityQueryService,
    AvailabilityStockPositionRepositoryPort,
)
from packages.asset_domain.inventory import (
    StockOwnership,
    StockPosition,
    StockPurpose,
    StockQuantities,
    StockReservationLine,
)
from packages.shared_kernel import OrganizationId, TypedId


class InMemoryStockPositionRepository(AvailabilityStockPositionRepositoryPort):
    def __init__(self, items: tuple[StockPosition, ...]) -> None:
        self.items = items

    def list_by_part_location_purpose(
        self,
        *,
        part_ref: TypedId,
        location_ref: TypedId,
        purpose: StockPurpose,
    ) -> tuple[StockPosition, ...]:
        return tuple(
            item
            for item in self.items
            if item.part_ref == part_ref
            and item.location_ref == location_ref
            and item.purpose is purpose
        )


def _position(
    *,
    part_ref: TypedId,
    location_ref: TypedId,
    on_hand: Decimal,
    reservation_qty: Decimal = Decimal(0),
) -> StockPosition:
    reservations: tuple[StockReservationLine, ...] = ()
    if reservation_qty > 0:
        reservations = (
            StockReservationLine(
                reservation_id=TypedId.new("stock_reservation"),
                demand_ref=TypedId.new("work_order"),
                qty=reservation_qty,
                priority=1,
                purpose_lock=StockPurpose.SERVICE_SLI,
            ),
        )
    return StockPosition(
        stock_position_id=TypedId.new("stock_position"),
        organization_id=OrganizationId.new(),
        part_ref=part_ref,
        location_ref=location_ref,
        purpose=StockPurpose.SERVICE_SLI,
        ownership=StockOwnership.COMPANY_OWNED,
        quantities=StockQuantities(
            on_hand=on_hand,
            quarantine=Decimal("1"),
            inspection=Decimal("2"),
            damaged=Decimal("3"),
        ),
        reservations=reservations,
    )


def test_availability_query_aggregates_matching_stock_positions() -> None:
    part_ref = TypedId.new("part")
    location_ref = TypedId.new("stock_location")
    service = AvailabilityQueryService(
        repository=InMemoryStockPositionRepository(
            (
                _position(
                    part_ref=part_ref,
                    location_ref=location_ref,
                    on_hand=Decimal("20"),
                    reservation_qty=Decimal("4"),
                ),
                _position(
                    part_ref=part_ref,
                    location_ref=location_ref,
                    on_hand=Decimal("10"),
                    reservation_qty=Decimal("1"),
                ),
                _position(
                    part_ref=TypedId.new("part"),
                    location_ref=location_ref,
                    on_hand=Decimal("99"),
                ),
            )
        )
    )

    result = service.get_availability(
        part_ref=part_ref,
        location_ref=location_ref,
        purpose=StockPurpose.SERVICE_SLI,
    )

    assert result.part_ref == part_ref
    assert result.location_ref == location_ref
    assert result.purpose is StockPurpose.SERVICE_SLI
    assert result.breakdown.on_hand == Decimal("30")
    assert result.breakdown.reserved == Decimal("5")
    assert result.breakdown.quarantine == Decimal("2")
    assert result.breakdown.inspection == Decimal("4")
    assert result.breakdown.damaged == Decimal("6")
    assert result.breakdown.available == Decimal("13")
    assert len(result.stock_position_refs) == 2


def test_availability_query_returns_zero_breakdown_when_no_position_matches() -> None:
    service = AvailabilityQueryService(repository=InMemoryStockPositionRepository(()))

    result = service.get_availability(
        part_ref=TypedId.new("part"),
        location_ref=TypedId.new("stock_location"),
        purpose=StockPurpose.SERVICE_SLI,
    )

    assert result.breakdown.available == Decimal(0)
    assert result.stock_position_refs == ()
