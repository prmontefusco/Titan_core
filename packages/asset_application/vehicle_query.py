"""Query de detalhe de `Vehicle` — Titan Asset A5."""

from dataclasses import dataclass
from typing import Protocol

from packages.asset_domain.vehicle import Vehicle
from packages.shared_kernel import TypedId


class VehicleQueryRepositoryPort(Protocol):
    def get_by_id(self, vehicle_id: TypedId) -> Vehicle | None: ...


class VehicleDetailNaoEncontrado(KeyError):
    """`vehicle_id` não corresponde a nenhum `Vehicle` visível nesta Organization."""


@dataclass(frozen=True, slots=True)
class VehicleQueryService:
    repository: VehicleQueryRepositoryPort

    def get_vehicle(self, vehicle_id: TypedId) -> Vehicle:
        vehicle = self.repository.get_by_id(vehicle_id)
        if vehicle is None:
            raise VehicleDetailNaoEncontrado(f"Vehicle '{vehicle_id.value}' não encontrado.")
        return vehicle
