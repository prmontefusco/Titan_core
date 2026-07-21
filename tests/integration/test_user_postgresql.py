import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from packages.core_domain import Organization, User
from packages.core_infrastructure.persistence import (
    OrganizationRepository,
    UserRepository,
    set_local_organization_context,
)
from packages.shared_kernel import OrganizationId

DATABASE_URL = os.environ.get("TITAN_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="TITAN_DATABASE_URL não configurada para teste PostgreSQL.",
)


def test_user_persistence_rejects_duplicates_and_enforces_operator_owner_rls() -> None:
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
                    text(
                        "GRANT SELECT, INSERT ON core_identity.organizations, "
                        f"core_identity.users TO {quoted_role}"
                    )
                )
                connection.execute(text(f"SET LOCAL ROLE {quoted_role}"))

                operator = Organization.create()
                set_local_organization_context(connection, operator.organization_id)
                OrganizationRepository(connection).add(operator)

                repository = UserRepository(connection)
                user = User.create(platform_operator_organization_id=operator.organization_id)
                repository.add(user)
                assert repository.get(user.user_id) == user

                with pytest.raises(IntegrityError):
                    with connection.begin_nested():
                        repository.add(user)

                unknown_owner = OrganizationId.new()
                set_local_organization_context(connection, unknown_owner)
                user_with_unknown_owner = User.create(
                    platform_operator_organization_id=unknown_owner
                )
                with pytest.raises(IntegrityError):
                    with connection.begin_nested():
                        repository.add(user_with_unknown_owner)

                set_local_organization_context(connection, OrganizationId.new())
                assert repository.get(user.user_id) is None

                connection.execute(text("SELECT set_config('titan.organization_id', '', true)"))
                assert repository.get(user.user_id) is None
            finally:
                transaction.rollback()
    finally:
        engine.dispose()
