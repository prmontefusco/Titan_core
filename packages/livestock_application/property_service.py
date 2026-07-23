"""Serviço de aplicação RuralPropertyService (Passo 8.1 - Titan Livestock)."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from packages.livestock_domain.property import RuralProperty
from packages.shared_kernel import OrganizationId, TypedId


class RuralPropertyRepositoryPort(Protocol):
    def save(self, property: RuralProperty) -> None: ...

    def get_by_id(self, property_id: TypedId) -> RuralProperty | None: ...

    def get_by_code(self, organization_id: OrganizationId, code: str) -> RuralProperty | None: ...

    def list_by_organization(
        self, organization_id: OrganizationId, limit: int = 50, offset: int = 0
    ) -> list[RuralProperty]: ...


@dataclass(frozen=True, slots=True)
class RuralPropertyService:
    repository: RuralPropertyRepositoryPort

    def register_property(
        self,
        organization_id: OrganizationId,
        code: str,
        name: str,
        municipality: str,
        state_code: str,
        registration_number: str | None = None,
        total_area_hectares: float | None = None,
    ) -> RuralProperty:
        # Verifica duplicidade de código dentro da mesma organização
        existing = self.repository.get_by_code(organization_id, code)
        if existing is not None:
            raise ValueError(
                f"Propriedade rural com código '{code}' já cadastrada para a organização "
                f"{organization_id.value}."
            )

        property_obj = RuralProperty(
            property_id=TypedId.new("rural_property"),
            organization_id=organization_id,
            code=code,
            name=name,
            municipality=municipality,
            state_code=state_code,
            registration_number=registration_number,
            total_area_hectares=total_area_hectares,
            created_at=datetime.now(UTC),
        )

        self.repository.save(property_obj)
        return property_obj

    def get_property(self, property_id: TypedId) -> RuralProperty | None:
        return self.repository.get_by_id(property_id)

    def get_by_code(self, organization_id: OrganizationId, code: str) -> RuralProperty | None:
        return self.repository.get_by_code(organization_id, code)

    def list_properties(
        self, organization_id: OrganizationId, limit: int = 50, offset: int = 0
    ) -> list[RuralProperty]:
        return self.repository.list_by_organization(organization_id, limit=limit, offset=offset)
