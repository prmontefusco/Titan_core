from dataclasses import FrozenInstanceError
from uuid import UUID

import pytest

from packages.shared_kernel import OrganizationId, TypedId, UniversalReference


def test_creates_typed_identifiers_and_organization_scoped_reference() -> None:
    target_id = TypedId.parse("subject", "018f6c67-4f22-7ab0-b43d-1f503c9f8d20")
    organization_id = OrganizationId.parse("cba2d59c-3f0c-4b83-9cb8-4e288f33a214")

    reference = UniversalReference(
        target_id=target_id,
        organization_id=organization_id,
        contract_version=1,
    )

    assert str(reference.target_id) == "subject:018f6c67-4f22-7ab0-b43d-1f503c9f8d20"
    assert reference.organization_id == organization_id


def test_reference_allows_absent_organization_when_not_applicable() -> None:
    reference = UniversalReference(
        target_id=TypedId.new("public_profile"),
        organization_id=None,
        contract_version=2,
    )

    assert reference.organization_id is None


@pytest.mark.parametrize("entity_type", ["", "Subject", "subject type", "subject/type"])
def test_rejects_noncanonical_entity_type(entity_type: str) -> None:
    with pytest.raises(ValueError, match="tipo lógico"):
        TypedId.new(entity_type)


@pytest.mark.parametrize("serialized_id", ["", "not-a-uuid", str(UUID(int=0))])
def test_rejects_invalid_identifier(serialized_id: str) -> None:
    with pytest.raises(ValueError):
        TypedId.parse("subject", serialized_id)


def test_rejects_untyped_organization() -> None:
    with pytest.raises(TypeError, match="OrganizationId"):
        UniversalReference(
            target_id=TypedId.new("subject"),
            organization_id=TypedId.new("organization"),  # type: ignore[arg-type]
            contract_version=1,
        )


@pytest.mark.parametrize("contract_version", [0, -1])
def test_rejects_invalid_contract_version(contract_version: int) -> None:
    with pytest.raises(ValueError, match="maior ou igual a 1"):
        UniversalReference(
            target_id=TypedId.new("subject"),
            organization_id=OrganizationId.new(),
            contract_version=contract_version,
        )


def test_identifiers_and_references_are_immutable() -> None:
    target_id = TypedId.new("subject")
    reference = UniversalReference(target_id, OrganizationId.new(), 1)

    with pytest.raises(FrozenInstanceError):
        reference.contract_version = 2  # type: ignore[misc]
