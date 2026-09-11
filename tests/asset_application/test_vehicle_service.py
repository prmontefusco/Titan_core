"""Testes do `VehicleService` — Titan Asset (A4)."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from packages.asset_application.event_recorder import AssetEventRecorder, AssetOperationContext
from packages.asset_application.vehicle_service import (
    VehicleNaoEncontrado,
    VehicleRepositoryPort,
    VehicleService,
)
from packages.asset_domain.events import (
    VEHICLE_CONFIGURATION_BASELINE_SET,
    VEHICLE_LIFECYCLE_STATE_CHANGED,
    VEHICLE_METER_READING_CORRECTED,
    VEHICLE_METER_READING_RECORDED,
    VEHICLE_REGISTERED,
    VEHICLE_RETURNED_TO_SERVICE,
)
from packages.asset_domain.vehicle import (
    AssetOwnership,
    MeterKind,
    Vehicle,
    VehicleIdentifiers,
    VehicleLifecycleState,
)
from packages.shared_kernel import TypedId
from tests.asset_support import FakeEventLog


class InMemoryVehicleRepository(VehicleRepositoryPort):
    def __init__(self) -> None:
        self.vehicles: dict[str, Vehicle] = {}

    def save(self, vehicle: Vehicle) -> None:
        self.vehicles[vehicle.vehicle_id.value.hex] = vehicle

    def update(self, vehicle: Vehicle) -> None:
        self.vehicles[vehicle.vehicle_id.value.hex] = vehicle

    def get_by_id(self, vehicle_id: TypedId) -> Vehicle | None:
        return self.vehicles.get(vehicle_id.value.hex)


def _register(service: VehicleService, context: AssetOperationContext) -> Vehicle:
    return service.register_vehicle(
        context,
        model_ref=TypedId.new("vehicle_model"),
        identifiers=VehicleIdentifiers(serial_number="SN-001", fleet_number="F-01"),
        ownership=AssetOwnership.COMPANY,
    )


def test_register_vehicle_and_get(
    recorder: AssetEventRecorder, context: AssetOperationContext, event_log: FakeEventLog
) -> None:
    service = VehicleService(repository=InMemoryVehicleRepository(), recorder=recorder)

    vehicle = _register(service, context)

    assert vehicle.organization_id == context.organization_id
    assert vehicle.lifecycle_state is VehicleLifecycleState.AVAILABLE
    assert service.get_vehicle(vehicle.vehicle_id) == vehicle
    event = event_log.only(VEHICLE_REGISTERED)
    assert event.aggregate_version == 1
    assert event.aggregate_reference.target_id == vehicle.vehicle_id


def test_get_vehicle_returns_none_when_not_found(
    recorder: AssetEventRecorder,
) -> None:
    service = VehicleService(repository=InMemoryVehicleRepository(), recorder=recorder)
    assert service.get_vehicle(TypedId.new("vehicle")) is None


def test_mutation_on_unknown_vehicle_raises(
    recorder: AssetEventRecorder, context: AssetOperationContext
) -> None:
    service = VehicleService(repository=InMemoryVehicleRepository(), recorder=recorder)
    with pytest.raises(VehicleNaoEncontrado):
        service.transition_lifecycle(
            context,
            TypedId.new("vehicle"),
            new_state=VehicleLifecycleState.DEGRADED,
            occurred_at=datetime(2026, 1, 1, tzinfo=UTC),
        )


def test_set_configuration_baseline(
    recorder: AssetEventRecorder, context: AssetOperationContext, event_log: FakeEventLog
) -> None:
    service = VehicleService(repository=InMemoryVehicleRepository(), recorder=recorder)
    vehicle = _register(service, context)

    baseline_ref = TypedId.new("configuration_baseline")
    valid_from = datetime(2026, 2, 1, tzinfo=UTC)
    updated = service.set_configuration_baseline(
        context, vehicle.vehicle_id, baseline_ref=baseline_ref, valid_from=valid_from
    )

    assert updated.current_baseline_ref == baseline_ref
    assert updated.baseline_valid_from == valid_from
    event = event_log.only(VEHICLE_CONFIGURATION_BASELINE_SET)
    assert event.aggregate_version == 2


def test_record_and_correct_meter_reading(
    recorder: AssetEventRecorder, context: AssetOperationContext, event_log: FakeEventLog
) -> None:
    service = VehicleService(repository=InMemoryVehicleRepository(), recorder=recorder)
    vehicle = _register(service, context)

    observed_at = datetime(2026, 1, 1, tzinfo=UTC)
    with_reading = service.record_meter_reading(
        context,
        vehicle.vehicle_id,
        kind=MeterKind.HOURS,
        value=Decimal("120.5"),
        observed_at=observed_at,
        recorded_at=observed_at,
        source="manual",
    )
    assert len(with_reading.meter_readings) == 1
    reading_id = with_reading.meter_readings[0].reading_id
    event_log.only(VEHICLE_METER_READING_RECORDED)

    corrected_at = datetime(2026, 1, 2, tzinfo=UTC)
    with_correction = service.correct_meter_reading(
        context,
        vehicle.vehicle_id,
        original_reading_id=reading_id,
        corrected_value=Decimal("125.0"),
        reason="Leitura original registrada com erro de digitação.",
        corrected_at=corrected_at,
    )
    assert len(with_correction.meter_readings) == 1
    assert len(with_correction.meter_corrections) == 1
    event_log.only(VEHICLE_METER_READING_CORRECTED)


def test_transition_lifecycle_and_return_to_service(
    recorder: AssetEventRecorder, context: AssetOperationContext, event_log: FakeEventLog
) -> None:
    service = VehicleService(repository=InMemoryVehicleRepository(), recorder=recorder)
    vehicle = _register(service, context)

    planned = service.transition_lifecycle(
        context,
        vehicle.vehicle_id,
        new_state=VehicleLifecycleState.MAINTENANCE_PLANNED,
        occurred_at=datetime(2026, 3, 1, tzinfo=UTC),
    )
    assert planned.lifecycle_state is VehicleLifecycleState.MAINTENANCE_PLANNED

    in_maintenance = service.transition_lifecycle(
        context,
        vehicle.vehicle_id,
        new_state=VehicleLifecycleState.IN_MAINTENANCE,
        occurred_at=datetime(2026, 3, 2, tzinfo=UTC),
    )
    assert in_maintenance.lifecycle_state is VehicleLifecycleState.IN_MAINTENANCE
    assert len(event_log.of_type(VEHICLE_LIFECYCLE_STATE_CHANGED)) == 2

    work_order_ref = TypedId.new("work_order")
    validation_ref = TypedId.new("post_maintenance_validation")
    returned = service.return_to_service(
        context,
        vehicle.vehicle_id,
        work_order_ref=work_order_ref,
        validation_ref=validation_ref,
        occurred_at=datetime(2026, 3, 5, tzinfo=UTC),
    )
    assert returned.lifecycle_state is VehicleLifecycleState.AVAILABLE
    event = event_log.only(VEHICLE_RETURNED_TO_SERVICE)
    assert event.aggregate_version == 4
