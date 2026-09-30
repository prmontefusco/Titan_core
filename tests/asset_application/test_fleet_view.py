"""Testes do `FleetViewService` — Titan Asset A6."""

from dataclasses import replace
from datetime import UTC, datetime

from packages.asset_application.fleet_view import (
    FleetOperationalState,
    FleetViewRepositoryPort,
    FleetViewService,
    FleetViewSnapshot,
)
from packages.asset_domain.vehicle import (
    AssetOwnership,
    Vehicle,
    VehicleIdentifiers,
    VehicleLifecycleState,
)
from packages.asset_domain.work_order import (
    ContractContext,
    FailureRecord,
    PriorityScore,
    WorkOrder,
    WorkOrderState,
)
from packages.shared_kernel import OrganizationId, TypedId

OCCURRED_AT = datetime(2026, 9, 11, tzinfo=UTC)


class InMemoryFleetViewRepository(FleetViewRepositoryPort):
    def __init__(self, snapshots: tuple[FleetViewSnapshot, ...]) -> None:
        self.snapshots = snapshots
        self.calls: list[TypedId | None] = []

    def list_fleet(self, *, site_ref: TypedId | None = None) -> tuple[FleetViewSnapshot, ...]:
        self.calls.append(site_ref)
        return tuple(
            snapshot
            for snapshot in self.snapshots
            if site_ref is None or snapshot.vehicle.site_ref == site_ref
        )


def _vehicle(
    *,
    site_ref: TypedId | None,
    state: VehicleLifecycleState = VehicleLifecycleState.AVAILABLE,
) -> Vehicle:
    return Vehicle(
        vehicle_id=TypedId.new("vehicle"),
        organization_id=OrganizationId.new(),
        model_ref=TypedId.new("vehicle_model"),
        identifiers=VehicleIdentifiers(serial_number="VH-001"),
        ownership=AssetOwnership.COMPANY,
        site_ref=site_ref,
        lifecycle_state=state,
    )


def _work_order(vehicle: Vehicle, *, state: WorkOrderState, score: int = 10) -> WorkOrder:
    return WorkOrder(
        work_order_id=TypedId.new("work_order"),
        organization_id=vehicle.organization_id,
        vehicle_ref=vehicle.vehicle_id,
        site_ref=vehicle.site_ref or TypedId.new("customer_site"),
        contract_context=ContractContext(
            contract_ref=TypedId.new("sli_contract"),
            contract_version_no=1,
            resolved_at=OCCURRED_AT,
        ),
        failure=FailureRecord(mode="Falha", reported_at=OCCURRED_AT),
        state=state,
        priority=PriorityScore(score=score, breakdown={"sla": score}),
    )


def test_fleet_view_counts_lifecycle_states() -> None:
    site_ref = TypedId.new("customer_site")
    available = _vehicle(site_ref=site_ref, state=VehicleLifecycleState.AVAILABLE)
    degraded = _vehicle(site_ref=site_ref, state=VehicleLifecycleState.DEGRADED)
    unavailable = _vehicle(site_ref=site_ref, state=VehicleLifecycleState.UNAVAILABLE)
    service = FleetViewService(
        InMemoryFleetViewRepository(
            (
                FleetViewSnapshot(vehicle=available),
                FleetViewSnapshot(vehicle=degraded),
                FleetViewSnapshot(vehicle=unavailable),
            )
        )
    )

    view = service.get_fleet_view(site_ref=site_ref)

    assert view.counts_by_state[FleetOperationalState.AVAILABLE] == 1
    assert view.counts_by_state[FleetOperationalState.DEGRADED] == 1
    assert view.counts_by_state[FleetOperationalState.UNAVAILABLE] == 1


def test_fleet_view_derives_waiting_material_from_work_order() -> None:
    site_ref = TypedId.new("customer_site")
    vehicle = _vehicle(site_ref=site_ref, state=VehicleLifecycleState.AVAILABLE)
    waiting = _work_order(vehicle, state=WorkOrderState.WAITING_MATERIAL)
    service = FleetViewService(
        InMemoryFleetViewRepository(
            (FleetViewSnapshot(vehicle=vehicle, open_work_orders=(waiting,)),)
        )
    )

    line = service.get_fleet_view(site_ref=site_ref).lines[0]

    assert line.operational_state is FleetOperationalState.WAITING_MATERIAL
    assert line.open_work_order_refs == (waiting.work_order_id,)
    assert "WORK_ORDER:WAITING_MATERIAL" in line.signals


def test_fleet_view_filters_by_site_and_flags_sla_risk() -> None:
    site_ref = TypedId.new("customer_site")
    other_site_ref = TypedId.new("customer_site")
    vehicle = _vehicle(site_ref=site_ref)
    other = _vehicle(site_ref=other_site_ref)
    risky = _work_order(vehicle, state=WorkOrderState.PLANNED, score=90)
    terminal = replace(
        risky, work_order_id=TypedId.new("work_order"), state=WorkOrderState.CANCELLED
    )
    repository = InMemoryFleetViewRepository(
        (
            FleetViewSnapshot(vehicle=vehicle, open_work_orders=(risky, terminal)),
            FleetViewSnapshot(vehicle=other),
        )
    )
    service = FleetViewService(repository)

    view = service.get_fleet_view(site_ref=site_ref)

    assert repository.calls == [site_ref]
    assert len(view.lines) == 1
    assert view.lines[0].operational_state is FleetOperationalState.SLA_RISK
    assert view.lines[0].open_work_order_refs == (risky.work_order_id,)
    assert view.counts_by_state[FleetOperationalState.SLA_RISK] == 1
