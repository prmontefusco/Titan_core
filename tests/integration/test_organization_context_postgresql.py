import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text

from packages.core_application import OrganizationContextDenied, OrganizationContextService
from packages.core_domain import (
    AuthenticatedPrincipal,
    ExternalIdentity,
    Membership,
    MembershipRoleAssignment,
    Organization,
    Permission,
    PrincipalType,
    Role,
    User,
)
from packages.core_infrastructure.organization_context import (
    PostgresqlIdentityAndAccessReader,
)
from packages.core_infrastructure.persistence import (
    AuthorizationRepository,
    ExternalIdentityRepository,
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


def test_postgresql_builds_context_and_denies_unlinked_organization() -> None:
    assert DATABASE_URL is not None
    engine = create_engine(DATABASE_URL)
    role_name = f"titan_test_runtime_{uuid4().hex}"
    quoted_role = engine.dialect.identifier_preparer.quote(role_name)
    now = datetime(2026, 7, 21, 12, tzinfo=UTC)

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
                protected_tables = (
                    "organizations, users, memberships, roles, role_permissions, "
                    "membership_role_assignments, membership_role_revocations, "
                    "external_identities"
                )
                grant_targets = protected_tables.replace(", ", ", core_identity.")
                connection.execute(
                    text(f"GRANT SELECT, INSERT ON core_identity.{grant_targets} TO {quoted_role}")
                )
                connection.execute(
                    text(f"GRANT SELECT ON core_identity.permissions TO {quoted_role}")
                )
                connection.execute(text(f"SET LOCAL ROLE {quoted_role}"))

                operator = Organization.create()
                allowed = Organization.create()
                denied = Organization.create()
                for organization in (operator, allowed, denied):
                    set_local_organization_context(connection, organization.organization_id)
                    OrganizationRepository(connection).add(organization)

                connection.execute(text("RESET ROLE"))
                permission = Permission.create(
                    operator_organization_id=operator.organization_id,
                    code="CONTEXTO.USAR",
                )
                AuthorizationRepository(connection).add_permission(permission)
                connection.execute(text(f"SET LOCAL ROLE {quoted_role}"))

                set_local_organization_context(connection, operator.organization_id)
                user = User.create(platform_operator_organization_id=operator.organization_id)
                UserRepository(connection).add(user)
                principal = AuthenticatedPrincipal(
                    issuer="https://issuer.example/realms/titan",
                    subject="subject-1",
                    principal_type=PrincipalType.USER,
                    authenticated_at=now,
                    client_id="titan-swagger",
                    technical_scopes=frozenset({"openid"}),
                )
                identity = ExternalIdentity.link_user(
                    operator_organization_id=operator.organization_id,
                    issuer=principal.issuer,
                    subject=principal.subject,
                    user_id=user.user_id,
                    linked_at=now,
                    linked_by_actor_id=TypedId.new("actor"),
                )
                ExternalIdentityRepository(connection).add(identity)

                set_local_organization_context(connection, allowed.organization_id)
                membership = Membership.create(
                    user_id=user.user_id,
                    organization_id=allowed.organization_id,
                    valid_from=now - timedelta(days=1),
                    valid_until=None,
                    origin_reference=TypedId.new("membership_invitation"),
                    granted_by_actor_id=TypedId.new("actor"),
                )
                MembershipRepository(connection).add(membership)
                role = Role.create(
                    organization_id=allowed.organization_id,
                    name="Operador",
                    permission_ids=(permission.permission_id,),
                )
                authorization = AuthorizationRepository(connection)
                authorization.add_role(role)
                authorization.assign_role(
                    MembershipRoleAssignment.create(
                        membership_id=membership.membership_id,
                        role_id=role.role_id,
                        organization_id=allowed.organization_id,
                        valid_from=now,
                        valid_until=None,
                        granted_by_actor_id=TypedId.new("actor"),
                    )
                )

                service = OrganizationContextService(
                    PostgresqlIdentityAndAccessReader(connection, operator.organization_id)
                )
                context = service.build(
                    principal=principal,
                    requested_organization_id=allowed.organization_id,
                    instant=now,
                )
                assert context.organization_id == allowed.organization_id
                assert context.permission_codes == {"CONTEXTO.USAR"}

                with pytest.raises(OrganizationContextDenied):
                    service.build(
                        principal=principal,
                        requested_organization_id=denied.organization_id,
                        instant=now,
                    )
                unknown_principal = AuthenticatedPrincipal(
                    issuer=principal.issuer,
                    subject="unknown-subject",
                    principal_type=PrincipalType.USER,
                    authenticated_at=now,
                    client_id=None,
                    technical_scopes=frozenset(),
                )
                with pytest.raises(OrganizationContextDenied):
                    service.build(
                        principal=unknown_principal,
                        requested_organization_id=allowed.organization_id,
                        instant=now,
                    )
            finally:
                transaction.rollback()
    finally:
        engine.dispose()
