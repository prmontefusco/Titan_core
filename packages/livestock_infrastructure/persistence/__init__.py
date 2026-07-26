"""Módulo de infraestrutura do Titan Livestock."""

from packages.livestock_infrastructure.persistence.animal_repository import (
    TransactionalAnimalRepository,
    animal_identifiers_table,
    animals_table,
)
from packages.livestock_infrastructure.persistence.exit_repository import (
    TransactionalAnimalExitRepository,
    animal_exits_table,
)
from packages.livestock_infrastructure.persistence.geometry_repository import (
    TransactionalPropertyGeometryRepository,
    property_geometries_table,
)
from packages.livestock_infrastructure.persistence.lot_repository import (
    TransactionalLivestockLotRepository,
    TransactionalLotMembershipRepository,
    livestock_lots_table,
    lot_memberships_table,
)
from packages.livestock_infrastructure.persistence.medication_repository import (
    TransactionalMedicationBatchRepository,
    TransactionalMedicationRepository,
    TransactionalPrescriptionRepository,
    medication_batches_table,
    medications_table,
    prescription_targets_table,
    prescriptions_table,
)
from packages.livestock_infrastructure.persistence.movement_repository import (
    TransactionalAnimalMovementRepository,
    TransactionalPropertyStayRepository,
    animal_movement_items_table,
    animal_movements_table,
    property_stays_table,
)
from packages.livestock_infrastructure.persistence.property_repository import (
    TransactionalRuralPropertyRepository,
    rural_properties_table,
)
from packages.livestock_infrastructure.persistence.reproduction_repository import (
    TransactionalReproductiveEventRepository,
    reproductive_event_offspring_table,
    reproductive_events_table,
)
from packages.livestock_infrastructure.persistence.sanitary_campaign_repository import (
    TransactionalSanitaryCampaignRepository,
    sanitary_campaigns_table,
)
from packages.livestock_infrastructure.persistence.treatment_repository import (
    TransactionalTreatmentApplicationRepository,
    treatment_applications_table,
)
from packages.livestock_infrastructure.persistence.veterinarian_repository import (
    TransactionalVeterinarianRepository,
    veterinarians_table,
)

__all__ = [
    "TransactionalAnimalMovementRepository",
    "TransactionalAnimalRepository",
    "TransactionalLivestockLotRepository",
    "TransactionalLotMembershipRepository",
    "TransactionalMedicationBatchRepository",
    "TransactionalMedicationRepository",
    "TransactionalPrescriptionRepository",
    "TransactionalPropertyStayRepository",
    "TransactionalRuralPropertyRepository",
    "TransactionalAnimalExitRepository",
    "TransactionalPropertyGeometryRepository",
    "TransactionalReproductiveEventRepository",
    "TransactionalSanitaryCampaignRepository",
    "property_geometries_table",
    "reproductive_event_offspring_table",
    "reproductive_events_table",
    "sanitary_campaigns_table",
    "TransactionalTreatmentApplicationRepository",
    "TransactionalVeterinarianRepository",
    "animal_identifiers_table",
    "animal_movement_items_table",
    "animal_movements_table",
    "animals_table",
    "livestock_lots_table",
    "lot_memberships_table",
    "medication_batches_table",
    "medications_table",
    "prescription_targets_table",
    "prescriptions_table",
    "property_stays_table",
    "rural_properties_table",
    "animal_exits_table",
    "treatment_applications_table",
    "veterinarians_table",
]
