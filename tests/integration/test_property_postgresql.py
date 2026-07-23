"""Testes de integração PostgreSQL com RLS para RuralProperty (Passo 8.1 - Titan Livestock)."""

import os
from collections.abc import Iterator
from uuid import uuid4

import pytest
from sqlalchemy import Connection, create_engine, text

from packages.livestock_application.property_service import RuralPropertyService
from packages.livestock_infrastructure.persistence.property_repository import (
    TransactionalRuralPropertyRepository,
)
from packages.shared_kernel import OrganizationId


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


def test_rural_property_persistence_and_rls(db_connection: Connection) -> None:
    org_1 = OrganizationId(uuid4())
    org_2 = OrganizationId(uuid4())

    # Cadastra organizações na tabela core_identity.organizations
    db_connection.execute(
        text(
            """
            INSERT INTO core_identity.organizations (organization_id, record_owner_organization_id)
            VALUES
                (:org1, :org1),
                (:org2, :org2)
            """
        ),
        {"org1": org_1.value, "org2": org_2.value},
    )

    # 1. Configura RLS para org_1
    db_connection.execute(
        text("SELECT set_config('titan.organization_id', :org_id, true)"),
        {"org_id": str(org_1.value)},
    )

    repo_1 = TransactionalRuralPropertyRepository(connection=db_connection)
    service_1 = RuralPropertyService(repository=repo_1)

    prop_1 = service_1.register_property(
        organization_id=org_1,
        code="PROP-SP-001",
        name="Fazenda Sol Nascente",
        municipality="Ribeirão Preto",
        state_code="SP",
        registration_number="CAR-SP-9912",
        total_area_hectares=250.0,
    )

    saved_prop = service_1.get_property(prop_1.property_id)
    assert saved_prop is not None
    assert saved_prop.name == "Fazenda Sol Nascente"
    assert saved_prop.code == "PROP-SP-001"

    # 2. RLS Isolation: uma role sem BYPASSRLS em outra Organization
    # não enxerga a propriedade da org_1

    role_name = f"titan_rls_prop_{uuid4().hex[:12]}"
    quoted_role = f'"{role_name}"'
    db_connection.execute(
        text(
            f"CREATE ROLE {quoted_role} "
            "NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS"
        )
    )
    db_connection.execute(text(f"GRANT USAGE ON SCHEMA core_audit TO {quoted_role}"))
    db_connection.execute(text(f"GRANT ALL ON core_audit.rural_properties TO {quoted_role}"))
    db_connection.execute(text(f"SET LOCAL ROLE {quoted_role}"))

    db_connection.execute(
        text("SELECT set_config('titan.organization_id', :org_id, true)"),
        {"org_id": str(org_2.value)},
    )

    repo_2 = TransactionalRuralPropertyRepository(connection=db_connection)
    service_2 = RuralPropertyService(repository=repo_2)

    # RLS deve impedir a org_2 de enxergar a propriedade da org_1
    assert service_2.get_property(prop_1.property_id) is None
    assert service_2.get_by_code(org_1, "PROP-SP-001") is None
    assert len(service_2.list_properties(org_1)) == 0

    # org_2 cadastra sua própria propriedade com o mesmo código local
    prop_2 = service_2.register_property(
        organization_id=org_2,
        code="PROP-SP-001",
        name="Fazenda Vale Verde (Org 2)",
        municipality="Campinas",
        state_code="SP",
    )
    assert prop_2.property_id != prop_1.property_id
    assert service_2.get_property(prop_2.property_id) is not None

    db_connection.execute(text("RESET ROLE"))
    db_connection.execute(text(f"DROP OWNED BY {quoted_role}"))
    db_connection.execute(text(f"DROP ROLE {quoted_role}"))
