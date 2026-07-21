from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime

import pytest

from packages.core_domain import (
    MembershipRoleAssignment,
    MembershipRoleRevocation,
    Permission,
    Role,
)
from packages.shared_kernel import OrganizationId, TypedId


def test_permission_requires_canonical_code_and_operator_owner() -> None:
    owner = OrganizationId.new()
    permission = Permission.create(operator_organization_id=owner, code="DOSSIER.LER")
    assert permission.record_owner_organization_id == owner
    with pytest.raises(ValueError, match="formato"):
        Permission.create(operator_organization_id=owner, code="dossier:ler")


def test_role_is_owned_by_organization_and_rejects_duplicate_permissions() -> None:
    organization_id = OrganizationId.new()
    permission_id = TypedId.new("permission")
    role = Role.create(
        organization_id=organization_id,
        name="Revisor",
        permission_ids=(permission_id,),
    )
    assert role.record_owner_organization_id == organization_id
    with pytest.raises(ValueError, match="duplicidade"):
        replace(role, permission_ids=(permission_id, permission_id))


def test_assignment_is_temporal_and_owned_by_membership_organization() -> None:
    organization_id = OrganizationId.new()
    assignment = MembershipRoleAssignment.create(
        membership_id=TypedId.new("membership"),
        role_id=TypedId.new("role"),
        organization_id=organization_id,
        valid_from=datetime(2026, 7, 21, tzinfo=UTC),
        valid_until=None,
        granted_by_actor_id=TypedId.new("actor"),
    )
    assert assignment.record_owner_organization_id == organization_id
    with pytest.raises(ValueError, match="posterior"):
        replace(assignment, valid_until=assignment.valid_from)


def test_revocation_preserves_assignment_and_organization() -> None:
    organization_id = OrganizationId.new()
    revocation = MembershipRoleRevocation.create(
        assignment_id=TypedId.new("membership_role_assignment"),
        organization_id=organization_id,
        revoked_at=datetime(2026, 7, 22, tzinfo=UTC),
        revoked_by_actor_id=TypedId.new("actor"),
    )
    assert revocation.record_owner_organization_id == organization_id


def test_authorization_models_are_immutable() -> None:
    permission = Permission.create(
        operator_organization_id=OrganizationId.new(), code="REGISTRO.LER"
    )
    with pytest.raises(FrozenInstanceError):
        permission.code = "REGISTRO.ALTERAR"  # type: ignore[misc]
