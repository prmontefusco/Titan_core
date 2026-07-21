from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from packages.core_application import OrganizationContextDenied, OrganizationContextService
from packages.core_domain import (
    AuthenticatedPrincipal,
    ExternalIdentity,
    Membership,
    PrincipalType,
)
from packages.shared_kernel import OrganizationId, TypedId

NOW = datetime(2026, 7, 21, 12, tzinfo=UTC)


@dataclass
class FakeReader:
    identity: ExternalIdentity | None
    memberships: tuple[Membership, ...]

    def resolve_external_identity(
        self, principal: AuthenticatedPrincipal
    ) -> ExternalIdentity | None:
        return self.identity

    def valid_memberships(
        self, user_id: TypedId, organization_id: OrganizationId, instant: datetime
    ) -> tuple[Membership, ...]:
        return tuple(item for item in self.memberships if item.organization_id == organization_id)

    def effective_roles_and_permissions(
        self, membership_id: TypedId, instant: datetime
    ) -> tuple[tuple[TypedId, ...], frozenset[str]]:
        return (TypedId.new("role"),), frozenset({"DOSSIER.LER"})


def _principal() -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        issuer="https://issuer.example",
        subject="subject-1",
        principal_type=PrincipalType.USER,
        authenticated_at=NOW,
        client_id="client",
        technical_scopes=frozenset({"openid"}),
    )


def _identity(user_id: TypedId) -> ExternalIdentity:
    return ExternalIdentity.link_user(
        operator_organization_id=OrganizationId.new(),
        issuer="https://issuer.example",
        subject="subject-1",
        user_id=user_id,
        linked_at=NOW,
        linked_by_actor_id=TypedId.new("actor"),
    )


def test_service_builds_context_only_for_requested_organization_membership() -> None:
    user_id = TypedId.new("user")
    organization_id = OrganizationId.new()
    membership = Membership.create(
        user_id=user_id,
        organization_id=organization_id,
        valid_from=NOW,
        valid_until=None,
        origin_reference=TypedId.new("membership_invitation"),
        granted_by_actor_id=TypedId.new("actor"),
    )
    context = OrganizationContextService(FakeReader(_identity(user_id), (membership,))).build(
        principal=_principal(), requested_organization_id=organization_id, instant=NOW
    )
    assert context.organization_id == organization_id
    assert context.membership_id == membership.membership_id
    assert context.permission_codes == {"DOSSIER.LER"}


def test_service_denies_unknown_identity_or_organization_without_membership() -> None:
    principal = _principal()
    with pytest.raises(OrganizationContextDenied):
        OrganizationContextService(FakeReader(None, ())).build(
            principal=principal,
            requested_organization_id=OrganizationId.new(),
            instant=NOW,
        )
    with pytest.raises(OrganizationContextDenied):
        OrganizationContextService(FakeReader(_identity(TypedId.new("user")), ())).build(
            principal=principal,
            requested_organization_id=OrganizationId.new(),
            instant=NOW,
        )
