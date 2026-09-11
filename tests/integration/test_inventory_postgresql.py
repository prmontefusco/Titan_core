"""Teste de integração PostgreSQL com RLS para `StockPosition`/`StockReservation`/
`StockTransfer` (A3, Titan Asset)."""

import os
from collections.abc import Iterator
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import Connection, create_engine, text

from packages.asset_domain.inventory import (
    DemandKind,
    DemandRef,
    ReservationState,
    StockLocation,
    StockLocationKind,
    StockOwnership,
    StockPosition,
    StockPurpose,
    StockQuantities,
    StockReservation,
    StockReservationLine,
    StockTransfer,
    TransferState,
)
from packages.asset_domain.part import Part, PartIdentity, PartRevision
from packages.asset_infrastructure.persistence.inventory_repository import (
    TransactionalStockPositionRepository,
    TransactionalStockReservationRepository,
    TransactionalStockTransferRepository,
)
from packages.asset_infrastructure.persistence.part_repository import TransactionalPartRepository
from packages.asset_infrastructure.persistence.stock_location_repository import (
    TransactionalStockLocationRepository,
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


def _setup_part_and_locations(
    db_connection: Connection, org: OrganizationId
) -> tuple[TypedId, TypedId, TypedId]:
    revision = PartRevision(revision_id=TypedId.new("part_revision"), revision_code="A")
    part = Part(
        part_id=TypedId.new("part"),
        organization_id=org,
        identity=PartIdentity(
            part_number="PN-500", description="Filtro de óleo", manufacturer="Acme"
        ),
        revisions=(revision,),
    )
    TransactionalPartRepository(connection=db_connection).save(part)

    location_repo = TransactionalStockLocationRepository(connection=db_connection)
    from_location = StockLocation(
        location_id=TypedId.new("stock_location"),
        organization_id=org,
        kind=StockLocationKind.CENTRAL_WAREHOUSE,
        code="WH-CENTRAL",
        display_name="Central",
    )
    to_location = StockLocation(
        location_id=TypedId.new("stock_location"),
        organization_id=org,
        kind=StockLocationKind.WORKSHOP,
        code="WH-OFICINA",
        display_name="Oficina",
    )
    location_repo.save(from_location)
    location_repo.save(to_location)
    return part.part_id, from_location.location_id, to_location.location_id


def test_stock_position_hold_release_and_rls(db_connection: Connection) -> None:
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
    part_id, location_id, _ = _setup_part_and_locations(db_connection, org_1)

    position_repo = TransactionalStockPositionRepository(connection=db_connection)
    position = StockPosition(
        stock_position_id=TypedId.new("stock_position"),
        organization_id=org_1,
        part_ref=part_id,
        location_ref=location_id,
        purpose=StockPurpose.SERVICE_SLI,
        ownership=StockOwnership.COMPANY_OWNED,
        quantities=StockQuantities(on_hand=Decimal(10)),
    )
    position_repo.save(position)

    saved = position_repo.get_by_id(position.stock_position_id)
    assert saved is not None
    assert saved.available == Decimal(10)

    line = StockReservationLine(
        reservation_id=TypedId.new("stock_reservation"),
        demand_ref=TypedId.new("work_order"),
        qty=Decimal(4),
        priority=1,
        purpose_lock=StockPurpose.SERVICE_SLI,
    )
    held = saved.hold(line)
    position_repo.update(held)

    reloaded = position_repo.get_by_id(position.stock_position_id)
    assert reloaded is not None
    assert reloaded.available == Decimal(6)
    assert len(reloaded.reservations) == 1
    assert reloaded.reservations[0].demand_ref == line.demand_ref

    released = reloaded.release(line.reservation_id)
    position_repo.update(released)
    reloaded_again = position_repo.get_by_id(position.stock_position_id)
    assert reloaded_again is not None
    assert reloaded_again.available == Decimal(10)
    assert reloaded_again.reservations == ()

    role_name = f"titan_rls_pos_{uuid4().hex[:12]}"
    quoted_role = f'"{role_name}"'
    db_connection.execute(
        text(
            f"CREATE ROLE {quoted_role} "
            "NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS"
        )
    )
    db_connection.execute(text(f"GRANT USAGE ON SCHEMA core_audit TO {quoted_role}"))
    for table in ("stock_positions", "stock_position_reservations"):
        db_connection.execute(text(f"GRANT ALL ON core_audit.{table} TO {quoted_role}"))
    db_connection.execute(text(f"SET LOCAL ROLE {quoted_role}"))
    db_connection.execute(
        text("SELECT set_config('titan.organization_id', :org_id, true)"),
        {"org_id": str(org_2.value)},
    )
    position_repo_2 = TransactionalStockPositionRepository(connection=db_connection)
    assert position_repo_2.get_by_id(position.stock_position_id) is None
    db_connection.execute(text("RESET ROLE"))
    db_connection.execute(text(f"DROP OWNED BY {quoted_role}"))
    db_connection.execute(text(f"DROP ROLE {quoted_role}"))


def test_stock_reservation_persistence_and_state_machine(db_connection: Connection) -> None:
    org = OrganizationId(uuid4())
    db_connection.execute(
        text(
            "INSERT INTO core_identity.organizations "
            "(organization_id, record_owner_organization_id) VALUES (:org, :org)"
        ),
        {"org": org.value},
    )
    db_connection.execute(
        text("SELECT set_config('titan.organization_id', :org_id, true)"),
        {"org_id": str(org.value)},
    )
    part_id, location_id, _ = _setup_part_and_locations(db_connection, org)

    position_repo = TransactionalStockPositionRepository(connection=db_connection)
    position = StockPosition(
        stock_position_id=TypedId.new("stock_position"),
        organization_id=org,
        part_ref=part_id,
        location_ref=location_id,
        purpose=StockPurpose.SERVICE_SLI,
        ownership=StockOwnership.COMPANY_OWNED,
        quantities=StockQuantities(on_hand=Decimal(10)),
    )
    position_repo.save(position)

    reservation_repo = TransactionalStockReservationRepository(connection=db_connection)
    reservation = StockReservation(
        reservation_id=TypedId.new("stock_reservation"),
        organization_id=org,
        stock_position_ref=position.stock_position_id,
        demand=DemandRef(kind=DemandKind.WORK_ORDER, ref=TypedId.new("work_order")),
        qty=Decimal(3),
        purpose=StockPurpose.SERVICE_SLI,
        priority=2,
    )
    reservation_repo.save(reservation)

    saved = reservation_repo.get_by_id(reservation.reservation_id)
    assert saved is not None
    assert saved.state is ReservationState.HELD
    assert saved.demand.kind is DemandKind.WORK_ORDER

    allocated = saved.allocate()
    reservation_repo.update(allocated)
    consumed = reservation_repo.get_by_id(reservation.reservation_id)
    assert consumed is not None
    assert consumed.state is ReservationState.ALLOCATED
    final = consumed.consume()
    reservation_repo.update(final)
    reloaded = reservation_repo.get_by_id(reservation.reservation_id)
    assert reloaded is not None
    assert reloaded.state is ReservationState.CONSUMED


def test_stock_transfer_dispatch_and_partial_receive(db_connection: Connection) -> None:
    org = OrganizationId(uuid4())
    db_connection.execute(
        text(
            "INSERT INTO core_identity.organizations "
            "(organization_id, record_owner_organization_id) VALUES (:org, :org)"
        ),
        {"org": org.value},
    )
    db_connection.execute(
        text("SELECT set_config('titan.organization_id', :org_id, true)"),
        {"org_id": str(org.value)},
    )
    part_id, from_location_id, to_location_id = _setup_part_and_locations(db_connection, org)

    transfer_repo = TransactionalStockTransferRepository(connection=db_connection)
    transfer = StockTransfer(
        transfer_id=TypedId.new("stock_transfer"),
        organization_id=org,
        part_ref=part_id,
        from_location_ref=from_location_id,
        to_location_ref=to_location_id,
        qty=Decimal(10),
    )
    transfer_repo.save(transfer)

    dispatched = transfer.dispatch()
    transfer_repo.update(dispatched)
    reloaded = transfer_repo.get_by_id(transfer.transfer_id)
    assert reloaded is not None
    assert reloaded.state is TransferState.IN_TRANSIT

    partially_received = reloaded.receive(Decimal(6))
    transfer_repo.update(partially_received)
    reloaded_partial = transfer_repo.get_by_id(transfer.transfer_id)
    assert reloaded_partial is not None
    assert reloaded_partial.state is TransferState.PARTIALLY_RECEIVED
    assert reloaded_partial.qty_received == Decimal(6)

    fully_received = reloaded_partial.receive(Decimal(4))
    transfer_repo.update(fully_received)
    reloaded_final = transfer_repo.get_by_id(transfer.transfer_id)
    assert reloaded_final is not None
    assert reloaded_final.state is TransferState.RECEIVED
    assert reloaded_final.qty_received == Decimal(10)
