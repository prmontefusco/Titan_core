from dataclasses import FrozenInstanceError

import pytest

from packages.core_domain import Organization
from packages.shared_kernel import OrganizationId, TypedId


def test_creates_organization_with_stable_typed_identity() -> None:
    organization = Organization.create()

    assert isinstance(organization.organization_id, OrganizationId)
    assert organization.organization_id.value.int != 0


def test_rejects_identifier_from_another_entity_type() -> None:
    with pytest.raises(TypeError, match="OrganizationId"):
        Organization(organization_id=TypedId.new("organization"))  # type: ignore[arg-type]


def test_organization_identity_is_immutable() -> None:
    organization = Organization.create()

    with pytest.raises(FrozenInstanceError):
        organization.organization_id = OrganizationId.new()  # type: ignore[misc]
