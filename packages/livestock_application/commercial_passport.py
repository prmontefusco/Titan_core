"""Commercial Passport application contracts for Titan Livestock.

F1-F5 are deliberately application-only: these types compose existing
evaluations, decisions and readiness outputs, but do not evaluate policies,
emit Decisions, persist snapshots, expose APIs or create Dossiers/
VerificationBundles.
"""

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Protocol

from packages.core_domain.dossier import VerticalSection
from packages.livestock_application.market_readiness import (
    MARKET_ELIGIBILITY_RESULT_BOUNDARY,
    MarketReadinessStatus,
)
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference
from packages.shared_kernel.temporal import require_utc

PROPERTY_COMMERCIAL_PASSPORT_LIMITATIONS = (
    "PROPERTY_COMMERCIAL_PASSPORT_IS_DYNAMIC_PROJECTION",
    "POPULATION_ELIGIBILITY_IS_SEPARATE_FROM_PROPERTY_READINESS",
    "FORMAL_ISSUANCE_REQUIRES_DOSSIER_OR_VERIFICATION_BUNDLE",
)
LIVESTOCK_COMMERCIAL_PASSPORT_SECTION_VERSION = 1


class CommercialOpportunityKind(StrEnum):
    MARKET = "MARKET"
    ECONOMIC_BLOCK = "ECONOMIC_BLOCK"
    BUYER = "BUYER"
    PROGRAM = "PROGRAM"
    CERTIFICATION = "CERTIFICATION"
    PRIVATE_PROTOCOL = "PRIVATE_PROTOCOL"
    DELIVERY_WINDOW = "DELIVERY_WINDOW"
    LOGISTICS = "LOGISTICS"


class CommercialPassportRequirementDimension(StrEnum):
    PROPERTY_READINESS = "PROPERTY_READINESS"
    POPULATION_ELIGIBILITY = "POPULATION_ELIGIBILITY"


class CommercialPassportRequirementStatus(StrEnum):
    SATISFIED = "SATISFIED"
    MISSING = "MISSING"
    UNKNOWN = "UNKNOWN"
    FAILED = "FAILED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    BLOCKED = "BLOCKED"

    @property
    def semantic_description(self) -> str:
        return _REQUIREMENT_STATUS_DESCRIPTIONS[self]

    @property
    def applies_to_readiness_denominator(self) -> bool:
        return self is not CommercialPassportRequirementStatus.NOT_APPLICABLE

    @property
    def is_missing_evidence(self) -> bool:
        return self is CommercialPassportRequirementStatus.MISSING

    @property
    def is_unknown(self) -> bool:
        return self is CommercialPassportRequirementStatus.UNKNOWN

    @property
    def is_failed(self) -> bool:
        return self is CommercialPassportRequirementStatus.FAILED

    @property
    def blocks_opportunity(self) -> bool:
        return self is CommercialPassportRequirementStatus.BLOCKED


_REQUIREMENT_STATUS_DESCRIPTIONS: Mapping[CommercialPassportRequirementStatus, str] = {
    CommercialPassportRequirementStatus.SATISFIED: (
        "Requirement applies and is satisfied by the assessed material."
    ),
    CommercialPassportRequirementStatus.MISSING: (
        "Required evidence or data was not supplied or is absent from known material."
    ),
    CommercialPassportRequirementStatus.UNKNOWN: (
        "Titan cannot conclude with available knowledge; this is not false."
    ),
    CommercialPassportRequirementStatus.FAILED: (
        "Requirement applies, was evaluated and was not satisfied."
    ),
    CommercialPassportRequirementStatus.NOT_APPLICABLE: (
        "Requirement does not apply to this subject or context and does not reduce readiness."
    ),
    CommercialPassportRequirementStatus.BLOCKED: (
        "A current blocking condition prevents the opportunity regardless of other readiness."
    ),
}


class CommercialReadinessInterpretation(StrEnum):
    AVAILABLE = "AVAILABLE"
    PARTIALLY_READY = "PARTIALLY_READY"
    UNAVAILABLE_BLOCKED = "UNAVAILABLE_BLOCKED"
    UNAVAILABLE_FAILED = "UNAVAILABLE_FAILED"
    UNKNOWN = "UNKNOWN"
    NOT_ASSESSED = "NOT_ASSESSED"


@dataclass(frozen=True, slots=True)
class CommercialPassportContext:
    organization_id: OrganizationId
    property_id: TypedId
    reference_time: datetime
    knowledge_cutoff: datetime
    evaluated_at: datetime
    result_boundary: str = MARKET_ELIGIBILITY_RESULT_BOUNDARY

    def __post_init__(self) -> None:
        if self.property_id.entity_type not in {"property", "rural_property"}:
            raise ValueError("property_id deve ter entity_type 'property' ou 'rural_property'.")
        require_utc(self.reference_time, field_name="reference_time")
        require_utc(self.knowledge_cutoff, field_name="knowledge_cutoff")
        require_utc(self.evaluated_at, field_name="evaluated_at")
        if self.knowledge_cutoff < self.reference_time:
            raise ValueError("knowledge_cutoff nao pode ser anterior a reference_time.")
        if not self.result_boundary.strip():
            raise ValueError("result_boundary deve ser texto nao vazio.")


@dataclass(frozen=True, slots=True)
class CommercialOpportunity:
    code: str
    kind: CommercialOpportunityKind
    name: str
    purpose: str
    policy_id: TypedId
    policy_version: int
    effective_from: datetime | None = None
    effective_until: datetime | None = None

    def __post_init__(self) -> None:
        for field_name in ("code", "name", "purpose"):
            if not getattr(self, field_name).strip():
                raise ValueError(f"{field_name} deve ser texto nao vazio.")
        if self.policy_id.entity_type != "policy":
            raise ValueError("policy_id deve ter entity_type 'policy'.")
        if self.policy_version < 1:
            raise ValueError("policy_version deve ser inteiro >= 1.")
        if self.effective_from is not None:
            require_utc(self.effective_from, field_name="effective_from")
        if self.effective_until is not None:
            require_utc(self.effective_until, field_name="effective_until")
        if (
            self.effective_from is not None
            and self.effective_until is not None
            and self.effective_until <= self.effective_from
        ):
            raise ValueError("effective_until deve ser posterior a effective_from.")


@dataclass(frozen=True, slots=True)
class CommercialRequirementAssessment:
    requirement_code: str
    label: str
    dimension: CommercialPassportRequirementDimension
    status: CommercialPassportRequirementStatus
    reason: str
    reason_codes: tuple[str, ...] = ()
    evidence_references: tuple[UniversalReference, ...] = ()
    evaluation_id: TypedId | None = None
    decision_id: TypedId | None = None
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in ("requirement_code", "label", "reason"):
            if not getattr(self, field_name).strip():
                raise ValueError(f"{field_name} deve ser texto nao vazio.")
        if self.evaluation_id is not None and self.evaluation_id.entity_type != "evaluation":
            raise ValueError("evaluation_id deve ter entity_type 'evaluation'.")
        if self.decision_id is not None and self.decision_id.entity_type != "decision":
            raise ValueError("decision_id deve ter entity_type 'decision'.")
        _require_text_tuple(self.reason_codes, "reason_codes")
        _require_text_tuple(self.limitations, "limitations")

    @property
    def applies_to_readiness_denominator(self) -> bool:
        return self.status.applies_to_readiness_denominator

    @property
    def blocks_opportunity(self) -> bool:
        return self.status.blocks_opportunity


@dataclass(frozen=True, slots=True)
class CommercialReadinessBreakdown:
    satisfied: int = 0
    missing: int = 0
    unknown: int = 0
    failed: int = 0
    not_applicable: int = 0
    blocked: int = 0

    @property
    def applicable_count(self) -> int:
        return self.satisfied + self.missing + self.unknown + self.failed + self.blocked

    @property
    def total_count(self) -> int:
        return self.applicable_count + self.not_applicable

    @property
    def has_blocker(self) -> bool:
        return self.blocked > 0

    @property
    def derived_ratio(self) -> float | None:
        """Secondary projection: satisfied/applicable, never a Decision."""
        if self.applicable_count == 0:
            return None
        return self.satisfied / self.applicable_count

    @property
    def interpretation(self) -> CommercialReadinessInterpretation:
        """Operational interpretation of requirement counts; not a Decision."""
        if self.applicable_count == 0:
            return CommercialReadinessInterpretation.NOT_ASSESSED
        if self.blocked > 0:
            return CommercialReadinessInterpretation.UNAVAILABLE_BLOCKED
        if self.failed > 0:
            return CommercialReadinessInterpretation.UNAVAILABLE_FAILED
        if self.unknown > 0:
            return CommercialReadinessInterpretation.UNKNOWN
        if self.missing > 0:
            return CommercialReadinessInterpretation.PARTIALLY_READY
        return CommercialReadinessInterpretation.AVAILABLE


@dataclass(frozen=True, slots=True)
class PropertyCommercialReadiness:
    requirements: tuple[CommercialRequirementAssessment, ...]
    breakdown: CommercialReadinessBreakdown = field(init=False)

    def __post_init__(self) -> None:
        _ensure_unique_requirement_codes(self.requirements)
        invalid = [
            item.requirement_code
            for item in self.requirements
            if item.dimension is not CommercialPassportRequirementDimension.PROPERTY_READINESS
        ]
        if invalid:
            raise ValueError("Property readiness aceita somente requisitos de propriedade.")
        object.__setattr__(self, "breakdown", _breakdown(self.requirements))


@dataclass(frozen=True, slots=True)
class PopulationEligibilitySummary:
    subject_type: str
    counts_by_status: Mapping[str, int]
    limitations: tuple[str, ...] = ()
    source_report_reference: str = ""

    def __post_init__(self) -> None:
        if self.subject_type not in {"animal", "lot", "population"}:
            raise ValueError("subject_type deve ser 'animal', 'lot' ou 'population'.")
        if any(not key.strip() or value < 0 for key, value in self.counts_by_status.items()):
            raise ValueError("counts_by_status exige codigos nao vazios e contagens >= 0.")
        _require_text_tuple(self.limitations, "limitations")
        object.__setattr__(self, "counts_by_status", MappingProxyType(dict(self.counts_by_status)))

    @property
    def total_count(self) -> int:
        return sum(self.counts_by_status.values())

    @property
    def ready_count(self) -> int:
        return self.counts_by_status.get(MarketReadinessStatus.READY.value, 0)

    @property
    def not_ready_count(self) -> int:
        return self.counts_by_status.get(MarketReadinessStatus.NOT_READY.value, 0)

    @property
    def conditioned_count(self) -> int:
        return self.counts_by_status.get(MarketReadinessStatus.CONDITIONED.value, 0)

    @property
    def indeterminate_count(self) -> int:
        return self.counts_by_status.get(MarketReadinessStatus.INDETERMINATE.value, 0)

    @property
    def reassessment_required_count(self) -> int:
        return self.counts_by_status.get(MarketReadinessStatus.REASSESSMENT_REQUIRED.value, 0)

    @property
    def not_evaluated_count(self) -> int:
        return self.counts_by_status.get(MarketReadinessStatus.NOT_EVALUATED.value, 0)


@dataclass(frozen=True, slots=True)
class CommercialPassportOpportunityAssessment:
    opportunity: CommercialOpportunity
    property_readiness: PropertyCommercialReadiness
    population_eligibility: PopulationEligibilitySummary | None = None
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_text_tuple(self.limitations, "limitations")

    @property
    def has_blocker(self) -> bool:
        return self.property_readiness.breakdown.has_blocker


@dataclass(frozen=True, slots=True)
class CommercialPassport:
    """Dynamic Commercial Passport projection.

    This is not a Decision, not MarketEligibility and not an issued snapshot.
    """

    context: CommercialPassportContext
    opportunities: tuple[CommercialPassportOpportunityAssessment, ...]
    limitations: tuple[str, ...] = (
        "COMMERCIAL_PASSPORT_IS_DYNAMIC_PROJECTION",
        "COMMERCIAL_PASSPORT_IS_NOT_DECISION",
        "COMMERCIAL_PASSPORT_IS_NOT_MARKET_ELIGIBILITY",
        "FORMAL_DISCLOSURE_REQUIRES_ISSUED_SNAPSHOT",
    )

    def __post_init__(self) -> None:
        if not self.opportunities:
            raise ValueError("CommercialPassport exige ao menos uma oportunidade.")
        codes = [item.opportunity.code for item in self.opportunities]
        if len(set(codes)) != len(codes):
            raise ValueError("CommercialPassport nao aceita oportunidade duplicada.")
        _require_text_tuple(self.limitations, "limitations")


@dataclass(frozen=True, slots=True)
class PropertyCommercialPassportOpportunityInput:
    """Application input for one property opportunity in the dynamic passport."""

    opportunity: CommercialOpportunity
    requirements: tuple[CommercialRequirementAssessment, ...]
    population_eligibility: PopulationEligibilitySummary | None = None
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.requirements, tuple):
            raise TypeError("requirements deve ser tuple.")
        _require_text_tuple(self.limitations, "limitations")


class PropertyCommercialPassportService:
    """Build the dynamic property passport projection.

    This service composes already-derived requirement assessments. It does not
    resolve facts, evaluate Policy, emit Decision, derive population eligibility,
    issue snapshots or authorize external disclosure.
    """

    def build(
        self,
        *,
        context: CommercialPassportContext,
        opportunities: tuple[PropertyCommercialPassportOpportunityInput, ...],
    ) -> CommercialPassport:
        if not opportunities:
            raise ValueError("Property Commercial Passport exige ao menos uma oportunidade.")
        assessments = tuple(
            CommercialPassportOpportunityAssessment(
                opportunity=item.opportunity,
                property_readiness=PropertyCommercialReadiness(requirements=item.requirements),
                population_eligibility=item.population_eligibility,
                limitations=item.limitations,
            )
            for item in sorted(opportunities, key=lambda item: item.opportunity.code)
        )
        return CommercialPassport(
            context=context,
            opportunities=assessments,
            limitations=PROPERTY_COMMERCIAL_PASSPORT_LIMITATIONS,
        )


class PropertyCommercialPassportProjectionPort(Protocol):
    """Builds a dynamic Property Commercial Passport from productive sources."""

    def build_property_passport(
        self,
        *,
        context: CommercialPassportContext,
    ) -> CommercialPassport: ...


@dataclass(frozen=True, slots=True)
class CommercialPassportDossierSectionBuilder:
    """Build a Livestock vertical section for formal Commercial Passport issuance.

    The section is designed to travel inside the existing Core Dossier and
    VerificationBundle. It freezes the dynamic passport projection supplied by
    the caller; it does not create a new Decision, re-evaluate policies, persist
    anything or disclose cross-tenant data by itself.
    """

    def build(self, *, passport: CommercialPassport, issued_at: datetime) -> VerticalSection:
        require_utc(issued_at, field_name="issued_at")
        if issued_at < passport.context.evaluated_at:
            raise ValueError("issued_at nao pode ser anterior a evaluated_at.")
        return VerticalSection(
            namespace="livestock",
            section_version=LIVESTOCK_COMMERCIAL_PASSPORT_SECTION_VERSION,
            content={
                "commercial_passport": {
                    "status": "FORMAL_ISSUED_SNAPSHOT",
                    "subject_scope": "property",
                    "property_id": str(passport.context.property_id.value),
                    "temporal_context": {
                        "reference_time": passport.context.reference_time.isoformat(),
                        "knowledge_cutoff": passport.context.knowledge_cutoff.isoformat(),
                        "evaluated_at": passport.context.evaluated_at.isoformat(),
                        "issued_at": issued_at.isoformat(),
                    },
                    "result_boundary": passport.context.result_boundary,
                    "opportunities": [
                        _opportunity_snapshot(item) for item in passport.opportunities
                    ],
                    "limitations": list(passport.limitations),
                    "non_goals": [
                        "not a Decision",
                        "not MarketEligibility",
                        "not export authorization",
                        "not public disclosure without AuthorizationGrant",
                    ],
                }
            },
        )


def commercial_passport_projection(passport: CommercialPassport) -> dict[str, Any]:
    """HTTP-ready projection of a dynamic Commercial Passport.

    The payload is derived from the application projection. It is not a
    Decision, not MarketEligibility and not a formal issued snapshot.
    """

    return {
        "property_id": str(passport.context.property_id.value),
        "reference_time": passport.context.reference_time.isoformat(),
        "knowledge_cutoff": passport.context.knowledge_cutoff.isoformat(),
        "evaluated_at": passport.context.evaluated_at.isoformat(),
        "result_boundary": passport.context.result_boundary,
        "opportunities": [_opportunity_snapshot(item) for item in passport.opportunities],
        "limitations": list(passport.limitations),
    }


def _breakdown(
    requirements: tuple[CommercialRequirementAssessment, ...],
) -> CommercialReadinessBreakdown:
    counts = Counter(item.status for item in requirements)
    return CommercialReadinessBreakdown(
        satisfied=counts[CommercialPassportRequirementStatus.SATISFIED],
        missing=counts[CommercialPassportRequirementStatus.MISSING],
        unknown=counts[CommercialPassportRequirementStatus.UNKNOWN],
        failed=counts[CommercialPassportRequirementStatus.FAILED],
        not_applicable=counts[CommercialPassportRequirementStatus.NOT_APPLICABLE],
        blocked=counts[CommercialPassportRequirementStatus.BLOCKED],
    )


def _ensure_unique_requirement_codes(
    requirements: tuple[CommercialRequirementAssessment, ...],
) -> None:
    codes = [item.requirement_code for item in requirements]
    if len(set(codes)) != len(codes):
        raise ValueError("Requirement codes nao podem repetir na mesma readiness.")


def _require_text_tuple(values: tuple[str, ...], field_name: str) -> None:
    if not isinstance(values, tuple):
        raise TypeError(f"{field_name} deve ser tuple.")
    if any(not isinstance(item, str) or not item.strip() for item in values):
        raise ValueError(f"{field_name} nao aceita texto vazio.")


def _opportunity_snapshot(item: CommercialPassportOpportunityAssessment) -> dict[str, Any]:
    opportunity = item.opportunity
    readiness = item.property_readiness
    population = item.population_eligibility
    return {
        "opportunity": {
            "code": opportunity.code,
            "kind": opportunity.kind.value,
            "name": opportunity.name,
            "purpose": opportunity.purpose,
            "policy_id": str(opportunity.policy_id.value),
            "policy_version": opportunity.policy_version,
            "effective_from": (
                None
                if opportunity.effective_from is None
                else opportunity.effective_from.isoformat()
            ),
            "effective_until": (
                None
                if opportunity.effective_until is None
                else opportunity.effective_until.isoformat()
            ),
        },
        "property_readiness": {
            "interpretation": readiness.breakdown.interpretation.value,
            "breakdown": {
                "satisfied": readiness.breakdown.satisfied,
                "missing": readiness.breakdown.missing,
                "unknown": readiness.breakdown.unknown,
                "failed": readiness.breakdown.failed,
                "not_applicable": readiness.breakdown.not_applicable,
                "blocked": readiness.breakdown.blocked,
                "applicable_count": readiness.breakdown.applicable_count,
                "total_count": readiness.breakdown.total_count,
                "derived_ratio": _readiness_ratio_snapshot(readiness.breakdown),
            },
            "requirements": [
                _requirement_snapshot(requirement) for requirement in readiness.requirements
            ],
        },
        "population_eligibility": None
        if population is None
        else {
            "subject_type": population.subject_type,
            "counts_by_status": dict(population.counts_by_status),
            "total_count": population.total_count,
            "source_report_reference": population.source_report_reference,
            "limitations": list(population.limitations),
        },
        "limitations": list(item.limitations),
    }


def _requirement_snapshot(requirement: CommercialRequirementAssessment) -> dict[str, Any]:
    return {
        "requirement_code": requirement.requirement_code,
        "label": requirement.label,
        "dimension": requirement.dimension.value,
        "status": requirement.status.value,
        "reason": requirement.reason,
        "reason_codes": list(requirement.reason_codes),
        "evidence_references": [
            {
                "entity_type": reference.target_id.entity_type,
                "id": str(reference.target_id.value),
                "organization_id": (
                    None
                    if reference.organization_id is None
                    else str(reference.organization_id.value)
                ),
                "contract_version": reference.contract_version,
            }
            for reference in requirement.evidence_references
        ],
        "evaluation_id": (
            None if requirement.evaluation_id is None else str(requirement.evaluation_id.value)
        ),
        "decision_id": None
        if requirement.decision_id is None
        else str(requirement.decision_id.value),
        "limitations": list(requirement.limitations),
    }


def _readiness_ratio_snapshot(breakdown: CommercialReadinessBreakdown) -> dict[str, int] | None:
    if breakdown.applicable_count == 0:
        return None
    return {
        "satisfied": breakdown.satisfied,
        "applicable": breakdown.applicable_count,
    }
