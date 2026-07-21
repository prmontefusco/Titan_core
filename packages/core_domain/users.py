"""Identidade humana interna reconhecida pelo Titan."""

from dataclasses import dataclass
from typing import Self

from packages.shared_kernel import OrganizationId, TypedId


@dataclass(frozen=True, slots=True)
class User:
    """User global cujo registro é owned pela Organization operadora."""

    user_id: TypedId
    record_owner_organization_id: OrganizationId

    def __post_init__(self) -> None:
        if not isinstance(self.user_id, TypedId):
            raise TypeError("user_id deve ser um TypedId.")
        if self.user_id.entity_type != "user":
            raise ValueError("user_id deve possuir tipo lógico 'user'.")
        if not isinstance(self.record_owner_organization_id, OrganizationId):
            raise TypeError("record_owner_organization_id deve ser um OrganizationId.")

    @classmethod
    def create(cls, *, platform_operator_organization_id: OrganizationId) -> Self:
        return cls(
            user_id=TypedId.new("user"),
            record_owner_organization_id=platform_operator_organization_id,
        )
