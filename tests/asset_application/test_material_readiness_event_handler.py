"""Testes do handler de eventos para `MaterialReadinessRecalculator` — Titan Asset A6."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import cast

from packages.asset_application.material_readiness_event_handler import (
    MaterialReadinessEventHandler,
    MaterialReadinessEventHandlingOutcome,
)
from packages.asset_application.material_readiness_recalculator import (
    MaterialReadinessRecalculation,
    MaterialReadinessRecalculationOutcome,
    MaterialReadinessRecalculator,
)
from packages.asset_domain.events import (
    INVENTORY_STOCK_RESERVED,
    INVENTORY_TRANSFER_RECEIVED,
    VEHICLE_REGISTERED,
    inventory_stock_reserved_payload,
    inventory_transfer_received_payload,
    vehicle_registered_payload,
)
from packages.core_domain.events import CanonicalPayload, DomainEvent
from packages.shared_kernel import OrganizationId, RecordTimestamps, TypedId, UniversalReference

OCCURRED_AT = datetime(2026, 9, 11, tzinfo=UTC)


class FakeRecalculator:
    def __init__(self) -> None:
        self.reservation_calls: list[TypedId] = []
        self.transfer_calls: list[TypedId] = []

    def recalculate_for_reservation(
        self,
        context: object,
        reservation_id: TypedId,
        *,
        occurred_at: datetime,
    ) -> MaterialReadinessRecalculation:
        self.reservation_calls.append(reservation_id)
        return MaterialReadinessRecalculation(
            work_order_id=TypedId.new("work_order"),
            outcome=MaterialReadinessRecalculationOutcome.UNCHANGED,
            material_fully_reserved=True,
        )

    def recalculate_for_transfer(
        self,
        context: object,
        transfer_id: TypedId,
        *,
        occurred_at: datetime,
    ) -> MaterialReadinessRecalculation:
        self.transfer_calls.append(transfer_id)
        return MaterialReadinessRecalculation(
            work_order_id=TypedId.new("work_order"),
            outcome=MaterialReadinessRecalculationOutcome.UNCHANGED,
            material_fully_reserved=True,
        )


def _event(event_type: str, payload: CanonicalPayload, aggregate_id: TypedId) -> DomainEvent:
    organization_id = OrganizationId.new()
    reference = UniversalReference(
        target_id=aggregate_id,
        organization_id=organization_id,
        contract_version=1,
    )
    return DomainEvent(
        event_id=TypedId.new("domain_event"),
        organization_id=organization_id,
        aggregate_reference=reference,
        aggregate_version=1,
        event_type=event_type,
        event_version=1,
        timestamps=RecordTimestamps(occurred_at=OCCURRED_AT, recorded_at=OCCURRED_AT),
        actor_reference=reference,
        source_reference=reference,
        correlation_id=TypedId.new("correlation"),
        causation_id=None,
        payload=payload,
    )


def test_handler_routes_reservation_inventory_events_to_recalculator() -> None:
    reservation_id = TypedId.new("stock_reservation")
    recalculator = FakeRecalculator()
    handler = MaterialReadinessEventHandler(cast(MaterialReadinessRecalculator, recalculator))
    event = _event(
        INVENTORY_STOCK_RESERVED,
        inventory_stock_reserved_payload(
            reservation_id=reservation_id,
            stock_position_ref=TypedId.new("stock_position"),
            demand_kind="WORK_ORDER",
            demand_ref=TypedId.new("work_order"),
            qty=Decimal(2),
            purpose="SERVICE_SLI",
            priority=10,
            decision_ref=None,
        ),
        reservation_id,
    )

    result = handler.handle(event)

    assert result.outcome is MaterialReadinessEventHandlingOutcome.HANDLED
    assert recalculator.reservation_calls == [reservation_id]
    assert result.recalculation is not None
    assert result.recalculation.outcome is MaterialReadinessRecalculationOutcome.UNCHANGED


def test_handler_routes_transfer_received_to_recalculator() -> None:
    transfer_id = TypedId.new("stock_transfer")
    recalculator = FakeRecalculator()
    handler = MaterialReadinessEventHandler(cast(MaterialReadinessRecalculator, recalculator))
    event = _event(
        INVENTORY_TRANSFER_RECEIVED,
        inventory_transfer_received_payload(
            transfer_id=transfer_id,
            qty_received=Decimal(2),
            to_location_ref=TypedId.new("stock_location"),
            partial=False,
        ),
        transfer_id,
    )

    result = handler.handle(event)

    assert result.outcome is MaterialReadinessEventHandlingOutcome.HANDLED
    assert recalculator.transfer_calls == [transfer_id]


def test_handler_ignores_unrelated_asset_events() -> None:
    recalculator = FakeRecalculator()
    handler = MaterialReadinessEventHandler(cast(MaterialReadinessRecalculator, recalculator))
    vehicle_id = TypedId.new("vehicle")
    event = _event(
        VEHICLE_REGISTERED,
        vehicle_registered_payload(
            vehicle_id=vehicle_id,
            model_ref=TypedId.new("vehicle_model"),
            variant_ref=None,
            serial_number="SN-1",
            chassis=None,
            fleet_number=None,
            site_ref=None,
            ownership="COMPANY",
        ),
        vehicle_id,
    )

    result = handler.handle(event)

    assert result.outcome is MaterialReadinessEventHandlingOutcome.IGNORED
    assert recalculator.reservation_calls == []
    assert recalculator.transfer_calls == []
