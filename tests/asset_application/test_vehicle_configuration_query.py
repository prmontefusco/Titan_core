"""Testes da query `GetVehicleConfigurationAt` — Titan Asset A5."""

from datetime import UTC, datetime

import pytest

from packages.asset_application.vehicle_configuration_query import (
    VehicleConfigurationAtNaoEncontrada,
    VehicleConfigurationAtService,
    VehicleConfigurationBaselineRepositoryPort,
    VehicleConfigurationVehicleRepositoryPort,
)
from packages.asset_domain.configuration import (
    BaselinePosition,
    ConfigurationBaseline,
    ConfigurationRevision,
    Effectivity,
)
from packages.asset_domain.vehicle import AssetOwnership, Vehicle, VehicleIdentifiers
from packages.shared_kernel import OrganizationId, TypedId

OCCURRED_AT = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)


class InMemoryVehicleRepository(VehicleConfigurationVehicleRepositoryPort):
    def __init__(self, items: tuple[Vehicle, ...]) -> None:
        self.items = {item.vehicle_id: item for item in items}

    def get_by_id(self, vehicle_id: TypedId) -> Vehicle | None:
        return self.items.get(vehicle_id)


class InMemoryBaselineRepository(VehicleConfigurationBaselineRepositoryPort):
    def __init__(self, items: tuple[ConfigurationBaseline, ...]) -> None:
        self.items = {item.baseline_id: item for item in items}

    def get_by_id(self, baseline_id: TypedId) -> ConfigurationBaseline | None:
        return self.items.get(baseline_id)


def _baseline(*, baseline_id: TypedId, model_ref: TypedId) -> ConfigurationBaseline:
    return ConfigurationBaseline(
        baseline_id=baseline_id,
        organization_id=OrganizationId.new(),
        model_ref=model_ref,
        revision=ConfigurationRevision(number=1),
        effectivity=Effectivity(valid_from=OCCURRED_AT),
        positions=(
            BaselinePosition(
                position_code="MOTOR",
                part_ref=TypedId.new("part"),
                part_revision_ref=TypedId.new("part_revision"),
            ),
        ),
    )


def _vehicle(*, baseline_id: TypedId, model_ref: TypedId) -> Vehicle:
    return Vehicle(
        vehicle_id=TypedId.new("vehicle"),
        organization_id=OrganizationId.new(),
        model_ref=model_ref,
        identifiers=VehicleIdentifiers(serial_number="SN-001"),
        ownership=AssetOwnership.COMPANY,
        current_baseline_ref=baseline_id,
        baseline_valid_from=OCCURRED_AT,
        created_at=OCCURRED_AT,
    )


def test_vehicle_configuration_at_returns_current_baseline_covering_instant() -> None:
    baseline_id = TypedId.new("configuration_baseline")
    model_ref = TypedId.new("vehicle_model")
    baseline = _baseline(baseline_id=baseline_id, model_ref=model_ref)
    vehicle = _vehicle(baseline_id=baseline_id, model_ref=model_ref)
    service = VehicleConfigurationAtService(
        vehicle_repository=InMemoryVehicleRepository((vehicle,)),
        baseline_repository=InMemoryBaselineRepository((baseline,)),
    )

    result = service.get_configuration_at(vehicle_id=vehicle.vehicle_id, instant=OCCURRED_AT)

    assert result.vehicle == vehicle
    assert result.baseline == baseline
    assert result.instant == OCCURRED_AT


def test_vehicle_configuration_at_rejects_instant_before_current_vehicle_baseline() -> None:
    baseline_id = TypedId.new("configuration_baseline")
    model_ref = TypedId.new("vehicle_model")
    vehicle = _vehicle(baseline_id=baseline_id, model_ref=model_ref)
    service = VehicleConfigurationAtService(
        vehicle_repository=InMemoryVehicleRepository((vehicle,)),
        baseline_repository=InMemoryBaselineRepository(
            (_baseline(baseline_id=baseline_id, model_ref=model_ref),)
        ),
    )

    with pytest.raises(VehicleConfigurationAtNaoEncontrada):
        service.get_configuration_at(
            vehicle_id=vehicle.vehicle_id,
            instant=datetime(2026, 10, 1, 12, 0, tzinfo=UTC),
        )


def test_vehicle_configuration_at_rejects_missing_baseline() -> None:
    baseline_id = TypedId.new("configuration_baseline")
    model_ref = TypedId.new("vehicle_model")
    vehicle = _vehicle(baseline_id=baseline_id, model_ref=model_ref)
    service = VehicleConfigurationAtService(
        vehicle_repository=InMemoryVehicleRepository((vehicle,)),
        baseline_repository=InMemoryBaselineRepository(()),
    )

    with pytest.raises(VehicleConfigurationAtNaoEncontrada):
        service.get_configuration_at(vehicle_id=vehicle.vehicle_id, instant=OCCURRED_AT)
