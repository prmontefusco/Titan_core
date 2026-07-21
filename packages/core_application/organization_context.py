"""Construção fail-closed do OrganizationContext."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from packages.core_domain import (
    AuthenticatedPrincipal,
    ExternalIdentity,
    ExternalIdentityStatus,
    Membership,
    OrganizationContext,
)
from packages.shared_kernel import OrganizationId, TypedId


class OrganizationContextDenied(PermissionError):
    """Negação indistinguível para vínculo ausente, inválido ou invisível."""


class IdentityAndAccessReader(Protocol):
    def resolve_external_identity(
        self, principal: AuthenticatedPrincipal
    ) -> ExternalIdentity | None: ...

    def valid_memberships(
        self, user_id: TypedId, organization_id: OrganizationId, instant: datetime
    ) -> tuple[Membership, ...]: ...

    def effective_roles_and_permissions(
        self, membership_id: TypedId, instant: datetime
    ) -> tuple[tuple[TypedId, ...], frozenset[str]]: ...


@dataclass(frozen=True, slots=True)
class OrganizationContextService:
    reader: IdentityAndAccessReader

    def build(
        self,
        *,
        principal: AuthenticatedPrincipal,
        requested_organization_id: OrganizationId,
        instant: datetime,
    ) -> OrganizationContext:
        identity = self.reader.resolve_external_identity(principal)
        if identity is None or identity.status is not ExternalIdentityStatus.ATIVA:
            raise OrganizationContextDenied("CONTEXTO_ORGANIZACIONAL_NEGADO")
        memberships = self.reader.valid_memberships(
            identity.internal_principal_id, requested_organization_id, instant
        )
        if len(memberships) != 1:
            raise OrganizationContextDenied("CONTEXTO_ORGANIZACIONAL_NEGADO")
        membership = memberships[0]
        role_ids, permission_codes = self.reader.effective_roles_and_permissions(
            membership.membership_id, instant
        )
        return OrganizationContext(
            organization_id=requested_organization_id,
            authenticated_principal=principal,
            user_id=identity.internal_principal_id,
            actor_id=TypedId(entity_type="actor", value=identity.internal_principal_id.value),
            membership_id=membership.membership_id,
            role_ids=role_ids,
            permission_codes=permission_codes,
            validated_at=instant,
        )
