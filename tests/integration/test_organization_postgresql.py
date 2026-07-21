import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text

from packages.core_domain import Organization
from packages.core_infrastructure.persistence import (
    OrganizationRepository,
    set_local_organization_context,
)

DATABASE_URL = os.environ.get("TITAN_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="TITAN_DATABASE_URL não configurada para teste PostgreSQL.",
)


def test_rls_isolates_organization_creation_and_query() -> None:
    assert DATABASE_URL is not None
    engine = create_engine(DATABASE_URL)
    role_name = f"titan_test_runtime_{uuid4().hex}"
    quoted_role = engine.dialect.identifier_preparer.quote(role_name)

    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                connection.execute(
                    text(
                        f"CREATE ROLE {quoted_role} "
                        "NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS"
                    )
                )
                connection.execute(text(f"GRANT USAGE ON SCHEMA core_identity TO {quoted_role}"))
                connection.execute(
                    text(f"GRANT SELECT, INSERT ON core_identity.organizations TO {quoted_role}")
                )
                connection.execute(text(f"SET LOCAL ROLE {quoted_role}"))
                repository = OrganizationRepository(connection)
                first = Organization.create()
                second = Organization.create()

                set_local_organization_context(connection, first.organization_id)
                repository.add(first)
                set_local_organization_context(connection, second.organization_id)
                repository.add(second)

                set_local_organization_context(connection, first.organization_id)
                assert repository.get(first.organization_id) == first
                assert repository.get(second.organization_id) is None

                connection.execute(text("SELECT set_config('titan.organization_id', '', true)"))
                assert repository.get(first.organization_id) is None
            finally:
                transaction.rollback()
    finally:
        engine.dispose()
