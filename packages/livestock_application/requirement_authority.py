"""Assessment transitório de competência de Source por requisito (NEXT-03/Corte 1)."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from packages.shared_kernel import UniversalReference
from packages.shared_kernel.temporal import require_utc

AUTHORITY_TEST_A_POLICY_CODE = "AUTHORITY_TEST_A_v1"
AUTHORITY_TEST_A_PURPOSE = "MARKET_ELIGIBILITY_TEST"
AUTHORITY_TEST_A_REQUIREMENT = "sanitary_attestation"
AUTHORITY_TEST_A_CAPABILITY = "VETERINARY_ATTESTATION"


class RequirementAuthorityOutcome(StrEnum):
    SATISFIED = "SATISFIED"
    NOT_SATISFIED = "NOT_SATISFIED"
    INDETERMINATE = "INDETERMINATE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class RecognitionBoundary(StrEnum):
    INTERNAL_ONLY = "INTERNAL_ONLY"
    EXTERNAL_RECOGNITION_NOT_DEMONSTRATED = "EXTERNAL_RECOGNITION_NOT_DEMONSTRATED"


class SourceCompetenceStatus(StrEnum):
    COMPETENT = "COMPETENT"
    NOT_COMPETENT = "NOT_COMPETENT"
    UNKNOWN = "UNKNOWN"


class RequirementAuthorityValidation(StrEnum):
    VALIDATED = "VALIDATED"
    NOT_VALIDATED = "NOT_VALIDATED"


class RequirementEvidenceAdmissibility(StrEnum):
    ADMISSIBLE = "ADMISSIBLE"
    NOT_ADMISSIBLE = "NOT_ADMISSIBLE"


@dataclass(frozen=True, slots=True)
class SourceCompetenceAssertion:
    """Afirmação delimitada sobre competência de uma Source, sem reconhecimento externo."""

    source_reference: UniversalReference
    requirement_code: str
    purpose: str
    capability_code: str
    status: SourceCompetenceStatus
    valid_from: datetime | None
    valid_until: datetime | None
    known_at: datetime
    authority_basis_references: tuple[UniversalReference, ...]
    evidence_references: tuple[UniversalReference, ...]
    validation: RequirementAuthorityValidation
    admissibility: RequirementEvidenceAdmissibility
    recognition_boundary: RecognitionBoundary
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.source_reference, UniversalReference):
            raise TypeError("source_reference deve ser UniversalReference.")
        for field_name in ("requirement_code", "purpose", "capability_code"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} deve ser texto não vazio.")
        if not isinstance(self.status, SourceCompetenceStatus):
            raise TypeError("status deve ser SourceCompetenceStatus.")
        if not isinstance(self.validation, RequirementAuthorityValidation):
            raise TypeError("validation deve ser RequirementAuthorityValidation.")
        if not isinstance(self.admissibility, RequirementEvidenceAdmissibility):
            raise TypeError("admissibility deve ser RequirementEvidenceAdmissibility.")
        if not isinstance(self.recognition_boundary, RecognitionBoundary):
            raise TypeError("recognition_boundary deve ser RecognitionBoundary.")
        for field_name in ("valid_from", "valid_until", "known_at"):
            value = getattr(self, field_name)
            if value is not None:
                require_utc(value, field_name=field_name)
        if self.valid_from is not None and self.valid_until is not None:
            if self.valid_until <= self.valid_from:
                raise ValueError("valid_until deve ser posterior a valid_from.")
        if not all(
            isinstance(item, UniversalReference) for item in self.authority_basis_references
        ):
            raise TypeError("authority_basis_references deve conter UniversalReference.")
        if not all(isinstance(item, UniversalReference) for item in self.evidence_references):
            raise TypeError("evidence_references deve conter UniversalReference.")
        if any(not isinstance(item, str) or not item.strip() for item in self.limitations):
            raise ValueError("limitations deve conter apenas textos não vazios.")

    def is_valid_at(self, reference_time: datetime) -> bool:
        require_utc(reference_time, field_name="reference_time")
        return (self.valid_from is None or self.valid_from <= reference_time) and (
            self.valid_until is None or reference_time < self.valid_until
        )


@dataclass(frozen=True, slots=True)
class RequirementAuthorityAssessment:
    """Resultado explicável e não persistido da suficiência de Source por requisito."""

    subject_reference: UniversalReference
    policy_code: str
    requirement_code: str
    purpose: str
    reference_time: datetime
    knowledge_cutoff: datetime
    required_capability: str
    source_reference: UniversalReference | None
    authority_basis_references: tuple[UniversalReference, ...]
    evidence_references: tuple[UniversalReference, ...]
    recognition_boundary: RecognitionBoundary
    outcome: RequirementAuthorityOutcome
    limitations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RequirementAuthorityAssessmentService:
    """Compõe competência, Evidence e admissibilidade sem emitir Decision."""

    def assess(
        self,
        *,
        subject_reference: UniversalReference,
        policy_code: str,
        requirement_code: str,
        purpose: str,
        required_capability: str,
        reference_time: datetime,
        knowledge_cutoff: datetime,
        assertions: tuple[SourceCompetenceAssertion, ...],
    ) -> RequirementAuthorityAssessment:
        require_utc(reference_time, field_name="reference_time")
        require_utc(knowledge_cutoff, field_name="knowledge_cutoff")
        if knowledge_cutoff < reference_time:
            raise ValueError("knowledge_cutoff não pode ser anterior a reference_time.")
        for field_name, value in (
            ("policy_code", policy_code),
            ("requirement_code", requirement_code),
            ("purpose", purpose),
            ("required_capability", required_capability),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} deve ser texto não vazio.")

        candidates = tuple(
            item
            for item in assertions
            if item.requirement_code == requirement_code
            and item.purpose == purpose
            and item.capability_code == required_capability
            and item.known_at <= knowledge_cutoff
            and item.is_valid_at(reference_time)
        )
        if not candidates:
            return self._indeterminate(
                subject_reference,
                policy_code,
                requirement_code,
                purpose,
                reference_time,
                knowledge_cutoff,
                required_capability,
                "SOURCE_COMPETENCE_NOT_DEMONSTRATED",
            )

        statuses = {item.status for item in candidates}
        if statuses == {SourceCompetenceStatus.NOT_COMPETENT}:
            return self._from_candidate(
                candidates[0],
                subject_reference,
                policy_code,
                reference_time,
                knowledge_cutoff,
                required_capability,
                RequirementAuthorityOutcome.NOT_SATISFIED,
                ("SOURCE_EXPLICITLY_NOT_COMPETENT",),
            )
        if len(candidates) != 1 or statuses != {SourceCompetenceStatus.COMPETENT}:
            return self._from_candidate(
                candidates[0],
                subject_reference,
                policy_code,
                reference_time,
                knowledge_cutoff,
                required_capability,
                RequirementAuthorityOutcome.INDETERMINATE,
                ("SOURCE_COMPETENCE_AMBIGUOUS_OR_UNKNOWN",),
            )

        candidate = candidates[0]
        limitations = list(candidate.limitations)
        if not candidate.authority_basis_references:
            limitations.append("SOURCE_COMPETENCE_BASIS_ABSENT")
        if not candidate.evidence_references:
            limitations.append("SOURCE_COMPETENCE_EVIDENCE_ABSENT")
        if candidate.validation is not RequirementAuthorityValidation.VALIDATED:
            limitations.append("SOURCE_COMPETENCE_NOT_VALIDATED")
        if candidate.admissibility is not RequirementEvidenceAdmissibility.ADMISSIBLE:
            limitations.append("SOURCE_COMPETENCE_NOT_ADMISSIBLE")
        if candidate.recognition_boundary is not RecognitionBoundary.INTERNAL_ONLY:
            limitations.append("EXTERNAL_RECOGNITION_NOT_DEMONSTRATED")
        outcome = (
            RequirementAuthorityOutcome.SATISFIED
            if not limitations
            else RequirementAuthorityOutcome.INDETERMINATE
        )
        return self._from_candidate(
            candidate,
            subject_reference,
            policy_code,
            reference_time,
            knowledge_cutoff,
            required_capability,
            outcome,
            tuple(dict.fromkeys(limitations)),
        )

    @staticmethod
    def _indeterminate(
        subject_reference: UniversalReference,
        policy_code: str,
        requirement_code: str,
        purpose: str,
        reference_time: datetime,
        knowledge_cutoff: datetime,
        required_capability: str,
        limitation: str,
    ) -> RequirementAuthorityAssessment:
        return RequirementAuthorityAssessment(
            subject_reference,
            policy_code,
            requirement_code,
            purpose,
            reference_time,
            knowledge_cutoff,
            required_capability,
            None,
            (),
            (),
            RecognitionBoundary.INTERNAL_ONLY,
            RequirementAuthorityOutcome.INDETERMINATE,
            (limitation,),
        )

    @staticmethod
    def _from_candidate(
        candidate: SourceCompetenceAssertion,
        subject_reference: UniversalReference,
        policy_code: str,
        reference_time: datetime,
        knowledge_cutoff: datetime,
        required_capability: str,
        outcome: RequirementAuthorityOutcome,
        limitations: tuple[str, ...],
    ) -> RequirementAuthorityAssessment:
        return RequirementAuthorityAssessment(
            subject_reference,
            policy_code,
            candidate.requirement_code,
            candidate.purpose,
            reference_time,
            knowledge_cutoff,
            required_capability,
            candidate.source_reference,
            candidate.authority_basis_references,
            candidate.evidence_references,
            candidate.recognition_boundary,
            outcome,
            limitations,
        )
