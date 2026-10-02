"""Query `GetVehicleConfigurationAt` — Titan Asset A5.

O slice atual de `Vehicle` guarda a baseline vigente (`current_baseline_ref`) e
o instante em que ela passou a valer para o veículo. Ele não guarda histórico de
baselines anteriores dentro do agregado. Por isso esta query responde somente
com a baseline atual quando ela cobre o instante solicitado; não reconstrói uma
baseline histórica inexistente no estado disponível.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from packages.asset_domain.configuration import ConfigurationBaseline
from packages.asset_domain.vehicle import Vehicle
from packages.shared_kernel import TypedId
from packages.shared_kernel.temporal import require_utc


class VehicleConfigurationVehicleRepositoryPort(Protocol):
    def get_by_id(self, vehicle_id: TypedId) -> Vehicle | None: ...


class VehicleConfigurationBaselineRepositoryPort(Protocol):
    def get_by_id(self, baseline_id: TypedId) -> ConfigurationBaseline | None: ...


class VehicleConfigurationAtNaoEncontrada(KeyError):
    """Não há baseline configurável para o veículo no instante solicitado."""


def _instant_in_effectivity(baseline: ConfigurationBaseline, instant: datetime) -> bool:
    effectivity = baseline.effectivity
    if instant < effectivity.valid_from:
        return False
    return effectivity.valid_to is None or instant < effectivity.valid_to


def _serial_in_effectivity(baseline: ConfigurationBaseline, vehicle: Vehicle) -> bool:
    serial = vehicle.identifiers.serial_number
    effectivity = baseline.effectivity
    if effectivity.serial_from is not None and serial < effectivity.serial_from:
        return False
    return effectivity.serial_to is None or serial <= effectivity.serial_to


@dataclass(frozen=True, slots=True)
class VehicleConfigurationAt:
    vehicle: Vehicle
    baseline: ConfigurationBaseline
    instant: datetime


@dataclass(frozen=True, slots=True)
class VehicleConfigurationAtService:
    vehicle_repository: VehicleConfigurationVehicleRepositoryPort
    baseline_repository: VehicleConfigurationBaselineRepositoryPort

    def get_configuration_at(
        self, *, vehicle_id: TypedId, instant: datetime
    ) -> VehicleConfigurationAt:
        require_utc(instant, field_name="instant")
        vehicle = self.vehicle_repository.get_by_id(vehicle_id)
        if (
            vehicle is None
            or vehicle.current_baseline_ref is None
            or vehicle.baseline_valid_from is None
        ):
            raise VehicleConfigurationAtNaoEncontrada(
                f"Vehicle '{vehicle_id.value}' não possui baseline vigente."
            )
        if instant < vehicle.baseline_valid_from:
            raise VehicleConfigurationAtNaoEncontrada(
                "O instante solicitado é anterior à baseline vigente registrada no veículo."
            )
        baseline = self.baseline_repository.get_by_id(vehicle.current_baseline_ref)
        if (
            baseline is None
            or baseline.model_ref != vehicle.model_ref
            or baseline.variant_ref != vehicle.variant_ref
            or not _instant_in_effectivity(baseline, instant)
            or not _serial_in_effectivity(baseline, vehicle)
        ):
            raise VehicleConfigurationAtNaoEncontrada(
                f"ConfigurationBaseline vigente não cobre Vehicle '{vehicle_id.value}'."
            )
        return VehicleConfigurationAt(vehicle=vehicle, baseline=baseline, instant=instant)
