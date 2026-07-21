"""Contratos e invariantes universais do domínio Titan."""

from packages.core_domain.authentication import AuthenticatedPrincipal, PrincipalType
from packages.core_domain.authorization import (
    MembershipRoleAssignment,
    MembershipRoleRevocation,
    Permission,
    Role,
)
from packages.core_domain.corrections import ChangeKind, Correction, build_correction
from packages.core_domain.events import CanonicalPayload, DomainEvent
from packages.core_domain.memberships import Membership, MembershipStatus
from packages.core_domain.organization_context import (
    ExternalIdentity,
    ExternalIdentityStatus,
    OrganizationContext,
)
from packages.core_domain.organizations import Organization
from packages.core_domain.users import User

__all__ = [
    "CanonicalPayload",
    "ChangeKind",
    "Correction",
    "AuthenticatedPrincipal",
    "DomainEvent",
    "ExternalIdentity",
    "ExternalIdentityStatus",
    "Membership",
    "MembershipRoleAssignment",
    "MembershipRoleRevocation",
    "MembershipStatus",
    "Organization",
    "OrganizationContext",
    "Permission",
    "PrincipalType",
    "Role",
    "User",
    "build_correction",
]
