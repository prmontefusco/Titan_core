"""Testes unitários para AnimalService (Passo 8.2 - Titan Livestock)."""

from uuid import uuid4

import pytest

from packages.livestock_application.animal_service import (
    AnimalRepositoryPort,
    AnimalService,
)
from packages.livestock_domain.animal import (
    Animal,
    AnimalSex,
    IdentifierState,
    IdentifierType,
)
from packages.shared_kernel import OrganizationId, TypedId


class InMemoryAnimalRepository(AnimalRepositoryPort):
    def __init__(self) -> None:
        self.animals: dict[str, Animal] = {}

    def save(self, animal: Animal) -> None:
        self.animals[animal.animal_id.value.hex] = animal

    def update(self, animal: Animal) -> None:
        self.animals[animal.animal_id.value.hex] = animal

    def get_by_id(self, animal_id: TypedId) -> Animal | None:
        return self.animals.get(animal_id.value.hex)

    def find_by_identifier(
        self,
        organization_id: OrganizationId,
        identifier_type: IdentifierType,
        identifier_value: str,
    ) -> Animal | None:
        for animal in self.animals.values():
            if animal.organization_id == organization_id:
                for tag in animal.identifiers:
                    if (
                        tag.identifier_type == identifier_type
                        and tag.identifier_value == identifier_value
                        and tag.state == IdentifierState.ACTIVE
                    ):
                        return animal
        return None

    def list_by_organization(
        self, organization_id: OrganizationId, limit: int = 50, offset: int = 0
    ) -> list[Animal]:
        filtered = [a for a in self.animals.values() if a.organization_id == organization_id]
        return filtered[offset : offset + limit]


def test_register_animal_and_find_by_sisbov() -> None:
    repo = InMemoryAnimalRepository()
    service = AnimalService(repository=repo)
    org_id = OrganizationId(uuid4())
    prop_id = TypedId.new("rural_property")

    animal = service.register_animal(
        organization_id=org_id,
        birth_property_id=prop_id,
        sex=AnimalSex.MALE,
        breed="Nelore",
        initial_identifier_type=IdentifierType.OFFICIAL_SISBOV,
        initial_identifier_value="BR99881122",
    )

    assert animal.organization_id == org_id
    found = service.find_by_identifier(org_id, IdentifierType.OFFICIAL_SISBOV, "BR99881122")
    assert found == animal


def test_register_animal_duplicate_sisbov_fails() -> None:
    repo = InMemoryAnimalRepository()
    service = AnimalService(repository=repo)
    org_id = OrganizationId(uuid4())
    prop_id = TypedId.new("rural_property")

    service.register_animal(
        organization_id=org_id,
        birth_property_id=prop_id,
        sex=AnimalSex.FEMALE,
        initial_identifier_type=IdentifierType.OFFICIAL_SISBOV,
        initial_identifier_value="BR99881122",
    )

    with pytest.raises(ValueError, match="Já existe um animal com o identificador"):
        service.register_animal(
            organization_id=org_id,
            birth_property_id=prop_id,
            sex=AnimalSex.MALE,
            initial_identifier_type=IdentifierType.OFFICIAL_SISBOV,
            initial_identifier_value="BR99881122",
        )
