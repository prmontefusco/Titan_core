"""Serviço de aplicação AnimalService (Passo 8.2 - Titan Livestock)."""

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Protocol

from packages.livestock_application.event_recorder import (
    LivestockEventRecorder,
    LivestockOperationContext,
)
from packages.livestock_domain.animal import (
    Animal,
    AnimalIdentifier,
    AnimalSex,
    IdentifierState,
    IdentifierType,
)
from packages.livestock_domain.events import (
    ANIMAL_REGISTERED,
    IDENTIFIER_ATTACHED,
    IDENTIFIER_DEACTIVATED,
    animal_registered_payload,
    identifier_attached_payload,
    identifier_deactivated_payload,
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
    recorder: LivestockEventRecorder

    def register_animal(
        self,
        context: LivestockOperationContext,
        birth_property_id: TypedId,
        sex: AnimalSex,
        breed: str | None = None,
        birth_date: date | None = None,
        initial_identifier_type: IdentifierType | None = None,
        initial_identifier_value: str | None = None,
    ) -> Animal:
        organization_id = context.organization_id
        # Um único instante para o cadastro e para a marcação inicial. Lê-los em
        # momentos diferentes daria à marcação um `occurred_at` ANTERIOR ao do
        # cadastro — e uma linha do tempo ordenada por esse campo mostraria o
        # brinco sendo colocado antes de o animal existir. Empatados, a ordem fica
        # por `aggregate_version`, que é sequencial e não depende do relógio.
        occurred_at = datetime.now(UTC)
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
                attached_at=occurred_at,
            )
            identifiers.append(tag)

        created_at = occurred_at
        animal = Animal(
            animal_id=TypedId.new("animal"),
            organization_id=organization_id,
            birth_property_id=birth_property_id,
            sex=sex,
            breed=breed,
            birth_date=birth_date,
            identifiers=tuple(identifiers),
            created_at=created_at,
        )

        self.repository.save(animal)
        self.recorder.record(
            context=context,
            aggregate_id=animal.animal_id,
            event_type=ANIMAL_REGISTERED,
            payload=animal_registered_payload(
                animal_id=animal.animal_id,
                birth_property_id=animal.birth_property_id,
                sex=animal.sex.value,
                breed=animal.breed,
                birth_date=None if animal.birth_date is None else animal.birth_date.isoformat(),
            ),
            occurred_at=created_at,
        )
        # O identificador inicial é fato próprio: quem lê a linha do tempo precisa
        # ver a marcação como evento, não deduzi-la do cadastro.
        for tag in animal.identifiers:
            self._record_attachment(context, animal.animal_id, tag)
        return animal

    def _record_attachment(
        self,
        context: LivestockOperationContext,
        animal_id: TypedId,
        tag: AnimalIdentifier,
    ) -> None:
        self.recorder.record(
            context=context,
            aggregate_id=animal_id,
            event_type=IDENTIFIER_ATTACHED,
            payload=identifier_attached_payload(
                animal_id=animal_id,
                identifier_id=tag.identifier_id,
                identifier_type=tag.identifier_type.value,
                identifier_value=tag.identifier_value,
                attached_at=tag.attached_at,
            ),
            occurred_at=tag.attached_at,
        )

    def attach_identifier(
        self,
        context: LivestockOperationContext,
        animal_id: TypedId,
        identifier_type: IdentifierType,
        identifier_value: str,
    ) -> Animal:
        animal = self._owned_animal(context, animal_id)

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
        self._record_attachment(context, animal_id, tag)
        return updated_animal

    def deactivate_identifier(
        self,
        context: LivestockOperationContext,
        animal_id: TypedId,
        identifier_id: TypedId,
    ) -> Animal:
        animal = self._owned_animal(context, animal_id)

        deactivated_at = datetime.now(UTC)
        updated_animal = animal.deactivate_identifier(identifier_id, deactivated_at=deactivated_at)
        self.repository.update(updated_animal)
        self.recorder.record(
            context=context,
            aggregate_id=animal_id,
            event_type=IDENTIFIER_DEACTIVATED,
            payload=identifier_deactivated_payload(
                animal_id=animal_id,
                identifier_id=identifier_id,
                deactivated_at=deactivated_at,
            ),
            occurred_at=deactivated_at,
        )
        return updated_animal

    def _owned_animal(self, context: LivestockOperationContext, animal_id: TypedId) -> Animal:
        """Recusa operar animal de outra Organization em vez de gravar evento cruzado."""
        animal = self.repository.get_by_id(animal_id)
        if animal is None or animal.organization_id != context.organization_id:
            raise KeyError(f"Animal '{animal_id.value}' não encontrado.")
        return animal

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
