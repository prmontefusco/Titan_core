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
    ANIMAL_EXITED,
    ANIMAL_MOVED,
    ANIMAL_REGISTERED,
    ANIMAL_REMOVED_FROM_LOT,
    EXTERNAL_COUNTERPARTY_REGISTERED,
    IDENTIFIER_ATTACHED,
    IDENTIFIER_DEACTIVATED,
    IMPORTED_FACT_RECORDED,
    LIVESTOCK_EVENT_TYPES,
    LOT_CREATED,
    MEDICATION_BATCH_REGISTERED,
    MEDICATION_REGISTERED,
    PARENTAGE_REGISTERED,
    PRESCRIPTION_ISSUED,
    PROPERTY_REGISTERED,
    SANITARY_CAMPAIGN_REGISTERED,
    TRANSFER_ARTIFACT_RECEIVED,
    TREATMENT_APPLIED,
    VETERINARIAN_REGISTERED,
    VETERINARIAN_STATUS_UPDATED,
)
from packages.livestock_domain.exit import AnimalExit, ExitType
from packages.livestock_domain.external_counterparty import CounterpartyType, ExternalCounterparty
from packages.livestock_domain.imported_fact import FactOrigin, ImportedLivestockFact
from packages.livestock_domain.lot import (
    LivestockLot,
    LotMembership,
    LotStatus,
    LotType,
)
from packages.livestock_domain.medication import Medication, MedicationProductClass
from packages.livestock_domain.movement import (
    AnimalMovement,
    PropertyStay,
    StayStatus,
)
from packages.livestock_domain.parentage import ParentageConfidence, ParentageRole
from packages.livestock_domain.prescription import Prescription, PrescriptionTargetType
from packages.livestock_domain.property import RuralProperty
from packages.livestock_domain.sanitary_campaign import SanitaryCampaign
from packages.livestock_domain.transfer_artifact import (
    HistoryCoverage,
    ReceivedTransferArtifact,
    TransferArtifactGap,
    TransferArtifactGapCode,
)
from packages.livestock_domain.veterinarian import Veterinarian

__all__ = [
    "ANIMAL_ADDED_TO_LOT",
    "ANIMAL_EXITED",
    "ANIMAL_MOVED",
    "ANIMAL_REGISTERED",
    "ANIMAL_REMOVED_FROM_LOT",
    "EXTERNAL_COUNTERPARTY_REGISTERED",
    "IDENTIFIER_ATTACHED",
    "IDENTIFIER_DEACTIVATED",
    "IMPORTED_FACT_RECORDED",
    "LIVESTOCK_EVENT_TYPES",
    "LOT_CREATED",
    "MEDICATION_BATCH_REGISTERED",
    "MEDICATION_REGISTERED",
    "PARENTAGE_REGISTERED",
    "PRESCRIPTION_ISSUED",
    "PROPERTY_REGISTERED",
    "SANITARY_CAMPAIGN_REGISTERED",
    "TREATMENT_APPLIED",
    "TRANSFER_ARTIFACT_RECEIVED",
    "VETERINARIAN_REGISTERED",
    "VETERINARIAN_STATUS_UPDATED",
    "Animal",
    "AnimalExit",
    "AnimalIdentifier",
    "AnimalMovement",
    "AnimalSex",
    "ExitType",
    "ExternalCounterparty",
    "FactOrigin",
    "IdentifierState",
    "IdentifierType",
    "ImportedLivestockFact",
    "LivestockLot",
    "LotMembership",
    "LotStatus",
    "LotType",
    "Medication",
    "MedicationProductClass",
    "CounterpartyType",
    "ParentageConfidence",
    "ParentageRole",
    "Prescription",
    "PrescriptionTargetType",
    "PropertyStay",
    "RuralProperty",
    "HistoryCoverage",
    "ReceivedTransferArtifact",
    "SanitaryCampaign",
    "StayStatus",
    "TransferArtifactGap",
    "TransferArtifactGapCode",
    "VerificationStatus",
    "Veterinarian",
]
