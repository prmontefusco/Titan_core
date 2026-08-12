"""Classificação sanitária factual e bitemporal de medicamento (ADR-0056)."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from packages.core_domain.evidence import ConfidenceTier
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference
from packages.shared_kernel.temporal import require_utc


class MedicationSanitaryCategory(StrEnum):
    ANTIMICROBIAL = "ANTIMICROBIAL"


class MedicationClassificationStatus(StrEnum):
    APPLIES = "APPLIES"
    DOES_NOT_APPLY = "DOES_NOT_APPLY"
    UNKNOWN = "UNKNOWN"


class MedicationClassificationValidation(StrEnum):
    STRUCTURALLY_VALIDATED = "STRUCTURALLY_VALIDATED"
    NOT_VALIDATED = "NOT_VALIDATED"


@dataclass(frozen=True, slots=True)
class MedicationSanitaryClassificationAssertion:
    assertion_id: TypedId
    organization_id: OrganizationId
    medication_id: TypedId
    category: MedicationSanitaryCategory
    status: MedicationClassificationStatus
    valid_from: datetime | None
    valid_to: datetime | None
    observed_at: datetime
    source_reference: UniversalReference
    validation_status: MedicationClassificationValidation
    confidence_tier: ConfidenceTier
    limitations: tuple[str, ...] = ()
    recorded_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        require_utc(self.observed_at, field_name="observed_at")
        require_utc(self.recorded_at, field_name="recorded_at")
        if self.valid_from is not None:
            require_utc(self.valid_from, field_name="valid_from")
        if self.valid_to is not None:
            require_utc(self.valid_to, field_name="valid_to")
        if self.valid_from and self.valid_to and self.valid_from >= self.valid_to:
            raise ValueError("valid_from deve ser anterior a valid_to.")
        if self.assertion_id.entity_type != "medication_classification_assertion":
            raise ValueError("assertion_id possui tipo incorreto.")
        if self.medication_id.entity_type != "medication":
            raise ValueError("medication_id deve ser medication.")
        if self.source_reference.organization_id != self.organization_id:
            raise ValueError("source_reference pertence a outra Organization.")

    def known_as_of(self, cutoff: datetime) -> bool:
        require_utc(cutoff, field_name="knowledge_cutoff")
        return self.observed_at <= cutoff

    def valid_at(self, instant: datetime) -> bool:
        require_utc(instant, field_name="reference_time")
        return (self.valid_from is None or self.valid_from <= instant) and (
            self.valid_to is None or instant < self.valid_to
        )
