"""Caso de uso do agregado `Vehicle` — Titan Asset & Sustainment (A4).

`VehicleRepositoryPort` é a porta que a aplicação define e
`asset_infrastructure.persistence.vehicle_repository.TransactionalVehicleRepository`
satisfaz estruturalmente (mesmo padrão de `AnimalRepositoryPort` em
`livestock_application.animal_service`). O serviço não checa permissão (isso é
responsabilidade do adapter HTTP em A5, `require_permission` — mesmo padrão de
`apps/api/livestock_dependencies.py`) nem abre transação (a `Connection`
injetada no repositório/`event_log` pela camada de composição já amarra
`save`/`update`+`record` na mesma unidade de trabalho).
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol

from packages.asset_application.event_recorder import AssetEventRecorder, AssetOperationContext
from packages.asset_domain.events import (
    VEHICLE_CONFIGURATION_BASELINE_SET,
    VEHICLE_LIFECYCLE_STATE_CHANGED,
    VEHICLE_METER_READING_CORRECTED,
    VEHICLE_METER_READING_RECORDED,
    VEHICLE_REGISTERED,
    VEHICLE_RETURNED_TO_SERVICE,
    vehicle_configuration_baseline_set_payload,
    vehicle_lifecycle_state_changed_payload,
    vehicle_meter_reading_corrected_payload,
    vehicle_meter_reading_recorded_payload,
    vehicle_registered_payload,
    vehicle_returned_to_service_payload,
)
from packages.asset_domain.vehicle import (
    AssetOwnership,
    MeterCorrection,
    MeterKind,
    MeterReading,
    Vehicle,
    VehicleIdentifiers,
    VehicleLifecycleState,
)
from packages.shared_kernel import TypedId


class VehicleNaoEncontrado(KeyError):
    """`vehicle_id` não corresponde a nenhum `Vehicle` desta Organization."""


class VehicleRepositoryPort(Protocol):
    def save(self, vehicle: Vehicle) -> None: ...

    def update(self, vehicle: Vehicle) -> None: ...

    def get_by_id(self, vehicle_id: TypedId) -> Vehicle | None: ...


@dataclass(frozen=True, slots=True)
class VehicleService:
    repository: VehicleRepositoryPort
    recorder: AssetEventRecorder

    def _require(self, vehicle_id: TypedId) -> Vehicle:
        vehicle = self.repository.get_by_id(vehicle_id)
        if vehicle is None:
            raise VehicleNaoEncontrado(f"Vehicle '{vehicle_id.value}' não encontrado.")
        return vehicle

    def register_vehicle(
        self,
        context: AssetOperationContext,
        *,
        model_ref: TypedId,
        identifiers: VehicleIdentifiers,
        ownership: AssetOwnership,
        variant_ref: TypedId | None = None,
        site_ref: TypedId | None = None,
    ) -> Vehicle:
        vehicle = Vehicle(
            vehicle_id=TypedId.new("vehicle"),
            organization_id=context.organization_id,
            model_ref=model_ref,
            identifiers=identifiers,
            ownership=ownership,
            variant_ref=variant_ref,
            site_ref=site_ref,
        )
        self.repository.save(vehicle)
        self.recorder.record(
            context=context,
            aggregate_id=vehicle.vehicle_id,
            event_type=VEHICLE_REGISTERED,
            payload=vehicle_registered_payload(
                vehicle_id=vehicle.vehicle_id,
                model_ref=vehicle.model_ref,
                variant_ref=vehicle.variant_ref,
                serial_number=vehicle.identifiers.serial_number,
                chassis=vehicle.identifiers.chassis,
                fleet_number=vehicle.identifiers.fleet_number,
                site_ref=vehicle.site_ref,
                ownership=vehicle.ownership.value,
            ),
            occurred_at=vehicle.created_at,
        )
        return vehicle

    def set_configuration_baseline(
        self,
        context: AssetOperationContext,
        vehicle_id: TypedId,
        *,
        baseline_ref: TypedId,
        valid_from: datetime,
    ) -> Vehicle:
        vehicle = self._require(vehicle_id)
        previous_baseline_ref = vehicle.current_baseline_ref
        previous_valid_from = vehicle.baseline_valid_from
        updated = vehicle.set_configuration_baseline(baseline_ref, valid_from=valid_from)
        self.repository.update(updated)
        self.recorder.record(
            context=context,
            aggregate_id=updated.vehicle_id,
            event_type=VEHICLE_CONFIGURATION_BASELINE_SET,
            payload=vehicle_configuration_baseline_set_payload(
                vehicle_id=updated.vehicle_id,
                baseline_ref=baseline_ref,
                valid_from=valid_from,
                previous_baseline_ref=previous_baseline_ref,
                previous_valid_from=previous_valid_from,
            ),
            occurred_at=valid_from,
        )
        return updated

    def record_meter_reading(
        self,
        context: AssetOperationContext,
        vehicle_id: TypedId,
        *,
        kind: MeterKind,
        value: Decimal,
        observed_at: datetime,
        recorded_at: datetime,
        source: str,
    ) -> Vehicle:
        vehicle = self._require(vehicle_id)
        reading = MeterReading(
            reading_id=TypedId.new("vehicle_meter_reading"),
            kind=kind,
            value=value,
            observed_at=observed_at,
            recorded_at=recorded_at,
            source=source,
        )
        updated = vehicle.record_meter_reading(reading)
        self.repository.update(updated)
        self.recorder.record(
            context=context,
            aggregate_id=updated.vehicle_id,
            event_type=VEHICLE_METER_READING_RECORDED,
            payload=vehicle_meter_reading_recorded_payload(
                vehicle_id=updated.vehicle_id,
                reading_id=reading.reading_id,
                kind=reading.kind.value,
                value=reading.value,
                observed_at=reading.observed_at,
                source=reading.source,
            ),
            occurred_at=recorded_at,
        )
        return updated

    def correct_meter_reading(
        self,
        context: AssetOperationContext,
        vehicle_id: TypedId,
        *,
        original_reading_id: TypedId,
        corrected_value: Decimal,
        reason: str,
        corrected_at: datetime,
    ) -> Vehicle:
        vehicle = self._require(vehicle_id)
        correction = MeterCorrection(
            correction_id=TypedId.new("vehicle_meter_correction"),
            original_reading_id=original_reading_id,
            corrected_value=corrected_value,
            reason=reason,
            corrected_at=corrected_at,
        )
        updated = vehicle.correct_meter_reading(correction)
        self.repository.update(updated)
        self.recorder.record(
            context=context,
            aggregate_id=updated.vehicle_id,
            event_type=VEHICLE_METER_READING_CORRECTED,
            payload=vehicle_meter_reading_corrected_payload(
                vehicle_id=updated.vehicle_id,
                correction_id=correction.correction_id,
                original_reading_id=correction.original_reading_id,
                corrected_value=correction.corrected_value,
                reason=correction.reason,
            ),
            occurred_at=corrected_at,
        )
        return updated

    def transition_lifecycle(
        self,
        context: AssetOperationContext,
        vehicle_id: TypedId,
        *,
        new_state: VehicleLifecycleState,
        reason: str | None = None,
        occurred_at: datetime,
    ) -> Vehicle:
        vehicle = self._require(vehicle_id)
        from_state = vehicle.lifecycle_state
        updated = vehicle.transition_lifecycle(new_state, reason=reason)
        self.repository.update(updated)
        self.recorder.record(
            context=context,
            aggregate_id=updated.vehicle_id,
            event_type=VEHICLE_LIFECYCLE_STATE_CHANGED,
            payload=vehicle_lifecycle_state_changed_payload(
                vehicle_id=updated.vehicle_id,
                from_state=from_state.value,
                to_state=updated.lifecycle_state.value,
                reason=reason,
                work_order_ref=None,
            ),
            occurred_at=occurred_at,
        )
        return updated

    def return_to_service(
        self,
        context: AssetOperationContext,
        vehicle_id: TypedId,
        *,
        work_order_ref: TypedId,
        validation_ref: TypedId,
        occurred_at: datetime,
    ) -> Vehicle:
        vehicle = self._require(vehicle_id)
        updated = vehicle.return_to_service(
            work_order_ref=work_order_ref, validation_ref=validation_ref
        )
        self.repository.update(updated)
        self.recorder.record(
            context=context,
            aggregate_id=updated.vehicle_id,
            event_type=VEHICLE_RETURNED_TO_SERVICE,
            payload=vehicle_returned_to_service_payload(
                vehicle_id=updated.vehicle_id,
                work_order_ref=work_order_ref,
                validation_ref=validation_ref,
            ),
            occurred_at=occurred_at,
        )
        return updated

    def get_vehicle(self, vehicle_id: TypedId) -> Vehicle | None:
        return self.repository.get_by_id(vehicle_id)
