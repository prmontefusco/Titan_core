"""Módulo de domínio do Titan Livestock."""

from packages.livestock_domain.animal import (
    Animal,
    AnimalIdentifier,
    AnimalSex,
    IdentifierState,
    IdentifierType,
    VerificationStatus,
)
from packages.livestock_domain.events import (
    ANIMAL_ADDED_TO_LOT,
    ANIMAL_MOVED,
    ANIMAL_REGISTERED,
    ANIMAL_REMOVED_FROM_LOT,
    IDENTIFIER_ATTACHED,
    IDENTIFIER_DEACTIVATED,
    LIVESTOCK_EVENT_TYPES,
    LOT_CREATED,
    MEDICATION_BATCH_REGISTERED,
    MEDICATION_REGISTERED,
    PRESCRIPTION_ISSUED,
    PROPERTY_REGISTERED,
    TREATMENT_APPLIED,
    VETERINARIAN_REGISTERED,
    VETERINARIAN_STATUS_UPDATED,
)
from packages.livestock_domain.lot import (
    LivestockLot,
    LotMembership,
    LotStatus,
    LotType,
)
from packages.livestock_domain.medication import Medication
from packages.livestock_domain.movement import (
    AnimalMovement,
    PropertyStay,
    StayStatus,
)
from packages.livestock_domain.prescription import Prescription, PrescriptionTargetType
from packages.livestock_domain.property import RuralProperty
from packages.livestock_domain.veterinarian import Veterinarian

__all__ = [
    "ANIMAL_ADDED_TO_LOT",
    "ANIMAL_MOVED",
    "ANIMAL_REGISTERED",
    "ANIMAL_REMOVED_FROM_LOT",
    "IDENTIFIER_ATTACHED",
    "IDENTIFIER_DEACTIVATED",
    "LIVESTOCK_EVENT_TYPES",
    "LOT_CREATED",
    "MEDICATION_BATCH_REGISTERED",
    "MEDICATION_REGISTERED",
    "PRESCRIPTION_ISSUED",
    "PROPERTY_REGISTERED",
    "TREATMENT_APPLIED",
    "VETERINARIAN_REGISTERED",
    "VETERINARIAN_STATUS_UPDATED",
    "Animal",
    "AnimalIdentifier",
    "AnimalMovement",
    "AnimalSex",
    "IdentifierState",
    "IdentifierType",
    "LivestockLot",
    "LotMembership",
    "LotStatus",
    "LotType",
    "Medication",
    "Prescription",
    "PrescriptionTargetType",
    "PropertyStay",
    "RuralProperty",
    "StayStatus",
    "VerificationStatus",
    "Veterinarian",
]
