from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from packages.core_domain import (
    AuthenticatedPrincipal,
    ExternalIdentity,
    OrganizationContext,
    PrincipalType,
)
from packages.shared_kernel import OrganizationId, TypedId


def test_external_identity_uses_issuer_subject_and_internal_user() -> None:
    identity = ExternalIdentity.link_user(
        operator_organization_id=OrganizationId.new(),
        issuer="https://issuer.example",
        subject="subject-1",
        user_id=TypedId.new("user"),
        linked_at=datetime(2026, 7, 21, tzinfo=UTC),
        linked_by_actor_id=TypedId.new("actor"),
    )
    assert identity.issuer == "https://issuer.example"
    assert identity.subject == "subject-1"


def test_organization_context_is_immutable_and_has_no_token() -> None:
    principal = AuthenticatedPrincipal(
        issuer="https://issuer.example",
        subject="subject-1",
        principal_type=PrincipalType.USER,
        authenticated_at=None,
        client_id=None,
        technical_scopes=frozenset(),
    )
    context = OrganizationContext(
        organization_id=OrganizationId.new(),
        authenticated_principal=principal,
        user_id=TypedId.new("user"),
        actor_id=TypedId.new("actor"),
        membership_id=TypedId.new("membership"),
        role_ids=(TypedId.new("role"),),
        permission_codes=frozenset({"DOSSIER.LER"}),
        validated_at=datetime(2026, 7, 21, tzinfo=UTC),
    )
    with pytest.raises(FrozenInstanceError):
        context.permission_codes = frozenset()  # type: ignore[misc]
