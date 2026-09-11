"""Teste de integração PostgreSQL com RLS para `CustomerSite` (A3, Titan Asset)."""

import os
from collections.abc import Iterator
from uuid import uuid4

import pytest
from sqlalchemy import Connection, create_engine, text

from packages.asset_domain.customer_site import CustomerSite, CustomerSiteKind, SiteContact
from packages.asset_infrastructure.persistence.customer_site_repository import (
    TransactionalCustomerSiteRepository,
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


def test_customer_site_persistence_and_rls(db_connection: Connection) -> None:
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

    repo_1 = TransactionalCustomerSiteRepository(connection=db_connection)
    site = CustomerSite(
        site_id=TypedId.new("customer_site"),
        organization_id=org_1,
        customer_ref=TypedId.new("customer"),
        code="OM-001",
        display_name="Oficina Matriz",
        kind=CustomerSiteKind.OM,
        contacts=(SiteContact(name="Maria Souza", role="Gerente", email="maria@example.com"),),
    )
    repo_1.save(site)

    saved = repo_1.get_by_id(site.site_id)
    assert saved is not None
    assert saved.code == "OM-001"
    assert saved.display_name == "Oficina Matriz"
    assert saved.kind is CustomerSiteKind.OM
    assert len(saved.contacts) == 1
    assert saved.contacts[0].name == "Maria Souza"
    assert saved.contacts[0].email == "maria@example.com"

    updated_site = site.__class__(
        site_id=site.site_id,
        organization_id=site.organization_id,
        customer_ref=site.customer_ref,
        code=site.code,
        display_name="Oficina Matriz Renomeada",
        kind=site.kind,
        contacts=(
            SiteContact(name="Maria Souza", role="Gerente"),
            SiteContact(name="João Lima", role="Técnico", phone="+55 11 90000-0000"),
        ),
        version=site.version + 1,
    )
    repo_1.update(updated_site)

    reloaded = repo_1.get_by_id(site.site_id)
    assert reloaded is not None
    assert reloaded.display_name == "Oficina Matriz Renomeada"
    assert reloaded.version == 2
    assert [contact.name for contact in reloaded.contacts] == ["Maria Souza", "João Lima"]

    # RLS: role sem BYPASSRLS em outra Organization não enxerga o site da org_1.
    role_name = f"titan_rls_site_{uuid4().hex[:12]}"
    quoted_role = f'"{role_name}"'
    db_connection.execute(
        text(
            f"CREATE ROLE {quoted_role} "
            "NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS"
        )
    )
    db_connection.execute(text(f"GRANT USAGE ON SCHEMA core_audit TO {quoted_role}"))
    db_connection.execute(text(f"GRANT ALL ON core_audit.customer_sites TO {quoted_role}"))
    db_connection.execute(text(f"GRANT ALL ON core_audit.customer_site_contacts TO {quoted_role}"))
    db_connection.execute(text(f"SET LOCAL ROLE {quoted_role}"))

    db_connection.execute(
        text("SELECT set_config('titan.organization_id', :org_id, true)"),
        {"org_id": str(org_2.value)},
    )

    repo_2 = TransactionalCustomerSiteRepository(connection=db_connection)
    assert repo_2.get_by_id(site.site_id) is None

    db_connection.execute(text("RESET ROLE"))
    db_connection.execute(text(f"DROP OWNED BY {quoted_role}"))
    db_connection.execute(text(f"DROP ROLE {quoted_role}"))
