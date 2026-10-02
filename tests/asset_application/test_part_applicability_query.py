"""Testes da query `ResolvePartApplicability` — Titan Asset A5."""

from datetime import UTC, datetime

import pytest

from packages.asset_application.part_applicability_query import (
    PartApplicabilityQueryService,
    PartApplicabilityRepositoryPort,
    PartApplicabilityVehicleNaoEncontrado,
    PartApplicabilityVehicleRepositoryPort,
)
from packages.asset_domain.applicability import Applicability, ApplicabilityTarget
from packages.asset_domain.vehicle import AssetOwnership, Vehicle, VehicleIdentifiers
from packages.shared_kernel import OrganizationId, TypedId

INSTANT = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)


class InMemoryVehicleRepository(PartApplicabilityVehicleRepositoryPort):
    def __init__(self, items: tuple[Vehicle, ...]) -> None:
        self.items = {item.vehicle_id: item for item in items}

    def get_by_id(self, vehicle_id: TypedId) -> Vehicle | None:
        return self.items.get(vehicle_id)


class InMemoryApplicabilityRepository(PartApplicabilityRepositoryPort):
    def __init__(self, items: tuple[Applicability, ...]) -> None:
        self.items = items

    def list_by_part_and_target(
        self,
        *,
        part_ref: TypedId,
        model_ref: TypedId,
        variant_ref: TypedId | None,
    ) -> tuple[Applicability, ...]:
        return tuple(
            item
            for item in self.items
            if item.part_ref == part_ref
            and item.target.model_ref == model_ref
            and item.target.variant_ref == variant_ref
        )


def _vehicle(model_ref: TypedId) -> Vehicle:
    return Vehicle(
        vehicle_id=TypedId.new("vehicle"),
        organization_id=OrganizationId.new(),
        model_ref=model_ref,
        identifiers=VehicleIdentifiers(serial_number="SN-100"),
        ownership=AssetOwnership.COMPANY,
        created_at=INSTANT,
    )


def _applicability(part_ref: TypedId, model_ref: TypedId) -> Applicability:
    return Applicability(
        applicability_id=TypedId.new("applicability"),
        organization_id=OrganizationId.new(),
        part_ref=part_ref,
        part_revision_ref=TypedId.new("part_revision"),
        target=ApplicabilityTarget(
            model_ref=model_ref,
            variant_ref=None,
            serial_from="SN-001",
            serial_to="SN-999",
            valid_from=datetime(2026, 1, 1, tzinfo=UTC),
            valid_until=None,
        ),
        evidence_ref=TypedId.new("evidence"),
        asserted_at=INSTANT,
        asserted_by=TypedId.new("user"),
    )


def test_part_applicability_returns_active_assertions_with_evidence() -> None:
    part_ref = TypedId.new("part")
    model_ref = TypedId.new("vehicle_model")
    vehicle = _vehicle(model_ref)
    applicability = _applicability(part_ref, model_ref)
    service = PartApplicabilityQueryService(
        vehicle_repository=InMemoryVehicleRepository((vehicle,)),
        applicability_repository=InMemoryApplicabilityRepository((applicability,)),
    )

    result = service.resolve(part_ref=part_ref, vehicle_id=vehicle.vehicle_id, instant=INSTANT)

    assert result.part_ref == part_ref
    assert result.vehicle == vehicle
    assert result.assertions == (applicability,)
    assert result.assertions[0].evidence_ref.entity_type == "evidence"


def test_part_applicability_filters_assertions_outside_serial_range() -> None:
    part_ref = TypedId.new("part")
    model_ref = TypedId.new("vehicle_model")
    vehicle = _vehicle(model_ref)
    applicability = _applicability(part_ref, model_ref)
    outside_serial = Applicability(
        applicability_id=TypedId.new("applicability"),
        organization_id=OrganizationId.new(),
        part_ref=part_ref,
        part_revision_ref=TypedId.new("part_revision"),
        target=ApplicabilityTarget(
            model_ref=model_ref,
            variant_ref=None,
            serial_from="SN-200",
            serial_to=None,
            valid_from=datetime(2026, 1, 1, tzinfo=UTC),
            valid_until=None,
        ),
        evidence_ref=TypedId.new("evidence"),
        asserted_at=INSTANT,
        asserted_by=TypedId.new("user"),
    )
    service = PartApplicabilityQueryService(
        vehicle_repository=InMemoryVehicleRepository((vehicle,)),
        applicability_repository=InMemoryApplicabilityRepository((applicability, outside_serial)),
    )

    result = service.resolve(part_ref=part_ref, vehicle_id=vehicle.vehicle_id, instant=INSTANT)

    assert result.assertions == (applicability,)


def test_part_applicability_rejects_missing_vehicle() -> None:
    service = PartApplicabilityQueryService(
        vehicle_repository=InMemoryVehicleRepository(()),
        applicability_repository=InMemoryApplicabilityRepository(()),
    )

    with pytest.raises(PartApplicabilityVehicleNaoEncontrado):
        service.resolve(
            part_ref=TypedId.new("part"),
            vehicle_id=TypedId.new("vehicle"),
            instant=INSTANT,
        )
