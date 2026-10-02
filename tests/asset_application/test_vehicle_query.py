"""Testes da query `GetVehicle` — Titan Asset A5."""

from datetime import UTC, datetime

import pytest

from packages.asset_application.vehicle_query import (
    VehicleDetailNaoEncontrado,
    VehicleQueryRepositoryPort,
    VehicleQueryService,
)
from packages.asset_domain.vehicle import AssetOwnership, Vehicle, VehicleIdentifiers
from packages.shared_kernel import OrganizationId, TypedId

OCCURRED_AT = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)


class InMemoryVehicleQueryRepository(VehicleQueryRepositoryPort):
    def __init__(self, items: tuple[Vehicle, ...]) -> None:
        self.items = {item.vehicle_id: item for item in items}

    def get_by_id(self, vehicle_id: TypedId) -> Vehicle | None:
        return self.items.get(vehicle_id)


def _vehicle() -> Vehicle:
    return Vehicle(
        vehicle_id=TypedId.new("vehicle"),
        organization_id=OrganizationId.new(),
        model_ref=TypedId.new("vehicle_model"),
        identifiers=VehicleIdentifiers(serial_number="SN-001"),
        ownership=AssetOwnership.COMPANY,
        created_at=OCCURRED_AT,
    )


def test_vehicle_query_returns_aggregate() -> None:
    vehicle = _vehicle()
    service = VehicleQueryService(InMemoryVehicleQueryRepository((vehicle,)))

    assert service.get_vehicle(vehicle.vehicle_id) == vehicle


def test_vehicle_query_raises_when_missing() -> None:
    service = VehicleQueryService(InMemoryVehicleQueryRepository(()))

    with pytest.raises(VehicleDetailNaoEncontrado):
        service.get_vehicle(TypedId.new("vehicle"))
