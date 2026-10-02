"""Query `ResolvePartApplicability` — Titan Asset A5."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from packages.asset_domain.applicability import Applicability
from packages.asset_domain.vehicle import Vehicle
from packages.shared_kernel import TypedId
from packages.shared_kernel.temporal import require_utc


class PartApplicabilityVehicleRepositoryPort(Protocol):
    def get_by_id(self, vehicle_id: TypedId) -> Vehicle | None: ...


class PartApplicabilityRepositoryPort(Protocol):
    def list_by_part_and_target(
        self,
        *,
        part_ref: TypedId,
        model_ref: TypedId,
        variant_ref: TypedId | None,
    ) -> tuple[Applicability, ...]: ...


class PartApplicabilityVehicleNaoEncontrado(KeyError):
    """`vehicle_id` não corresponde a nenhum Vehicle desta Organization."""


def _serial_covered(applicability: Applicability, vehicle: Vehicle) -> bool:
    serial = vehicle.identifiers.serial_number
    target = applicability.target
    if target.serial_from is not None and serial < target.serial_from:
        return False
    return target.serial_to is None or serial <= target.serial_to


@dataclass(frozen=True, slots=True)
class PartApplicabilityResolution:
    part_ref: TypedId
    vehicle: Vehicle
    instant: datetime
    assertions: tuple[Applicability, ...]


@dataclass(frozen=True, slots=True)
class PartApplicabilityQueryService:
    vehicle_repository: PartApplicabilityVehicleRepositoryPort
    applicability_repository: PartApplicabilityRepositoryPort

    def resolve(
        self, *, part_ref: TypedId, vehicle_id: TypedId, instant: datetime
    ) -> PartApplicabilityResolution:
        require_utc(instant, field_name="instant")
        vehicle = self.vehicle_repository.get_by_id(vehicle_id)
        if vehicle is None:
            raise PartApplicabilityVehicleNaoEncontrado(
                f"Vehicle '{vehicle_id.value}' não encontrado."
            )
        candidates = self.applicability_repository.list_by_part_and_target(
            part_ref=part_ref,
            model_ref=vehicle.model_ref,
            variant_ref=vehicle.variant_ref,
        )
        assertions = tuple(
            applicability
            for applicability in candidates
            if applicability.is_active_at(instant) and _serial_covered(applicability, vehicle)
        )
        return PartApplicabilityResolution(
            part_ref=part_ref,
            vehicle=vehicle,
            instant=instant,
            assertions=assertions,
        )
