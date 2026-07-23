"""Serviço de aplicação MovementService (Passo 8.3 - Titan Livestock)."""

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Protocol

from packages.livestock_application.animal_service import AnimalRepositoryPort
from packages.livestock_application.property_service import RuralPropertyRepositoryPort
from packages.livestock_domain.movement import (
    AnimalMovement,
    PropertyStay,
    StayStatus,
)
from packages.shared_kernel import OrganizationId, TypedId


class MovementRepositoryPort(Protocol):
    def save(self, movement: AnimalMovement) -> None: ...

    def get_by_id(self, movement_id: TypedId) -> AnimalMovement | None: ...

    def list_by_animal(self, animal_id: TypedId) -> list[AnimalMovement]: ...

    def list_by_organization(
        self, organization_id: OrganizationId, limit: int = 50, offset: int = 0
    ) -> list[AnimalMovement]: ...


class PropertyStayRepositoryPort(Protocol):
    def save(self, stay: PropertyStay) -> None: ...

    def update(self, stay: PropertyStay) -> None: ...

    def delete_by_animal(self, animal_id: TypedId) -> None: ...

    def get_active_stay(self, animal_id: TypedId) -> PropertyStay | None: ...

    def get_timeline(self, animal_id: TypedId) -> list[PropertyStay]: ...


@dataclass(frozen=True, slots=True)
class MovementService:
    movement_repository: MovementRepositoryPort
    stay_repository: PropertyStayRepositoryPort
    animal_repository: AnimalRepositoryPort
    property_repository: RuralPropertyRepositoryPort

    def register_movement(
        self,
        organization_id: OrganizationId,
        origin_property_id: TypedId,
        destination_property_id: TypedId,
        movement_time: datetime,
        animal_ids: tuple[TypedId, ...],
        reason: str | None = None,
        evidence_reference: str | None = None,
    ) -> AnimalMovement:
        # 1. Valida existência de propriedades
        origin_prop = self.property_repository.get_by_id(origin_property_id)
        if origin_prop is None or origin_prop.organization_id != organization_id:
            raise KeyError(
                f"Propriedade de origem '{origin_property_id.value}' não encontrada ou "
                "pertencente a outra organização."
            )

        dest_prop = self.property_repository.get_by_id(destination_property_id)
        if dest_prop is None or dest_prop.organization_id != organization_id:
            raise KeyError(
                f"Propriedade de destino '{destination_property_id.value}' não encontrada ou "
                "pertencente a outra organização."
            )

        # 2. Valida existência dos animais
        for aid in animal_ids:
            animal = self.animal_repository.get_by_id(aid)
            if animal is None or animal.organization_id != organization_id:
                raise KeyError(
                    f"Animal '{aid.value}' não encontrado ou pertencente a outra organização."
                )

        m_time = (
            movement_time.replace(tzinfo=UTC) if movement_time.tzinfo is None else movement_time
        )

        movement = AnimalMovement(
            movement_id=TypedId.new("animal_movement"),
            organization_id=organization_id,
            origin_property_id=origin_property_id,
            destination_property_id=destination_property_id,
            movement_time=m_time,
            animal_ids=animal_ids,
            reason=reason,
            evidence_reference=evidence_reference,
            created_at=datetime.now(UTC),
        )

        self.movement_repository.save(movement)

        # 3. Atualiza as permanências (PropertyStay) para cada animal
        for aid in animal_ids:
            active_stay = self.stay_repository.get_active_stay(aid)
            if active_stay is not None:
                # Fecha a estada anterior
                closed_stay = replace(
                    active_stay,
                    end_time=m_time,
                    status=StayStatus.CLOSED,
                )
                self.stay_repository.update(closed_stay)

            # Abre a nova estada ativa no destino
            new_stay = PropertyStay(
                stay_id=TypedId.new("property_stay"),
                organization_id=organization_id,
                animal_id=aid,
                property_id=destination_property_id,
                start_time=m_time,
                end_time=None,
                status=StayStatus.ACTIVE,
                source_movement_id=movement.movement_id,
            )
            self.stay_repository.save(new_stay)

        return movement

    def get_active_stay(self, animal_id: TypedId) -> PropertyStay | None:
        return self.stay_repository.get_active_stay(animal_id)

    def get_stay_timeline(self, animal_id: TypedId) -> list[PropertyStay]:
        return self.stay_repository.get_timeline(animal_id)

    def rebuild_stays_for_animal(self, animal_id: TypedId) -> list[PropertyStay]:
        """Reconstrói as permanências a partir das movimentações autoritativas."""
        animal = self.animal_repository.get_by_id(animal_id)

        if animal is None:
            raise KeyError(f"Animal '{animal_id.value}' não encontrado.")

        movements = self.movement_repository.list_by_animal(animal_id)
        movements.sort(key=lambda m: m.movement_time)

        self.stay_repository.delete_by_animal(animal_id)

        # Estada inicial do nascimento
        current_stay = PropertyStay(
            stay_id=TypedId.new("property_stay"),
            organization_id=animal.organization_id,
            animal_id=animal_id,
            property_id=animal.birth_property_id,
            start_time=animal.created_at,
            end_time=None,
            status=StayStatus.ACTIVE,
            source_movement_id=None,
        )

        rebuilt: list[PropertyStay] = []
        for m in movements:
            closed_stay = replace(
                current_stay,
                end_time=m.movement_time,
                status=StayStatus.CLOSED,
            )
            rebuilt.append(closed_stay)
            self.stay_repository.save(closed_stay)

            current_stay = PropertyStay(
                stay_id=TypedId.new("property_stay"),
                organization_id=animal.organization_id,
                animal_id=animal_id,
                property_id=m.destination_property_id,
                start_time=m.movement_time,
                end_time=None,
                status=StayStatus.ACTIVE,
                source_movement_id=m.movement_id,
            )

        rebuilt.append(current_stay)
        self.stay_repository.save(current_stay)
        return rebuilt
