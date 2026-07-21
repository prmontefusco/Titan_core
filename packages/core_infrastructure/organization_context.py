"""Adapter PostgreSQL para construção de OrganizationContext."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Connection

from packages.core_application import IdentityAndAccessReader
from packages.core_domain import AuthenticatedPrincipal, ExternalIdentity, Membership
from packages.core_infrastructure.persistence import (
    AuthorizationRepository,
    ExternalIdentityRepository,
    MembershipRepository,
    set_local_organization_context,
)
from packages.shared_kernel import OrganizationId, TypedId


@dataclass(frozen=True, slots=True)
class PostgresqlIdentityAndAccessReader(IdentityAndAccessReader):
    connection: Connection
    operator_organization_id: OrganizationId

    def __post_init__(self) -> None:
        if not self.connection.in_transaction():
            raise RuntimeError("O reader exige transação ativa.")

    def resolve_external_identity(
        self, principal: AuthenticatedPrincipal
    ) -> ExternalIdentity | None:
        set_local_organization_context(self.connection, self.operator_organization_id)
        return ExternalIdentityRepository(self.connection).resolve(principal)

    def valid_memberships(
        self, user_id: TypedId, organization_id: OrganizationId, instant: datetime
    ) -> tuple[Membership, ...]:
        set_local_organization_context(self.connection, organization_id)
        return MembershipRepository(self.connection).list_valid_for_user(user_id, instant)

    def effective_roles_and_permissions(
        self, membership_id: TypedId, instant: datetime
    ) -> tuple[tuple[TypedId, ...], frozenset[str]]:
        repository = AuthorizationRepository(self.connection)
        return (
            repository.effective_role_ids(membership_id, instant),
            repository.effective_permission_codes(membership_id, instant),
        )
