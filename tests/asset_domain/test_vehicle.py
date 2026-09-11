"""Testes unitários de domínio para `Vehicle` (A2, primeiro slice de Titan Asset).

Cobre I‑VEH‑1 (baseline vigente única), I‑VEH‑2 (leitura de medidor monotônica,
correção não apaga) e I‑VEH‑3 (ciclo de vida monotônico; `IN_MAINTENANCE ->
AVAILABLE` só via `return_to_service`). `docs/asset/07_INVARIANTS.md`.
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

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
from packages.shared_kernel import OrganizationId, TypedId

MOMENTO = datetime(2026, 9, 11, 12, 0, tzinfo=UTC)


def _vehicle(**overrides: object) -> Vehicle:
    defaults: dict[str, object] = dict(
        vehicle_id=TypedId.new("vehicle"),
        organization_id=OrganizationId(uuid4()),
        model_ref=TypedId.new("vehicle_model"),
        identifiers=VehicleIdentifiers(serial_number="SN-0001"),
        ownership=AssetOwnership.COMPANY,
    )
    defaults.update(overrides)
    return Vehicle(**defaults)  # type: ignore[arg-type]


def test_vehicle_creation() -> None:
    vehicle = _vehicle()
    assert vehicle.lifecycle_state is VehicleLifecycleState.AVAILABLE
    assert vehicle.current_baseline_ref is None
    assert vehicle.meter_readings == ()
    assert vehicle.version == 1


def test_vehicle_id_entity_type_is_enforced() -> None:
    with pytest.raises(ValueError, match="entity_type 'vehicle'"):
        _vehicle(vehicle_id=TypedId.new("animal"))


def test_serial_number_cannot_be_blank() -> None:
    with pytest.raises(ValueError, match="serial_number não pode ser vazio"):
        VehicleIdentifiers(serial_number="   ")


# --- I-VEH-1 ------------------------------------------------------------------


def test_set_configuration_baseline_defines_current_ref_and_valid_from() -> None:
    vehicle = _vehicle()
    baseline_ref = TypedId.new("configuration_baseline")

    updated = vehicle.set_configuration_baseline(baseline_ref, valid_from=MOMENTO)

    assert updated.current_baseline_ref == baseline_ref
    assert updated.baseline_valid_from == MOMENTO
    assert updated.version == vehicle.version + 1
    # Só existe UMA baseline vigente por vez — trocar substitui, não acumula.
    assert isinstance(updated.current_baseline_ref, TypedId)


def test_set_configuration_baseline_rejects_wrong_entity_type() -> None:
    vehicle = _vehicle()
    with pytest.raises(ValueError, match="entity_type 'configuration_baseline'"):
        vehicle.set_configuration_baseline(TypedId.new("part"), valid_from=MOMENTO)


def test_set_configuration_baseline_rejects_valid_from_before_current() -> None:
    vehicle = _vehicle().set_configuration_baseline(
        TypedId.new("configuration_baseline"), valid_from=MOMENTO
    )
    earlier = datetime(2026, 1, 1, tzinfo=UTC)
    with pytest.raises(ValueError, match="não pode ser anterior"):
        vehicle.set_configuration_baseline(
            TypedId.new("configuration_baseline"), valid_from=earlier
        )


def test_baseline_valid_from_without_baseline_ref_is_rejected() -> None:
    with pytest.raises(ValueError, match="baseline_valid_from sem current_baseline_ref"):
        _vehicle(baseline_valid_from=MOMENTO)


def test_baseline_ref_without_valid_from_is_rejected() -> None:
    with pytest.raises(ValueError, match="baseline_valid_from é obrigatório"):
        _vehicle(current_baseline_ref=TypedId.new("configuration_baseline"))


# --- I-VEH-2 ------------------------------------------------------------------


def _reading(
    value: str, *, observed_at: datetime = MOMENTO, kind: MeterKind = MeterKind.HOURS
) -> MeterReading:
    return MeterReading(
        reading_id=TypedId.new("vehicle_meter_reading"),
        kind=kind,
        value=Decimal(value),
        observed_at=observed_at,
        recorded_at=observed_at,
        source="odometer",
    )


def test_record_meter_reading_accepts_monotonic_sequence() -> None:
    vehicle = _vehicle()
    vehicle = vehicle.record_meter_reading(_reading("100"))
    vehicle = vehicle.record_meter_reading(
        _reading("150", observed_at=datetime(2026, 9, 12, tzinfo=UTC))
    )
    assert [r.value for r in vehicle.meter_readings] == [Decimal("100"), Decimal("150")]


def test_record_meter_reading_rejects_regression() -> None:
    vehicle = _vehicle().record_meter_reading(_reading("100"))
    with pytest.raises(LeituraDeMedidorRetrocedeu):
        vehicle.record_meter_reading(_reading("50", observed_at=datetime(2026, 9, 12, tzinfo=UTC)))


def test_meter_kinds_are_tracked_independently() -> None:
    vehicle = _vehicle()
    vehicle = vehicle.record_meter_reading(_reading("500", kind=MeterKind.HOURS))
    # KILOMETERS começa do zero mesmo com HOURS em 500 — medidores independentes.
    vehicle = vehicle.record_meter_reading(_reading("10", kind=MeterKind.KILOMETERS))
    assert len(vehicle.meter_readings) == 2


def test_correct_meter_reading_preserves_original() -> None:
    original = _reading("100")
    vehicle = _vehicle().record_meter_reading(original)

    correction = MeterCorrection(
        correction_id=TypedId.new("vehicle_meter_correction"),
        original_reading_id=original.reading_id,
        corrected_value=Decimal("120"),
        reason="Leitura registrada errada por engano de digitação.",
        corrected_at=MOMENTO,
    )
    corrected = vehicle.correct_meter_reading(correction)

    # A leitura original PERMANECE — correção é aditiva (constituição §24).
    assert corrected.meter_readings == (original,)
    assert corrected.meter_corrections == (correction,)


def test_correct_meter_reading_requires_existing_original() -> None:
    vehicle = _vehicle()
    correction = MeterCorrection(
        correction_id=TypedId.new("vehicle_meter_correction"),
        original_reading_id=TypedId.new("vehicle_meter_reading"),
        corrected_value=Decimal("10"),
        reason="motivo",
        corrected_at=MOMENTO,
    )
    with pytest.raises(KeyError):
        vehicle.correct_meter_reading(correction)


def test_correct_meter_reading_requires_reason() -> None:
    with pytest.raises(ValueError, match="reason é obrigatório"):
        MeterCorrection(
            correction_id=TypedId.new("vehicle_meter_correction"),
            original_reading_id=TypedId.new("vehicle_meter_reading"),
            corrected_value=Decimal("10"),
            reason="  ",
            corrected_at=MOMENTO,
        )


# --- I-VEH-3 ------------------------------------------------------------------


def test_transition_lifecycle_allows_listed_transition() -> None:
    vehicle = _vehicle().transition_lifecycle(VehicleLifecycleState.MAINTENANCE_PLANNED)
    assert vehicle.lifecycle_state is VehicleLifecycleState.MAINTENANCE_PLANNED

    vehicle = vehicle.transition_lifecycle(VehicleLifecycleState.IN_MAINTENANCE)
    assert vehicle.lifecycle_state is VehicleLifecycleState.IN_MAINTENANCE


def test_transition_lifecycle_rejects_unlisted_transition() -> None:
    vehicle = _vehicle()
    with pytest.raises(TransicaoDeCicloDeVidaInvalida):
        # AVAILABLE -> IN_MAINTENANCE direto não está na tabela.
        vehicle.transition_lifecycle(VehicleLifecycleState.IN_MAINTENANCE)


def test_transition_lifecycle_never_reaches_available_from_in_maintenance() -> None:
    """I-VEH-3: a única via de IN_MAINTENANCE -> AVAILABLE é return_to_service."""
    vehicle = (
        _vehicle()
        .transition_lifecycle(VehicleLifecycleState.MAINTENANCE_PLANNED)
        .transition_lifecycle(VehicleLifecycleState.IN_MAINTENANCE)
    )
    with pytest.raises(TransicaoDeCicloDeVidaInvalida, match="return_to_service"):
        vehicle.transition_lifecycle(VehicleLifecycleState.AVAILABLE)


def test_return_to_service_from_in_maintenance_succeeds() -> None:
    vehicle = (
        _vehicle()
        .transition_lifecycle(VehicleLifecycleState.MAINTENANCE_PLANNED)
        .transition_lifecycle(VehicleLifecycleState.IN_MAINTENANCE)
    )
    returned = vehicle.return_to_service(
        work_order_ref=TypedId.new("work_order"),
        validation_ref=TypedId.new("post_maintenance_validation"),
    )
    assert returned.lifecycle_state is VehicleLifecycleState.AVAILABLE


def test_return_to_service_rejected_outside_in_maintenance() -> None:
    vehicle = _vehicle()
    with pytest.raises(RetornoAoServicoInvalido):
        vehicle.return_to_service(
            work_order_ref=TypedId.new("work_order"),
            validation_ref=TypedId.new("post_maintenance_validation"),
        )


def test_return_to_service_validates_reference_entity_types() -> None:
    vehicle = (
        _vehicle()
        .transition_lifecycle(VehicleLifecycleState.MAINTENANCE_PLANNED)
        .transition_lifecycle(VehicleLifecycleState.IN_MAINTENANCE)
    )
    with pytest.raises(ValueError, match="entity_type 'work_order'"):
        vehicle.return_to_service(
            work_order_ref=TypedId.new("animal"),
            validation_ref=TypedId.new("post_maintenance_validation"),
        )
