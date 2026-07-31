"""Adapter que concede acesso real (Membership/Role) na aprovação de um pedido.

Fronteira deliberada: `EntityTypeRequestService` conhece só o Protocol
`MembershipGrantPort`; quem sabe que a concessão passa pelas tabelas do Core
(`AuthorizationRepository`, `MembershipRepository`) é só este adapter.
"""

from dataclasses import dataclass

from sqlalchemy import Connection

from packages.core_domain import Membership, MembershipRoleAssignment, Role
from packages.core_infrastructure.persistence import AuthorizationRepository, MembershipRepository
from packages.livestock_application.entity_type_request_service import MembershipGrantPort
from packages.shared_kernel import OrganizationId, TypedId


@dataclass(frozen=True, slots=True)
class TransactionalMembershipGrant(MembershipGrantPort):
    connection: Connection

    def role_by_name(self, organization_id: OrganizationId, name: str) -> Role | None:
        return AuthorizationRepository(self.connection).get_role_by_name(organization_id, name)

    def permission_id_by_code(self, code: str) -> TypedId | None:
        return AuthorizationRepository(self.connection).get_permission_id_by_code(code)

    def add_role(self, role: Role) -> None:
        AuthorizationRepository(self.connection).add_role(role)

    def add_membership(self, membership: Membership) -> None:
        MembershipRepository(self.connection).add(membership)

    def assign_role(self, assignment: MembershipRoleAssignment) -> None:
        AuthorizationRepository(self.connection).assign_role(assignment)
