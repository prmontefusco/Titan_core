"""Teste de integração PostgreSQL com RLS para `StockLocation` (A3, Titan Asset)."""

import os
from collections.abc import Iterator
from uuid import uuid4

import pytest
from sqlalchemy import Connection, create_engine, text

from packages.asset_domain.customer_site import CustomerSite, CustomerSiteKind
from packages.asset_domain.inventory import StockLocation, StockLocationKind
from packages.asset_infrastructure.persistence.customer_site_repository import (
    TransactionalCustomerSiteRepository,
)
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


def test_stock_location_persistence_rls_and_site_fk(db_connection: Connection) -> None:
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

    site_repo = TransactionalCustomerSiteRepository(connection=db_connection)
    site = CustomerSite(
        site_id=TypedId.new("customer_site"),
        organization_id=org_1,
        customer_ref=TypedId.new("customer"),
        code="OM-002",
        display_name="Oficina Regional",
        kind=CustomerSiteKind.OM,
    )
    site_repo.save(site)

    location_repo = TransactionalStockLocationRepository(connection=db_connection)
    location = StockLocation(
        location_id=TypedId.new("stock_location"),
        organization_id=org_1,
        kind=StockLocationKind.WORKSHOP,
        code="WH-001",
        display_name="Almoxarifado Oficina Regional",
        site_ref=site.site_id,
    )
    location_repo.save(location)

    saved = location_repo.get_by_id(location.location_id)
    assert saved is not None
    assert saved.code == "WH-001"
    assert saved.kind is StockLocationKind.WORKSHOP
    assert saved.site_ref == site.site_id

    updated_location = StockLocation(
        location_id=location.location_id,
        organization_id=location.organization_id,
        kind=StockLocationKind.CENTRAL_WAREHOUSE,
        code=location.code,
        display_name="Almoxarifado Central",
        site_ref=None,
    )
    location_repo.update(updated_location)
    reloaded = location_repo.get_by_id(location.location_id)
    assert reloaded is not None
    assert reloaded.kind is StockLocationKind.CENTRAL_WAREHOUSE
    assert reloaded.display_name == "Almoxarifado Central"
    assert reloaded.site_ref is None

    role_name = f"titan_rls_loc_{uuid4().hex[:12]}"
    quoted_role = f'"{role_name}"'
    db_connection.execute(
        text(
            f"CREATE ROLE {quoted_role} "
            "NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS"
        )
    )
    db_connection.execute(text(f"GRANT USAGE ON SCHEMA core_audit TO {quoted_role}"))
    db_connection.execute(text(f"GRANT ALL ON core_audit.stock_locations TO {quoted_role}"))
    db_connection.execute(text(f"SET LOCAL ROLE {quoted_role}"))

    db_connection.execute(
        text("SELECT set_config('titan.organization_id', :org_id, true)"),
        {"org_id": str(org_2.value)},
    )

    location_repo_2 = TransactionalStockLocationRepository(connection=db_connection)
    assert location_repo_2.get_by_id(location.location_id) is None

    db_connection.execute(text("RESET ROLE"))
    db_connection.execute(text(f"DROP OWNED BY {quoted_role}"))
    db_connection.execute(text(f"DROP ROLE {quoted_role}"))
