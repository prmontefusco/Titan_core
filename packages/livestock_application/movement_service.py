"""Serviço de aplicação MovementService (Passo 8.3 - Titan Livestock)."""

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Protocol

from packages.livestock_application.animal_service import AnimalRepositoryPort
from packages.livestock_application.event_recorder import (
    LivestockEventRecorder,
    LivestockOperationContext,
)
from packages.livestock_application.exit_service import guard_animal_active
from packages.livestock_application.property_service import RuralPropertyRepositoryPort
from packages.livestock_domain.events import ANIMAL_MOVED, animal_moved_payload
from packages.livestock_domain.movement import (
    AnimalMovement,
    PropertyStay,
    StayStatus,
)
from packages.shared_kernel import OrganizationId, TypedId
from packages.shared_kernel.temporal import require_utc


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
    recorder: LivestockEventRecorder

    def register_movement(
        self,
        context: LivestockOperationContext,
        origin_property_id: TypedId,
        destination_property_id: TypedId,
        movement_time: datetime,
        animal_ids: tuple[TypedId, ...],
        reason: str | None = None,
        evidence_reference: str | None = None,
    ) -> AnimalMovement:
        organization_id = context.organization_id
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

        # 2. Valida existência dos animais e recusa mover quem já saiu do rebanho
        for aid in animal_ids:
            animal = self.animal_repository.get_by_id(aid)
            if animal is None or animal.organization_id != organization_id:
                raise KeyError(
                    f"Animal '{aid.value}' não encontrado ou pertencente a outra organização."
                )
            guard_animal_active(self.animal_repository, aid, movement_time)

        # O horário do movimento é alegado pelo chamador: precisa ser UTC explícito
        # (o domínio rejeita naive) e não pode estar no futuro em relação ao relógio
        # do servidor, capturado aqui uma única vez.
        now = datetime.now(UTC)
        require_utc(movement_time, field_name="movement_time")
        if movement_time > now:
            raise ValueError("movement_time não pode ser no futuro.")

        movement = AnimalMovement(
            movement_id=TypedId.new("animal_movement"),
            organization_id=organization_id,
            origin_property_id=origin_property_id,
            destination_property_id=destination_property_id,
            movement_time=movement_time,
            animal_ids=animal_ids,
            reason=reason,
            evidence_reference=evidence_reference,
            created_at=now,
        )

        self.movement_repository.save(movement)
        # O fato é a movimentação, e ela tem fluxo próprio: repetir o evento em
        # cada animal gravaria o mesmo acontecimento várias vezes. Quem monta a
        # linha do tempo de um animal alcança a movimentação pelos animal_ids.
        self.recorder.record(
            context=context,
            aggregate_id=movement.movement_id,
            event_type=ANIMAL_MOVED,
            payload=animal_moved_payload(
                movement_id=movement.movement_id,
                origin_property_id=movement.origin_property_id,
                destination_property_id=movement.destination_property_id,
                movement_time=movement.movement_time,
                animal_ids=movement.animal_ids,
                reason=movement.reason,
                evidence_reference=movement.evidence_reference,
            ),
            occurred_at=movement.movement_time,
        )

        # 3. Atualiza as permanências (PropertyStay) para cada animal
        for aid in animal_ids:
            active_stay = self.stay_repository.get_active_stay(aid)
            if active_stay is not None:
                # Fecha a estada anterior
                closed_stay = replace(
                    active_stay,
                    end_time=movement_time,
                    status=StayStatus.CLOSED,
                )
                self.stay_repository.update(closed_stay)

            # Abre a nova estada ativa no destino
            new_stay = PropertyStay(
                stay_id=TypedId.new("property_stay"),
                organization_id=organization_id,
                animal_id=aid,
                property_id=destination_property_id,
                start_time=movement_time,
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

        # Estada inicial do nascimento. Ela não existe quando a propriedade de
        # nascimento é desconhecida (ADR-0040): inventar um ponto de partida diria
        # onde o animal esteve, que é justamente o que não se sabe. A história de
        # permanências passa a começar na primeira movimentação registrada.
        current_stay: PropertyStay | None = None
        if animal.birth_property_id is not None:
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
            if current_stay is not None:
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

        if current_stay is not None:
            rebuilt.append(current_stay)
            self.stay_repository.save(current_stay)
        return rebuilt
