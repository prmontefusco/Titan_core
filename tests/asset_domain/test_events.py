"""Contrato dos eventos de `Vehicle` (A2). Espelha `tests/livestock_domain/test_events_contract.py`.

`CanonicalPayload` preserva só bytes serializados e versionados — não expõe
decodificação pública (`packages/core_domain/events.py`). O contrato testável é:
schema derivado do `event_type`, determinismo dos bytes para o mesmo conteúdo, e
namespace `asset.vehicle.*` em todo `message_type` declarado.
"""

import re
from datetime import UTC, datetime
from decimal import Decimal

from packages.asset_domain import events
from packages.core_domain.events import CanonicalPayload
from packages.shared_kernel import TypedId

MOMENTO = datetime(2026, 9, 11, 12, 0, tzinfo=UTC)

EXPECTED_EVENT_TYPES = frozenset(
    {
        "asset.vehicle.registered",
        "asset.vehicle.configuration_baseline_set",
        "asset.vehicle.meter_reading_recorded",
        "asset.vehicle.meter_reading_corrected",
        "asset.vehicle.lifecycle_state_changed",
        "asset.vehicle.returned_to_service",
    }
)


def test_declared_event_types_are_frozen() -> None:
    assert events.ASSET_VEHICLE_EVENT_TYPES == EXPECTED_EVENT_TYPES


def test_every_event_type_is_namespaced_under_asset_and_canonical() -> None:
    canonical = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*$")
    for event_type in events.ASSET_VEHICLE_EVENT_TYPES:
        assert event_type.startswith("asset.vehicle.")
        assert canonical.fullmatch(event_type), event_type


def test_vehicle_registered_payload_schema_derives_from_event_type() -> None:
    payload = events.vehicle_registered_payload(
        vehicle_id=TypedId.new("vehicle"),
        model_ref=TypedId.new("vehicle_model"),
        variant_ref=None,
        serial_number="SN-0001",
        chassis=None,
        fleet_number="F-01",
        site_ref=None,
        ownership="COMPANY",
    )
    assert isinstance(payload, CanonicalPayload)
    assert payload.schema == "asset_vehicle_registered_payload"
    assert payload.version == events.PAYLOAD_VERSION


def test_vehicle_registered_payload_is_deterministic_for_the_same_content() -> None:
    vehicle_id = TypedId.new("vehicle")
    model_ref = TypedId.new("vehicle_model")
    arguments = dict(
        vehicle_id=vehicle_id,
        model_ref=model_ref,
        variant_ref=None,
        serial_number="SN-0001",
        chassis=None,
        fleet_number=None,
        site_ref=None,
        ownership="COMPANY",
    )
    first = events.vehicle_registered_payload(**arguments)  # type: ignore[arg-type]
    second = events.vehicle_registered_payload(**arguments)  # type: ignore[arg-type]
    assert first.canonical_bytes == second.canonical_bytes


def test_vehicle_configuration_baseline_set_payload_builds() -> None:
    payload = events.vehicle_configuration_baseline_set_payload(
        vehicle_id=TypedId.new("vehicle"),
        baseline_ref=TypedId.new("configuration_baseline"),
        valid_from=MOMENTO,
        previous_baseline_ref=None,
        previous_valid_from=None,
    )
    assert payload.schema == "asset_vehicle_configuration_baseline_set_payload"


def test_vehicle_meter_reading_recorded_payload_accepts_decimal_value() -> None:
    """O serializador canônico recusa float; o builder precisa aceitar Decimal
    sem lançar (mesma razão de `_decimal` em `livestock_domain/events.py`)."""
    payload = events.vehicle_meter_reading_recorded_payload(
        vehicle_id=TypedId.new("vehicle"),
        reading_id=TypedId.new("vehicle_meter_reading"),
        kind="HOURS",
        value=Decimal("1234.5"),
        observed_at=MOMENTO,
        source="odometer",
    )
    assert payload.schema == "asset_vehicle_meter_reading_recorded_payload"


def test_vehicle_meter_reading_corrected_payload_builds() -> None:
    payload = events.vehicle_meter_reading_corrected_payload(
        vehicle_id=TypedId.new("vehicle"),
        correction_id=TypedId.new("vehicle_meter_correction"),
        original_reading_id=TypedId.new("vehicle_meter_reading"),
        corrected_value=Decimal("10"),
        reason="motivo",
    )
    assert payload.schema == "asset_vehicle_meter_reading_corrected_payload"


def test_vehicle_lifecycle_state_changed_payload_accepts_optional_reason_and_wo() -> None:
    payload = events.vehicle_lifecycle_state_changed_payload(
        vehicle_id=TypedId.new("vehicle"),
        from_state="AVAILABLE",
        to_state="DEGRADED",
        reason=None,
        work_order_ref=None,
    )
    assert payload.schema == "asset_vehicle_lifecycle_state_changed_payload"


def test_vehicle_returned_to_service_payload_builds() -> None:
    payload = events.vehicle_returned_to_service_payload(
        vehicle_id=TypedId.new("vehicle"),
        work_order_ref=TypedId.new("work_order"),
        validation_ref=TypedId.new("post_maintenance_validation"),
    )
    assert payload.schema == "asset_vehicle_returned_to_service_payload"


def test_vehicle_registered_is_a_registered_event_type() -> None:
    assert events.VEHICLE_REGISTERED in events.ASSET_VEHICLE_EVENT_TYPES
