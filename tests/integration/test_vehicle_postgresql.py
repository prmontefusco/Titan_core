"""Teste de integração PostgreSQL com RLS para `Vehicle` (A3, Titan Asset)."""

import os
from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import Connection, create_engine, text

from packages.asset_domain.vehicle import (
    AssetOwnership,
    MeterCorrection,
    MeterKind,
    MeterReading,
    Vehicle,
    VehicleIdentifiers,
    VehicleLifecycleState,
)
from packages.asset_infrastructure.persistence.vehicle_repository import (
    TransactionalVehicleRepository,
)
from packages.shared_kernel import OrganizationId, TypedId


@pytest.fixture
def db_connection() -> Iterator[Connection]:
    db_url = os.getenv(
        "TITAN_DATABASE_URL",
        "postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan",
    )
    engine = create_engine(db_url, pool_pre_ping=True)
    with engine.connect() as conn:
        with conn.begin():
            yield conn


def test_vehicle_persistence_meter_history_and_rls(db_connection: Connection) -> None:
    org_1 = OrganizationId(uuid4())
    org_2 = OrganizationId(uuid4())
    db_connection.execute(
        text(
            "INSERT INTO core_identity.organizations "
            "(organization_id, record_owner_organization_id) VALUES (:org1, :org1), (:org2, :org2)"
        ),
        {"org1": org_1.value, "org2": org_2.value},
    )
    db_connection.execute(
        text("SELECT set_config('titan.organization_id', :org_id, true)"),
        {"org_id": str(org_1.value)},
    )

    repo = TransactionalVehicleRepository(connection=db_connection)
    vehicle = Vehicle(
        vehicle_id=TypedId.new("vehicle"),
        organization_id=org_1,
        model_ref=TypedId.new("vehicle_model"),
        identifiers=VehicleIdentifiers(serial_number="SN-001", fleet_number="F-01"),
        ownership=AssetOwnership.COMPANY,
    )
    repo.save(vehicle)

    saved = repo.get_by_id(vehicle.vehicle_id)
    assert saved is not None
    assert saved.identifiers.serial_number == "SN-001"
    assert saved.lifecycle_state is VehicleLifecycleState.AVAILABLE
    assert saved.meter_readings == ()

    reading = MeterReading(
        reading_id=TypedId.new("vehicle_meter_reading"),
        kind=MeterKind.HOURS,
        value=Decimal("120.5"),
        observed_at=datetime(2026, 1, 1, tzinfo=UTC),
        recorded_at=datetime(2026, 1, 1, 12, tzinfo=UTC),
        source="manual",
    )
    with_reading = saved.record_meter_reading(reading)
    repo.update(with_reading)

    reloaded = repo.get_by_id(vehicle.vehicle_id)
    assert reloaded is not None
    assert len(reloaded.meter_readings) == 1
    assert reloaded.meter_readings[0].value == Decimal("120.5")

    correction = MeterCorrection(
        correction_id=TypedId.new("vehicle_meter_correction"),
        original_reading_id=reading.reading_id,
        corrected_value=Decimal("125.0"),
        reason="Leitura original registrada com erro de digitação.",
        corrected_at=datetime(2026, 1, 2, tzinfo=UTC),
    )
    with_correction = reloaded.correct_meter_reading(correction)
    repo.update(with_correction)

    reloaded_again = repo.get_by_id(vehicle.vehicle_id)
    assert reloaded_again is not None
    # I-VEH-2: a leitura original permanece, a correção é aditiva.
    assert len(reloaded_again.meter_readings) == 1
    assert reloaded_again.meter_readings[0].value == Decimal("120.5")
    assert len(reloaded_again.meter_corrections) == 1
    assert reloaded_again.meter_corrections[0].corrected_value == Decimal("125.0")

    role_name = f"titan_rls_veh_{uuid4().hex[:12]}"
    quoted_role = f'"{role_name}"'
    db_connection.execute(
        text(
            f"CREATE ROLE {quoted_role} "
            "NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS"
        )
    )
    db_connection.execute(text(f"GRANT USAGE ON SCHEMA core_audit TO {quoted_role}"))
    for table in ("vehicles", "vehicle_meter_readings", "vehicle_meter_corrections"):
        db_connection.execute(text(f"GRANT ALL ON core_audit.{table} TO {quoted_role}"))
    db_connection.execute(text(f"SET LOCAL ROLE {quoted_role}"))
    db_connection.execute(
        text("SELECT set_config('titan.organization_id', :org_id, true)"),
        {"org_id": str(org_2.value)},
    )
    repo_2 = TransactionalVehicleRepository(connection=db_connection)
    assert repo_2.get_by_id(vehicle.vehicle_id) is None
    db_connection.execute(text("RESET ROLE"))
    db_connection.execute(text(f"DROP OWNED BY {quoted_role}"))
    db_connection.execute(text(f"DROP ROLE {quoted_role}"))
