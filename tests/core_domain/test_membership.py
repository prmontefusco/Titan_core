from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta

import pytest

from packages.core_domain import Membership, MembershipStatus, Organization, User
from packages.shared_kernel import OrganizationId, TypedId


def _membership() -> Membership:
    organization = Organization.create()
    user = User.create(platform_operator_organization_id=OrganizationId.new())
    return Membership.create(
        user_id=user.user_id,
        organization_id=organization.organization_id,
        valid_from=datetime(2026, 7, 21, tzinfo=UTC),
        valid_until=datetime(2026, 8, 21, tzinfo=UTC),
        origin_reference=TypedId.new("membership_invitation"),
        granted_by_actor_id=TypedId.new("actor"),
    )


def test_membership_is_owned_by_linked_organization_and_starts_active() -> None:
    membership = _membership()

    assert membership.record_owner_organization_id == membership.organization_id
    assert membership.status is MembershipStatus.ATIVA


def test_membership_validity_uses_half_open_utc_interval() -> None:
    membership = _membership()

    assert membership.is_valid_at(membership.valid_from)
    assert membership.valid_until is not None
    assert not membership.is_valid_at(membership.valid_until)


def test_membership_inactive_status_is_not_valid() -> None:
    membership = replace(_membership(), status=MembershipStatus.SUSPENSA)

    assert not membership.is_valid_at(membership.valid_from + timedelta(days=1))


def test_membership_rejects_non_utc_and_invalid_interval() -> None:
    membership = _membership()

    with pytest.raises(ValueError, match="timezone UTC"):
        replace(membership, valid_from=datetime(2026, 7, 21))
    with pytest.raises(ValueError, match="posterior"):
        replace(membership, valid_until=membership.valid_from)


def test_membership_rejects_wrong_user_actor_and_owner() -> None:
    membership = _membership()

    with pytest.raises(ValueError, match="tipo lógico 'user'"):
        replace(membership, user_id=TypedId.new("service_identity"))
    with pytest.raises(ValueError, match="tipo lógico 'actor'"):
        replace(membership, granted_by_actor_id=TypedId.new("user"))
    with pytest.raises(ValueError, match="owned"):
        replace(membership, record_owner_organization_id=OrganizationId.new())


def test_membership_is_immutable() -> None:
    membership = _membership()

    with pytest.raises(FrozenInstanceError):
        membership.status = MembershipStatus.ENCERRADA  # type: ignore[misc]
