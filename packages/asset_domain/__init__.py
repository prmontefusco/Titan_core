"""Módulo de domínio da vertical Titan Asset & Sustainment (A2, primeiro slice).

Ver `docs/asset/05_DOMAIN_MODEL.md`. Cresce incrementalmente por agregado — nada
aqui existe antes do agregado que o usa (constituição §38).
"""

from packages.asset_domain.events import (
    ASSET_VEHICLE_EVENT_TYPES,
    VEHICLE_CONFIGURATION_BASELINE_SET,
    VEHICLE_LIFECYCLE_STATE_CHANGED,
    VEHICLE_METER_READING_CORRECTED,
    VEHICLE_METER_READING_RECORDED,
    VEHICLE_REGISTERED,
    VEHICLE_RETURNED_TO_SERVICE,
)
from packages.asset_domain.vehicle import (
    AssetOwnership,
    LeituraDeMedidorRetrocedeu,
    MeterCorrection,
    MeterKind,
    MeterReading,
    RetornoAoServicoInvalido,
    TransicaoDeCicloDeVidaInvalida,
    Vehicle,
    VehicleIdentifiers,
    VehicleLifecycleState,
)

__all__ = [
    "ASSET_VEHICLE_EVENT_TYPES",
    "VEHICLE_CONFIGURATION_BASELINE_SET",
    "VEHICLE_LIFECYCLE_STATE_CHANGED",
    "VEHICLE_METER_READING_CORRECTED",
    "VEHICLE_METER_READING_RECORDED",
    "VEHICLE_REGISTERED",
    "VEHICLE_RETURNED_TO_SERVICE",
    "AssetOwnership",
    "LeituraDeMedidorRetrocedeu",
    "MeterCorrection",
    "MeterKind",
    "MeterReading",
    "RetornoAoServicoInvalido",
    "TransicaoDeCicloDeVidaInvalida",
    "Vehicle",
    "VehicleIdentifiers",
    "VehicleLifecycleState",
]
