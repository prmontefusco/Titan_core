"""Contrato de eventos de domínio da vertical Titan Asset (A2, primeiro slice).

Mesmo padrão de `packages/livestock_domain/events.py`: um evento da vertical é um
`DomainEvent` do Core (não subclasse) — `event_type` + payload canônico. Namespace
`asset.` (`docs/asset/08_DOMAIN_EVENTS.md`; manifesto `docs/architecture/verticals.toml`).

Este arquivo cobre só os eventos de `Vehicle` (`packages/asset_domain/vehicle.py`).
Os demais eventos de `08_DOMAIN_EVENTS.md` (Part/Applicability/Inventory/CustomerSite/
sustainment) entram junto dos respectivos agregados.
"""

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal

from packages.core_domain.events import CanonicalPayload
from packages.shared_kernel import TypedId
from packages.shared_kernel.serialization import CanonicalValue

VEHICLE_REGISTERED = "asset.vehicle.registered"
VEHICLE_CONFIGURATION_BASELINE_SET = "asset.vehicle.configuration_baseline_set"
VEHICLE_METER_READING_RECORDED = "asset.vehicle.meter_reading_recorded"
VEHICLE_METER_READING_CORRECTED = "asset.vehicle.meter_reading_corrected"
VEHICLE_LIFECYCLE_STATE_CHANGED = "asset.vehicle.lifecycle_state_changed"
VEHICLE_RETURNED_TO_SERVICE = "asset.vehicle.returned_to_service"

ASSET_VEHICLE_EVENT_TYPES = frozenset(
    {
        VEHICLE_REGISTERED,
        VEHICLE_CONFIGURATION_BASELINE_SET,
        VEHICLE_METER_READING_RECORDED,
        VEHICLE_METER_READING_CORRECTED,
        VEHICLE_LIFECYCLE_STATE_CHANGED,
        VEHICLE_RETURNED_TO_SERVICE,
    }
)

PAYLOAD_VERSION = 1


def _payload(event_type: str, value: Mapping[str, CanonicalValue]) -> CanonicalPayload:
    schema = f"{event_type.replace('.', '_')}_payload"
    return CanonicalPayload.from_mapping(schema=schema, version=PAYLOAD_VERSION, value=value)


def _id(value: TypedId) -> str:
    return str(value.value)


def _optional_id(value: TypedId | None) -> str | None:
    return None if value is None else _id(value)


def _decimal(value: Decimal | float | None) -> Decimal | None:
    """O serializador canônico recusa float; área/quantidade viram Decimal."""
    return None if value is None else Decimal(str(value))


def vehicle_registered_payload(
    *,
    vehicle_id: TypedId,
    model_ref: TypedId,
    variant_ref: TypedId | None,
    serial_number: str,
    chassis: str | None,
    fleet_number: str | None,
    site_ref: TypedId | None,
    ownership: str,
) -> CanonicalPayload:
    return _payload(
        VEHICLE_REGISTERED,
        {
            "chassis": chassis,
            "fleet_number": fleet_number,
            "model_ref": _id(model_ref),
            "ownership": ownership,
            "serial_number": serial_number,
            "site_ref": _optional_id(site_ref),
            "variant_ref": _optional_id(variant_ref),
            "vehicle_id": _id(vehicle_id),
        },
    )


def vehicle_configuration_baseline_set_payload(
    *,
    vehicle_id: TypedId,
    baseline_ref: TypedId,
    valid_from: datetime,
    previous_baseline_ref: TypedId | None,
    previous_valid_from: datetime | None,
) -> CanonicalPayload:
    return _payload(
        VEHICLE_CONFIGURATION_BASELINE_SET,
        {
            "baseline_ref": _id(baseline_ref),
            "previous_baseline_ref": _optional_id(previous_baseline_ref),
            "previous_valid_from": previous_valid_from,
            "valid_from": valid_from,
            "vehicle_id": _id(vehicle_id),
        },
    )


def vehicle_meter_reading_recorded_payload(
    *,
    vehicle_id: TypedId,
    reading_id: TypedId,
    kind: str,
    value: Decimal,
    observed_at: datetime,
    source: str,
) -> CanonicalPayload:
    return _payload(
        VEHICLE_METER_READING_RECORDED,
        {
            "kind": kind,
            "observed_at": observed_at,
            "reading_id": _id(reading_id),
            "source": source,
            "value": _decimal(value),
            "vehicle_id": _id(vehicle_id),
        },
    )


def vehicle_meter_reading_corrected_payload(
    *,
    vehicle_id: TypedId,
    correction_id: TypedId,
    original_reading_id: TypedId,
    corrected_value: Decimal,
    reason: str,
) -> CanonicalPayload:
    return _payload(
        VEHICLE_METER_READING_CORRECTED,
        {
            "corrected_value": _decimal(corrected_value),
            "correction_id": _id(correction_id),
            "original_reading_id": _id(original_reading_id),
            "reason": reason,
            "vehicle_id": _id(vehicle_id),
        },
    )


def vehicle_lifecycle_state_changed_payload(
    *,
    vehicle_id: TypedId,
    from_state: str,
    to_state: str,
    reason: str | None,
    work_order_ref: TypedId | None,
) -> CanonicalPayload:
    return _payload(
        VEHICLE_LIFECYCLE_STATE_CHANGED,
        {
            "from_state": from_state,
            "reason": reason,
            "to_state": to_state,
            "vehicle_id": _id(vehicle_id),
            "work_order_ref": _optional_id(work_order_ref),
        },
    )


def vehicle_returned_to_service_payload(
    *,
    vehicle_id: TypedId,
    work_order_ref: TypedId,
    validation_ref: TypedId,
) -> CanonicalPayload:
    return _payload(
        VEHICLE_RETURNED_TO_SERVICE,
        {
            "validation_ref": _id(validation_ref),
            "vehicle_id": _id(vehicle_id),
            "work_order_ref": _id(work_order_ref),
        },
    )
