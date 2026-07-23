"""Eventos de domínio da vertical Titan Livestock (Passo 8.0 - 9.1)."""

from dataclasses import dataclass
from datetime import datetime

from packages.core_domain.events import DomainEvent
from packages.shared_kernel import TypedId


@dataclass(frozen=True, slots=True)
class PropertyRegisteredEvent(DomainEvent):
    property_id: TypedId
    code: str
    name: str
    municipality: str
    state_code: str


@dataclass(frozen=True, slots=True)
class AnimalRegisteredEvent(DomainEvent):
    animal_id: TypedId
    birth_property_id: TypedId
    sex: str
    breed: str | None


@dataclass(frozen=True, slots=True)
class IdentifierAttachedEvent(DomainEvent):
    animal_id: TypedId
    identifier_id: TypedId
    identifier_type: str
    identifier_value: str
    verification_status: str


@dataclass(frozen=True, slots=True)
class IdentifierDeactivatedEvent(DomainEvent):
    animal_id: TypedId
    identifier_id: TypedId
    deactivated_at: datetime


@dataclass(frozen=True, slots=True)
class AnimalMovedEvent(DomainEvent):
    movement_id: TypedId
    origin_property_id: TypedId
    destination_property_id: TypedId
    movement_time: datetime
    animal_ids: tuple[TypedId, ...]


@dataclass(frozen=True, slots=True)
class LotCreatedEvent(DomainEvent):
    lot_id: TypedId
    property_id: TypedId
    code: str
    name: str
    lot_type: str


@dataclass(frozen=True, slots=True)
class AnimalAddedToLotEvent(DomainEvent):
    lot_id: TypedId
    animal_id: TypedId
    membership_id: TypedId
    valid_from: datetime


@dataclass(frozen=True, slots=True)
class AnimalRemovedFromLotEvent(DomainEvent):
    lot_id: TypedId
    animal_id: TypedId
    membership_id: TypedId
    valid_until: datetime


@dataclass(frozen=True, slots=True)
class VeterinarianRegisteredEvent(DomainEvent):
    veterinarian_id: TypedId
    name: str
    council_number: str
    council_state: str
    verification_status: str


@dataclass(frozen=True, slots=True)
class VeterinarianStatusUpdatedEvent(DomainEvent):
    veterinarian_id: TypedId
    old_status: str
    new_status: str
    evidence_reference: str | None


@dataclass(frozen=True, slots=True)
class MedicationRegisteredEvent(DomainEvent):
    medication_id: TypedId
    trade_name: str
    active_ingredient: str
    withdrawal_period_days: int


@dataclass(frozen=True, slots=True)
class PrescriptionIssuedEvent(DomainEvent):
    prescription_id: TypedId
    veterinarian_id: TypedId
    medication_id: TypedId
    property_id: TypedId
    prescribed_date: datetime
    target_type: str
    target_ids: tuple[TypedId, ...]


@dataclass(frozen=True, slots=True)
class TreatmentAppliedEvent(DomainEvent):
    application_id: TypedId
    animal_id: TypedId
    medication_batch_id: TypedId
    applied_at: datetime
    corrects_application_id: TypedId | None
