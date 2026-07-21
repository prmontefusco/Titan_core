from dataclasses import FrozenInstanceError, fields

import pytest

from packages.core_domain import User
from packages.shared_kernel import OrganizationId, TypedId


def test_creates_user_owned_by_platform_operator_organization() -> None:
    operator_id = OrganizationId.new()

    user = User.create(platform_operator_organization_id=operator_id)

    assert user.user_id.entity_type == "user"
    assert user.record_owner_organization_id == operator_id


def test_rejects_identifier_with_wrong_logical_type() -> None:
    with pytest.raises(ValueError, match="tipo lógico 'user'"):
        User(
            user_id=TypedId.new("service_identity"),
            record_owner_organization_id=OrganizationId.new(),
        )


def test_rejects_untyped_record_owner() -> None:
    with pytest.raises(TypeError, match="OrganizationId"):
        User(
            user_id=TypedId.new("user"),
            record_owner_organization_id=TypedId.new("organization"),  # type: ignore[arg-type]
        )


def test_user_is_immutable() -> None:
    user = User.create(platform_operator_organization_id=OrganizationId.new())

    with pytest.raises(FrozenInstanceError):
        user.user_id = TypedId.new("user")  # type: ignore[misc]


def test_user_contract_has_no_credential_membership_role_or_permission() -> None:
    field_names = {field.name for field in fields(User)}

    assert field_names == {"user_id", "record_owner_organization_id"}
