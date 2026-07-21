import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from packages.core_domain import (
    Membership,
    MembershipRoleAssignment,
    MembershipRoleRevocation,
    Organization,
    Permission,
    Role,
    User,
)
from packages.core_infrastructure.persistence import (
    AuthorizationRepository,
    MembershipRepository,
    OrganizationRepository,
    UserRepository,
    set_local_organization_context,
)
from packages.shared_kernel import TypedId

DATABASE_URL = os.environ.get("TITAN_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="TITAN_DATABASE_URL não configurada para teste PostgreSQL."
)


def test_role_grant_and_revocation_change_effective_permissions_without_direct_user_link() -> None:
    assert DATABASE_URL is not None
    engine = create_engine(DATABASE_URL)
    role_name = f"titan_test_runtime_{uuid4().hex}"
    quoted_role = engine.dialect.identifier_preparer.quote(role_name)
    granted_at = datetime(2026, 7, 21, 12, tzinfo=UTC)
    revoked_at = granted_at + timedelta(hours=1)

    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                connection.execute(
                    text(
                        f"CREATE ROLE {quoted_role} NOLOGIN NOSUPERUSER NOCREATEDB "
                        "NOCREATEROLE NOINHERIT NOBYPASSRLS"
                    )
                )
                connection.execute(text(f"GRANT USAGE ON SCHEMA core_identity TO {quoted_role}"))
                connection.execute(
                    text(
                        "GRANT SELECT, INSERT ON core_identity.organizations, core_identity.users, "
                        "core_identity.memberships, core_identity.roles, "
                        "core_identity.role_permissions, "
                        "core_identity.membership_role_assignments, "
                        f"core_identity.membership_role_revocations TO {quoted_role}"
                    )
                )
                connection.execute(
                    text(f"GRANT SELECT ON core_identity.permissions TO {quoted_role}")
                )
                connection.execute(text(f"SET LOCAL ROLE {quoted_role}"))

                operator = Organization.create()
                organization = Organization.create()
                for item in (operator, organization):
                    set_local_organization_context(connection, item.organization_id)
                    OrganizationRepository(connection).add(item)

                connection.execute(text("RESET ROLE"))
                permission = Permission.create(
                    operator_organization_id=operator.organization_id,
                    code="DOSSIER.LER",
                )
                AuthorizationRepository(connection).add_permission(permission)
                connection.execute(text(f"SET LOCAL ROLE {quoted_role}"))

                set_local_organization_context(connection, operator.organization_id)
                user = User.create(platform_operator_organization_id=operator.organization_id)
                UserRepository(connection).add(user)

                set_local_organization_context(connection, organization.organization_id)
                membership = Membership.create(
                    user_id=user.user_id,
                    organization_id=organization.organization_id,
                    valid_from=granted_at - timedelta(days=1),
                    valid_until=None,
                    origin_reference=TypedId.new("membership_invitation"),
                    granted_by_actor_id=TypedId.new("actor"),
                )
                MembershipRepository(connection).add(membership)
                role = Role.create(
                    organization_id=organization.organization_id,
                    name="Revisor",
                    permission_ids=(permission.permission_id,),
                )
                repository = AuthorizationRepository(connection)
                repository.add_role(role)
                assignment = MembershipRoleAssignment.create(
                    membership_id=membership.membership_id,
                    role_id=role.role_id,
                    organization_id=organization.organization_id,
                    valid_from=granted_at,
                    valid_until=None,
                    granted_by_actor_id=TypedId.new("actor"),
                )
                repository.assign_role(assignment)
                assert repository.effective_permission_codes(
                    membership.membership_id, granted_at
                ) == {"DOSSIER.LER"}

                revocation = MembershipRoleRevocation.create(
                    assignment_id=assignment.assignment_id,
                    organization_id=organization.organization_id,
                    revoked_at=revoked_at,
                    revoked_by_actor_id=TypedId.new("actor"),
                )
                repository.revoke_role(revocation)
                assert repository.effective_permission_codes(
                    membership.membership_id, revoked_at - timedelta(seconds=1)
                ) == {"DOSSIER.LER"}
                assert (
                    repository.effective_permission_codes(membership.membership_id, revoked_at)
                    == set()
                )

                other_organization = Organization.create()
                set_local_organization_context(connection, other_organization.organization_id)
                OrganizationRepository(connection).add(other_organization)
                invalid_assignment = MembershipRoleAssignment.create(
                    membership_id=membership.membership_id,
                    role_id=role.role_id,
                    organization_id=other_organization.organization_id,
                    valid_from=granted_at,
                    valid_until=None,
                    granted_by_actor_id=TypedId.new("actor"),
                )
                with pytest.raises(IntegrityError):
                    with connection.begin_nested():
                        AuthorizationRepository(connection).assign_role(invalid_assignment)
            finally:
                transaction.rollback()
    finally:
        engine.dispose()
