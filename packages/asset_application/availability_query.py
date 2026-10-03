"""Query `GetAvailability` — Titan Asset A5."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from packages.asset_domain.inventory import AvailabilityBreakdown, StockPosition, StockPurpose
from packages.shared_kernel import TypedId


class AvailabilityStockPositionRepositoryPort(Protocol):
    def list_by_part_location_purpose(
        self,
        *,
        part_ref: TypedId,
        location_ref: TypedId,
        purpose: StockPurpose,
    ) -> tuple[StockPosition, ...]: ...


@dataclass(frozen=True, slots=True)
class AvailabilityResult:
    part_ref: TypedId
    location_ref: TypedId
    purpose: StockPurpose
    breakdown: AvailabilityBreakdown
    stock_position_refs: tuple[TypedId, ...]


def _sum_breakdowns(positions: tuple[StockPosition, ...]) -> AvailabilityBreakdown:
    on_hand = Decimal(0)
    reserved = Decimal(0)
    quarantine = Decimal(0)
    inspection = Decimal(0)
    damaged = Decimal(0)
    for position in positions:
        breakdown = position.availability_breakdown()
        on_hand += breakdown.on_hand
        reserved += breakdown.reserved
        quarantine += breakdown.quarantine
        inspection += breakdown.inspection
        damaged += breakdown.damaged
    return AvailabilityBreakdown(
        on_hand=on_hand,
        reserved=reserved,
        quarantine=quarantine,
        inspection=inspection,
        damaged=damaged,
    )


@dataclass(frozen=True, slots=True)
class AvailabilityQueryService:
    repository: AvailabilityStockPositionRepositoryPort

    def get_availability(
        self,
        *,
        part_ref: TypedId,
        location_ref: TypedId,
        purpose: StockPurpose,
    ) -> AvailabilityResult:
        positions = self.repository.list_by_part_location_purpose(
            part_ref=part_ref,
            location_ref=location_ref,
            purpose=purpose,
        )
        return AvailabilityResult(
            part_ref=part_ref,
            location_ref=location_ref,
            purpose=purpose,
            breakdown=_sum_breakdowns(positions),
            stock_position_refs=tuple(position.stock_position_id for position in positions),
        )
