"""Serviço de aplicação AnimalService (Passo 8.2 - Titan Livestock)."""

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Protocol

from packages.livestock_domain.animal import (
    Animal,
    AnimalIdentifier,
    AnimalSex,
    IdentifierState,
    IdentifierType,
)
from packages.shared_kernel import OrganizationId, TypedId


class AnimalRepositoryPort(Protocol):
    def save(self, animal: Animal) -> None: ...

    def update(self, animal: Animal) -> None: ...

    def get_by_id(self, animal_id: TypedId) -> Animal | None: ...

    def find_by_identifier(
        self,
        organization_id: OrganizationId,
        identifier_type: IdentifierType,
        identifier_value: str,
    ) -> Animal | None: ...

    def list_by_organization(
        self, organization_id: OrganizationId, limit: int = 50, offset: int = 0
    ) -> list[Animal]: ...


@dataclass(frozen=True, slots=True)
class AnimalService:
    repository: AnimalRepositoryPort

    def register_animal(
        self,
        organization_id: OrganizationId,
        birth_property_id: TypedId,
        sex: AnimalSex,
        breed: str | None = None,
        birth_date: date | None = None,
        initial_identifier_type: IdentifierType | None = None,
        initial_identifier_value: str | None = None,
    ) -> Animal:
        identifiers: list[AnimalIdentifier] = []

        if initial_identifier_type is not None and initial_identifier_value is not None:
            # Valida duplicidade de identificador oficial no tenant
            existing = self.repository.find_by_identifier(
                organization_id, initial_identifier_type, initial_identifier_value
            )
            if existing is not None:
                raise ValueError(
                    f"Já existe um animal com o identificador '{initial_identifier_type.value}:"
                    f"{initial_identifier_value}' cadastrado para a organização "
                    f"{organization_id.value}."
                )

            tag = AnimalIdentifier(
                identifier_id=TypedId.new("animal_identifier"),
                identifier_type=initial_identifier_type,
                identifier_value=initial_identifier_value,
                state=IdentifierState.ACTIVE,
                attached_at=datetime.now(UTC),
            )
            identifiers.append(tag)

        animal = Animal(
            animal_id=TypedId.new("animal"),
            organization_id=organization_id,
            birth_property_id=birth_property_id,
            sex=sex,
            breed=breed,
            birth_date=birth_date,
            identifiers=tuple(identifiers),
            created_at=datetime.now(UTC),
        )

        self.repository.save(animal)
        return animal

    def attach_identifier(
        self,
        animal_id: TypedId,
        identifier_type: IdentifierType,
        identifier_value: str,
    ) -> Animal:
        animal = self.repository.get_by_id(animal_id)
        if animal is None:
            raise KeyError(f"Animal '{animal_id.value}' não encontrado.")

        # Valida duplicidade no tenant
        existing = self.repository.find_by_identifier(
            animal.organization_id, identifier_type, identifier_value
        )
        if existing is not None and existing.animal_id != animal_id:
            raise ValueError(
                f"Identificador '{identifier_type.value}:{identifier_value}' já está "
                f"em uso por outro animal ({existing.animal_id.value})."
            )

        tag = AnimalIdentifier(
            identifier_id=TypedId.new("animal_identifier"),
            identifier_type=identifier_type,
            identifier_value=identifier_value,
            state=IdentifierState.ACTIVE,
            attached_at=datetime.now(UTC),
        )

        updated_animal = animal.attach_identifier(tag)
        self.repository.update(updated_animal)
        return updated_animal

    def deactivate_identifier(self, animal_id: TypedId, identifier_id: TypedId) -> Animal:
        animal = self.repository.get_by_id(animal_id)
        if animal is None:
            raise KeyError(f"Animal '{animal_id.value}' não encontrado.")

        updated_animal = animal.deactivate_identifier(
            identifier_id, deactivated_at=datetime.now(UTC)
        )
        self.repository.update(updated_animal)
        return updated_animal

    def get_animal(self, animal_id: TypedId) -> Animal | None:
        return self.repository.get_by_id(animal_id)

    def find_by_identifier(
        self,
        organization_id: OrganizationId,
        identifier_type: IdentifierType,
        identifier_value: str,
    ) -> Animal | None:
        return self.repository.find_by_identifier(
            organization_id, identifier_type, identifier_value
        )

    def list_animals(
        self, organization_id: OrganizationId, limit: int = 50, offset: int = 0
    ) -> list[Animal]:
        return self.repository.list_by_organization(organization_id, limit=limit, offset=offset)
