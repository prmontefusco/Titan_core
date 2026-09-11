"""Persistência do agregado `Vehicle` — Titan Asset (A3).

`meter_readings`/`meter_corrections` são append-only no domínio (I-VEH-2:
correção nunca apaga a leitura original) — `meter_corrections` tem FK para
`meter_readings`, então `update()` nunca faz delete+reinsert dessas tabelas
(mesma lição de `part_repository.py`): só insere o que ainda não existe,
identificado por `reading_id`/`correction_id` (estáveis, nunca regenerados).
"""

from dataclasses import dataclass
from datetime import UTC
from typing import Any

from sqlalchemy import (
    Column,
    Connection,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
    Table,
    insert,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.engine import Row

from packages.asset_domain.vehicle import (
    AssetOwnership,
    MeterCorrection,
    MeterKind,
    MeterReading,
    Vehicle,
    VehicleIdentifiers,
    VehicleLifecycleState,
)
from packages.asset_infrastructure.persistence.metadata import asset_metadata
from packages.core_infrastructure.persistence.events import CORE_AUDIT_SCHEMA
from packages.shared_kernel import OrganizationId, TypedId

vehicles_table = Table(
    "vehicles",
    asset_metadata,
    Column("vehicle_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("model_id", PG_UUID(as_uuid=True), nullable=False),
    Column("serial_number", String(100), nullable=False),
    Column("chassis", String(100), nullable=True),
    Column("fleet_number", String(50), nullable=True),
    Column("ownership", String(20), nullable=False),
    Column("variant_id", PG_UUID(as_uuid=True), nullable=True),
    Column("site_id", PG_UUID(as_uuid=True), nullable=True),
    Column("current_baseline_id", PG_UUID(as_uuid=True), nullable=True),
    Column("baseline_valid_from", DateTime(timezone=True), nullable=True),
    Column("lifecycle_state", String(30), nullable=False),
    Column("version", Integer, nullable=False, default=1),
    Column("created_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_vehicles_organization",
    ),
    ForeignKeyConstraint(
        ["site_id"], ["core_audit.customer_sites.site_id"], name="fk_vehicles_site"
    ),
    ForeignKeyConstraint(
        ["current_baseline_id"],
        ["core_audit.configuration_baselines.baseline_id"],
        name="fk_vehicles_current_baseline",
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=asset",
)

vehicle_meter_readings_table = Table(
    "vehicle_meter_readings",
    asset_metadata,
    Column("reading_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("vehicle_id", PG_UUID(as_uuid=True), nullable=False),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("kind", String(20), nullable=False),
    Column("value", Numeric, nullable=False),
    Column("observed_at", DateTime(timezone=True), nullable=False),
    Column("recorded_at", DateTime(timezone=True), nullable=False),
    Column("source", String(100), nullable=False),
    ForeignKeyConstraint(
        ["vehicle_id"], ["core_audit.vehicles.vehicle_id"], name="fk_vehicle_meter_readings_vehicle"
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=asset",
)

vehicle_meter_corrections_table = Table(
    "vehicle_meter_corrections",
    asset_metadata,
    Column("correction_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("vehicle_id", PG_UUID(as_uuid=True), nullable=False),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("original_reading_id", PG_UUID(as_uuid=True), nullable=False),
    Column("corrected_value", Numeric, nullable=False),
    Column("reason", String(500), nullable=False),
    Column("corrected_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(
        ["vehicle_id"],
        ["core_audit.vehicles.vehicle_id"],
        name="fk_vehicle_meter_corrections_vehicle",
    ),
    ForeignKeyConstraint(
        ["original_reading_id"],
        ["core_audit.vehicle_meter_readings.reading_id"],
        name="fk_vehicle_meter_corrections_reading",
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=asset",
)


@dataclass(frozen=True, slots=True)
class TransactionalVehicleRepository:
    connection: Connection

    def __post_init__(self) -> None:
        if not isinstance(self.connection, Connection) or not self.connection.in_transaction():
            raise RuntimeError(
                "TransactionalVehicleRepository exige Connection com transação ativa."
            )

    def save(self, vehicle: Vehicle) -> None:
        self.connection.execute(insert(vehicles_table).values(**self._values(vehicle)))
        self._insert_new_readings(vehicle)
        self._insert_new_corrections(vehicle)

    def update(self, vehicle: Vehicle) -> None:
        self.connection.execute(
            update(vehicles_table)
            .where(vehicles_table.c.vehicle_id == vehicle.vehicle_id.value)
            .values(**self._values(vehicle, include_id=False))
        )
        self._insert_new_readings(vehicle)
        self._insert_new_corrections(vehicle)

    def _values(self, vehicle: Vehicle, *, include_id: bool = True) -> dict[str, Any]:
        values: dict[str, Any] = {
            "record_owner_organization_id": vehicle.organization_id.value,
            "model_id": vehicle.model_ref.value,
            "serial_number": vehicle.identifiers.serial_number,
            "chassis": vehicle.identifiers.chassis,
            "fleet_number": vehicle.identifiers.fleet_number,
            "ownership": vehicle.ownership.value,
            "variant_id": vehicle.variant_ref.value if vehicle.variant_ref else None,
            "site_id": vehicle.site_ref.value if vehicle.site_ref else None,
            "current_baseline_id": (
                vehicle.current_baseline_ref.value if vehicle.current_baseline_ref else None
            ),
            "baseline_valid_from": vehicle.baseline_valid_from,
            "lifecycle_state": vehicle.lifecycle_state.value,
            "version": vehicle.version,
            "created_at": vehicle.created_at,
        }
        if include_id:
            values["vehicle_id"] = vehicle.vehicle_id.value
        return values

    def _insert_new_readings(self, vehicle: Vehicle) -> None:
        existing_ids = {
            row.reading_id
            for row in self.connection.execute(
                select(vehicle_meter_readings_table.c.reading_id).where(
                    vehicle_meter_readings_table.c.vehicle_id == vehicle.vehicle_id.value
                )
            )
        }
        for reading in vehicle.meter_readings:
            if reading.reading_id.value in existing_ids:
                continue
            self.connection.execute(
                insert(vehicle_meter_readings_table).values(
                    reading_id=reading.reading_id.value,
                    vehicle_id=vehicle.vehicle_id.value,
                    record_owner_organization_id=vehicle.organization_id.value,
                    kind=reading.kind.value,
                    value=reading.value,
                    observed_at=reading.observed_at,
                    recorded_at=reading.recorded_at,
                    source=reading.source,
                )
            )

    def _insert_new_corrections(self, vehicle: Vehicle) -> None:
        existing_ids = {
            row.correction_id
            for row in self.connection.execute(
                select(vehicle_meter_corrections_table.c.correction_id).where(
                    vehicle_meter_corrections_table.c.vehicle_id == vehicle.vehicle_id.value
                )
            )
        }
        for correction in vehicle.meter_corrections:
            if correction.correction_id.value in existing_ids:
                continue
            self.connection.execute(
                insert(vehicle_meter_corrections_table).values(
                    correction_id=correction.correction_id.value,
                    vehicle_id=vehicle.vehicle_id.value,
                    record_owner_organization_id=vehicle.organization_id.value,
                    original_reading_id=correction.original_reading_id.value,
                    corrected_value=correction.corrected_value,
                    reason=correction.reason,
                    corrected_at=correction.corrected_at,
                )
            )

    def get_by_id(self, vehicle_id: TypedId) -> Vehicle | None:
        row = self.connection.execute(
            select(vehicles_table).where(vehicles_table.c.vehicle_id == vehicle_id.value)
        ).fetchone()
        if row is None:
            return None
        return self._map(row)

    def _map(self, row: Row[Any]) -> Vehicle:
        def _tz(value: Any) -> Any:
            if value is not None and value.tzinfo is None:
                return value.replace(tzinfo=UTC)
            return value

        reading_rows = self.connection.execute(
            select(vehicle_meter_readings_table).where(
                vehicle_meter_readings_table.c.vehicle_id == row.vehicle_id
            )
        ).fetchall()
        readings = tuple(
            MeterReading(
                reading_id=TypedId(
                    entity_type="vehicle_meter_reading", value=reading_row.reading_id
                ),
                kind=MeterKind(reading_row.kind),
                value=reading_row.value,
                observed_at=_tz(reading_row.observed_at),
                recorded_at=_tz(reading_row.recorded_at),
                source=reading_row.source,
            )
            for reading_row in reading_rows
        )
        correction_rows = self.connection.execute(
            select(vehicle_meter_corrections_table).where(
                vehicle_meter_corrections_table.c.vehicle_id == row.vehicle_id
            )
        ).fetchall()
        corrections = tuple(
            MeterCorrection(
                correction_id=TypedId(
                    entity_type="vehicle_meter_correction", value=correction_row.correction_id
                ),
                original_reading_id=TypedId(
                    entity_type="vehicle_meter_reading", value=correction_row.original_reading_id
                ),
                corrected_value=correction_row.corrected_value,
                reason=correction_row.reason,
                corrected_at=_tz(correction_row.corrected_at),
            )
            for correction_row in correction_rows
        )
        return Vehicle(
            vehicle_id=TypedId(entity_type="vehicle", value=row.vehicle_id),
            organization_id=OrganizationId(row.record_owner_organization_id),
            model_ref=TypedId(entity_type="vehicle_model", value=row.model_id),
            identifiers=VehicleIdentifiers(
                serial_number=row.serial_number,
                chassis=row.chassis,
                fleet_number=row.fleet_number,
            ),
            ownership=AssetOwnership(row.ownership),
            variant_ref=(
                TypedId(entity_type="vehicle_variant", value=row.variant_id)
                if row.variant_id is not None
                else None
            ),
            site_ref=(
                TypedId(entity_type="customer_site", value=row.site_id)
                if row.site_id is not None
                else None
            ),
            current_baseline_ref=(
                TypedId(entity_type="configuration_baseline", value=row.current_baseline_id)
                if row.current_baseline_id is not None
                else None
            ),
            baseline_valid_from=_tz(row.baseline_valid_from),
            lifecycle_state=VehicleLifecycleState(row.lifecycle_state),
            meter_readings=readings,
            meter_corrections=corrections,
            version=row.version,
            created_at=_tz(row.created_at),
        )
