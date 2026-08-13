"""Registro e seleção segura de classificação sanitária de medicamentos."""

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Protocol

from packages.core_domain.evidence import ConfidenceTier
from packages.livestock_application.event_recorder import LivestockOperationContext
from packages.livestock_application.medication_service import MedicationRepositoryPort
from packages.livestock_domain.medication_classification import (
    MedicationClassificationStatus,
    MedicationClassificationValidation,
    MedicationSanitaryCategory,
    MedicationSanitaryClassificationAssertion,
)
from packages.shared_kernel import OrganizationId, TypedId


class MedicationClassificationRepositoryPort(Protocol):
    def save(self, assertion: MedicationSanitaryClassificationAssertion) -> None: ...
    def list_by_medication(
        self, organization_id: OrganizationId, medication_id: TypedId
    ) -> list[MedicationSanitaryClassificationAssertion]: ...


@dataclass(frozen=True, slots=True)
class MedicationClassificationService:
    repository: MedicationClassificationRepositoryPort
    medication_repository: MedicationRepositoryPort

    def record(
        self,
        *,
        context: LivestockOperationContext,
        medication_id: TypedId,
        status: MedicationClassificationStatus,
        valid_from: datetime | None,
        valid_to: datetime | None,
        observed_at: datetime,
        known_at: datetime,
        limitations: tuple[str, ...] = (),
    ) -> MedicationSanitaryClassificationAssertion:
        medication = self.medication_repository.get_by_id(medication_id)
        if medication is None or medication.organization_id != context.organization_id:
            raise KeyError("Medicamento não encontrado nesta Organization.")
        item = MedicationSanitaryClassificationAssertion(
            assertion_id=TypedId.new("medication_classification_assertion"),
            organization_id=context.organization_id,
            medication_id=medication_id,
            category=MedicationSanitaryCategory.ANTIMICROBIAL,
            status=status,
            valid_from=valid_from,
            valid_to=valid_to,
            observed_at=observed_at,
            source_reference=context.source_reference,
            validation_status=MedicationClassificationValidation.STRUCTURALLY_VALIDATED,
            confidence_tier=ConfidenceTier.DOCUMENTED,
            limitations=tuple(value.strip() for value in limitations if value.strip()),
            known_at=known_at,
        )
        self.repository.save(item)
        return item

    def select(
        self,
        *,
        organization_id: OrganizationId,
        medication_id: TypedId,
        reference_time: datetime,
        knowledge_cutoff: datetime,
    ) -> MedicationSanitaryClassificationAssertion | None:
        candidates = [
            item
            for item in self.repository.list_by_medication(organization_id, medication_id)
            if item.category is MedicationSanitaryCategory.ANTIMICROBIAL
            and item.known_as_of(knowledge_cutoff)
            and item.valid_at(reference_time)
        ]
        if not candidates:
            return None
        statuses = {item.status for item in candidates}
        if len(statuses) > 1:
            latest = max(candidates, key=lambda item: item.observed_at)
            return replace(
                latest,
                status=MedicationClassificationStatus.UNKNOWN,
                limitations=latest.limitations + ("MEDICATION_CLASSIFICATION_CONFLICT",),
            )
        return max(candidates, key=lambda item: item.observed_at)
