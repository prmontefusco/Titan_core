"""Módulo de infraestrutura do Titan Livestock."""

from packages.livestock_infrastructure.persistence.animal_repository import (
    TransactionalAnimalRepository,
    animal_identifiers_table,
    animals_table,
)
from packages.livestock_infrastructure.persistence.coverage_contribution_repository import (
    TransactionalCoverageContributionRepository,
    coverage_contributions_table,
)
from packages.livestock_infrastructure.persistence.establishment_qualification_repository import (
    TransactionalEstablishmentQualificationRepository,
    establishment_qualifications_table,
)
from packages.livestock_infrastructure.persistence.exit_repository import (
    TransactionalAnimalExitRepository,
    animal_exits_table,
)
from packages.livestock_infrastructure.persistence.external_counterparty_repository import (
    TransactionalExternalCounterpartyRepository,
    external_counterparties_table,
)
from packages.livestock_infrastructure.persistence.geometry_repository import (
    TransactionalPropertyGeometryRepository,
    property_geometries_table,
)
from packages.livestock_infrastructure.persistence.imported_fact_repository import (
    TransactionalImportedLivestockFactRepository,
    imported_livestock_facts_table,
)
from packages.livestock_infrastructure.persistence.lot_repository import (
    TransactionalLivestockLotRepository,
    TransactionalLotMembershipRepository,
    livestock_lots_table,
    lot_memberships_table,
)
from packages.livestock_infrastructure.persistence.medication_classification_repository import (
    TransactionalMedicationClassificationRepository,
    medication_classification_assertions_table,
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
from packages.livestock_infrastructure.persistence.qualification_assertion_repository import (
    TransactionalEstablishmentQualificationAssertionRepository,
    TransactionalQualificationSourceArtifactRepository,
    establishment_qualification_assertions_table,
    qualification_source_artifacts_table,
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
from packages.livestock_infrastructure.persistence.transfer_artifact_repository import (
    TransactionalReceivedTransferArtifactRepository,
    received_transfer_artifacts_table,
)
from packages.livestock_infrastructure.persistence.transformation_repository import (
    TransactionalTraceableItemRepository,
    TransactionalTransformationEventRepository,
    traceable_items_table,
    transformation_events_table,
)
from packages.livestock_infrastructure.persistence.treatment_repository import (
    TransactionalTreatmentApplicationRepository,
    treatment_applications_table,
)
from packages.livestock_infrastructure.persistence.veterinarian_repository import (
    TransactionalVeterinarianRepository,
    veterinarians_table,
)

from .entity_type_request_grant import TransactionalMembershipGrant
from .entity_type_request_repository import (
    TransactionalEntityTypeRequestRepository,
    entity_type_requests_table,
)
from .environmental_embargo_assertion_repository import (
    TransactionalPropertyEnvironmentalEmbargoAssertionRepository,
    property_environmental_embargo_assertions_table,
)

__all__ = [
    "TransactionalEntityTypeRequestRepository",
    "TransactionalCoverageContributionRepository",
    "TransactionalMembershipGrant",
    "TransactionalAnimalMovementRepository",
    "TransactionalAnimalRepository",
    "TransactionalLivestockLotRepository",
    "TransactionalLotMembershipRepository",
    "TransactionalMedicationBatchRepository",
    "TransactionalMedicationRepository",
    "TransactionalMedicationClassificationRepository",
    "TransactionalPrescriptionRepository",
    "TransactionalPropertyStayRepository",
    "TransactionalRuralPropertyRepository",
    "TransactionalAnimalExitRepository",
    "TransactionalExternalCounterpartyRepository",
    "TransactionalEstablishmentQualificationRepository",
    "TransactionalPropertyEnvironmentalEmbargoAssertionRepository",
    "TransactionalImportedLivestockFactRepository",
    "TransactionalPropertyGeometryRepository",
    "TransactionalReproductiveEventRepository",
    "TransactionalSanitaryCampaignRepository",
    "TransactionalQualificationSourceArtifactRepository",
    "TransactionalEstablishmentQualificationAssertionRepository",
    "entity_type_requests_table",
    "qualification_source_artifacts_table",
    "establishment_qualification_assertions_table",
    "property_environmental_embargo_assertions_table",
    "property_geometries_table",
    "reproductive_event_offspring_table",
    "reproductive_events_table",
    "sanitary_campaigns_table",
    "TransactionalTreatmentApplicationRepository",
    "TransactionalReceivedTransferArtifactRepository",
    "TransactionalTraceableItemRepository",
    "TransactionalTransformationEventRepository",
    "traceable_items_table",
    "transformation_events_table",
    "TransactionalVeterinarianRepository",
    "animal_identifiers_table",
    "coverage_contributions_table",
    "animal_movement_items_table",
    "animal_movements_table",
    "animals_table",
    "livestock_lots_table",
    "lot_memberships_table",
    "medication_batches_table",
    "medications_table",
    "medication_classification_assertions_table",
    "prescription_targets_table",
    "prescriptions_table",
    "property_stays_table",
    "rural_properties_table",
    "animal_exits_table",
    "external_counterparties_table",
    "establishment_qualifications_table",
    "imported_livestock_facts_table",
    "treatment_applications_table",
    "received_transfer_artifacts_table",
    "veterinarians_table",
]
