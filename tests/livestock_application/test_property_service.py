"""Testes unitários para RuralPropertyService (Passo 8.1 - Titan Livestock)."""

from uuid import uuid4

import pytest

from packages.livestock_application.property_service import (
    RuralPropertyRepositoryPort,
    RuralPropertyService,
)
from packages.livestock_domain.property import RuralProperty
from packages.shared_kernel import OrganizationId, TypedId


class InMemoryRuralPropertyRepository(RuralPropertyRepositoryPort):
    def __init__(self) -> None:
        self.properties: dict[str, RuralProperty] = {}

    def save(self, property: RuralProperty) -> None:
        self.properties[property.property_id.value.hex] = property

    def get_by_id(self, property_id: TypedId) -> RuralProperty | None:
        return self.properties.get(property_id.value.hex)

    def get_by_code(self, organization_id: OrganizationId, code: str) -> RuralProperty | None:
        for prop in self.properties.values():
            if prop.organization_id == organization_id and prop.code == code:
                return prop
        return None

    def list_by_organization(
        self, organization_id: OrganizationId, limit: int = 50, offset: int = 0
    ) -> list[RuralProperty]:
        filtered = [p for p in self.properties.values() if p.organization_id == organization_id]
        return filtered[offset : offset + limit]


def test_register_property_success() -> None:
    repo = InMemoryRuralPropertyRepository()
    service = RuralPropertyService(repository=repo)
    org_id = OrganizationId(uuid4())

    prop = service.register_property(
        organization_id=org_id,
        code="PROP-MG-001",
        name="Fazenda Boa Vista",
        municipality="Uberaba",
        state_code="MG",
        registration_number="CAR-MG-9981",
        total_area_hectares=500.0,
    )

    assert prop.code == "PROP-MG-001"
    assert prop.organization_id == org_id
    assert repo.get_by_id(prop.property_id) == prop


def test_register_property_duplicate_code_fails() -> None:
    repo = InMemoryRuralPropertyRepository()
    service = RuralPropertyService(repository=repo)
    org_id = OrganizationId(uuid4())

    service.register_property(
        organization_id=org_id,
        code="PROP-MG-001",
        name="Fazenda Boa Vista",
        municipality="Uberaba",
        state_code="MG",
    )

    with pytest.raises(ValueError, match="já cadastrada para a organização"):
        service.register_property(
            organization_id=org_id,
            code="PROP-MG-001",
            name="Outra Fazenda com mesmo código",
            municipality="Uberlândia",
            state_code="MG",
        )
