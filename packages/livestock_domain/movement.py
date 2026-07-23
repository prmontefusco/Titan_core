"""Entidades de domínio AnimalMovement e PropertyStay (Passo 8.3 - Titan Livestock)."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from packages.shared_kernel import OrganizationId, TypedId
from packages.shared_kernel.temporal import require_utc


class StayStatus(StrEnum):
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class AnimalMovement:
    movement_id: TypedId
    organization_id: OrganizationId
    origin_property_id: TypedId
    destination_property_id: TypedId
    movement_time: datetime
    animal_ids: tuple[TypedId, ...]
    reason: str | None = None
    evidence_reference: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        require_utc(self.movement_time, field_name="movement_time")
        require_utc(self.created_at, field_name="created_at")
        if self.movement_id.entity_type != "animal_movement":
            raise ValueError(
                "movement_id deve ter entity_type 'animal_movement', recebido "
                f"'{self.movement_id.entity_type}'."
            )
        if self.origin_property_id.entity_type != "rural_property":
            raise ValueError(
                "origin_property_id deve ter entity_type 'rural_property', recebido "
                f"'{self.origin_property_id.entity_type}'."
            )
        if self.destination_property_id.entity_type != "rural_property":
            raise ValueError(
                "destination_property_id deve ter entity_type 'rural_property', recebido "
                f"'{self.destination_property_id.entity_type}'."
            )
        if self.origin_property_id == self.destination_property_id:
            raise ValueError("origin_property_id e destination_property_id não podem ser iguais.")
        if not self.animal_ids:
            raise ValueError("animal_ids deve conter pelo menos um animal.")
        for aid in self.animal_ids:
            if aid.entity_type != "animal":
                raise ValueError(
                    f"Todos os animal_ids devem ter entity_type 'animal', recebido "
                    f"'{aid.entity_type}'."
                )

        # A regra "não pode ser no futuro" compara com o instante atual e por isso
        # vive na Application (movement_service), que injeta o relógio. O domínio
        # não lê o relógio: seria não determinístico e intestável com tempo fixo.


@dataclass(frozen=True, slots=True)
class PropertyStay:
    stay_id: TypedId
    organization_id: OrganizationId
    animal_id: TypedId
    property_id: TypedId
    start_time: datetime
    end_time: datetime | None = None
    status: StayStatus = StayStatus.ACTIVE
    source_movement_id: TypedId | None = None

    def __post_init__(self) -> None:
        if self.stay_id.entity_type != "property_stay":
            raise ValueError(
                "stay_id deve ter entity_type 'property_stay', recebido "
                f"'{self.stay_id.entity_type}'."
            )
        if self.animal_id.entity_type != "animal":
            raise ValueError(
                f"animal_id deve ter entity_type 'animal', recebido '{self.animal_id.entity_type}'."
            )
        if self.property_id.entity_type != "rural_property":
            raise ValueError(
                "property_id deve ter entity_type 'rural_property', recebido "
                f"'{self.property_id.entity_type}'."
            )
        if (
            self.source_movement_id is not None
            and self.source_movement_id.entity_type != "animal_movement"
        ):
            raise ValueError(
                "source_movement_id deve ter entity_type 'animal_movement', recebido "
                f"'{self.source_movement_id.entity_type}'."
            )

        require_utc(self.start_time, field_name="start_time")
        if self.end_time is not None:
            require_utc(self.end_time, field_name="end_time")
            if self.end_time <= self.start_time:
                raise ValueError("end_time deve ser estritamente posterior a start_time.")
            if self.status == StayStatus.ACTIVE:
                raise ValueError(
                    "Uma permanência com end_time preenchido não pode ter status ACTIVE."
                )
