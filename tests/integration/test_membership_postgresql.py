import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from packages.core_domain import Membership, Organization, User
from packages.core_infrastructure.persistence import (
    MembershipRepository,
    OrganizationRepository,
    UserRepository,
    set_local_organization_context,
)
from packages.shared_kernel import OrganizationId, TypedId

DATABASE_URL = os.environ.get("TITAN_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="TITAN_DATABASE_URL não configurada para teste PostgreSQL.",
)


def test_user_can_have_isolated_temporal_memberships_in_two_organizations() -> None:
    assert DATABASE_URL is not None
    engine = create_engine(DATABASE_URL)
    role_name = f"titan_test_runtime_{uuid4().hex}"
    quoted_role = engine.dialect.identifier_preparer.quote(role_name)
    instant = datetime(2026, 7, 21, 12, tzinfo=UTC)

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
                        "core_identity.users, core_identity.memberships "
                        f"TO {quoted_role}"
                    )
                )
                connection.execute(text(f"SET LOCAL ROLE {quoted_role}"))

                operator = Organization.create()
                first_organization = Organization.create()
                second_organization = Organization.create()
                for organization in (operator, first_organization, second_organization):
                    set_local_organization_context(connection, organization.organization_id)
                    OrganizationRepository(connection).add(organization)

                set_local_organization_context(connection, operator.organization_id)
                user = User.create(platform_operator_organization_id=operator.organization_id)
                UserRepository(connection).add(user)

                memberships: list[Membership] = []
                for organization in (first_organization, second_organization):
                    membership = Membership.create(
                        user_id=user.user_id,
                        organization_id=organization.organization_id,
                        valid_from=instant - timedelta(days=1),
                        valid_until=instant + timedelta(days=1),
                        origin_reference=TypedId.new("membership_invitation"),
                        granted_by_actor_id=TypedId.new("actor"),
                    )
                    set_local_organization_context(connection, organization.organization_id)
                    repository = MembershipRepository(connection)
                    repository.add(membership)
                    assert repository.get(membership.membership_id) == membership
                    assert repository.list_valid_for_user(user.user_id, instant) == (membership,)
                    memberships.append(membership)

                set_local_organization_context(connection, first_organization.organization_id)
                repository = MembershipRepository(connection)
                assert repository.get(memberships[1].membership_id) is None

                with pytest.raises(IntegrityError):
                    with connection.begin_nested():
                        repository.add(memberships[0])

                unknown_organization = OrganizationId.new()
                set_local_organization_context(connection, unknown_organization)
                invalid_membership = Membership.create(
                    user_id=user.user_id,
                    organization_id=unknown_organization,
                    valid_from=instant,
                    valid_until=None,
                    origin_reference=TypedId.new("membership_invitation"),
                    granted_by_actor_id=TypedId.new("actor"),
                )
                with pytest.raises(IntegrityError):
                    with connection.begin_nested():
                        MembershipRepository(connection).add(invalid_membership)

                connection.execute(text("SELECT set_config('titan.organization_id', '', true)"))
                assert (
                    MembershipRepository(connection).list_valid_for_user(user.user_id, instant)
                    == ()
                )
            finally:
                transaction.rollback()
    finally:
        engine.dispose()
