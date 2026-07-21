"""Organization como unidade estável de isolamento e responsabilidade."""

from dataclasses import dataclass
from typing import Self

from packages.shared_kernel import OrganizationId


@dataclass(frozen=True, slots=True)
class Organization:
    """Identidade de uma Organization reconhecida pelo Titan."""

    organization_id: OrganizationId

    def __post_init__(self) -> None:
        if not isinstance(self.organization_id, OrganizationId):
            raise TypeError("organization_id deve ser um OrganizationId.")

    @classmethod
    def create(cls) -> Self:
        return cls(organization_id=OrganizationId.new())
