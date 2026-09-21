"""Operational gap analysis for Commercial Passport projections.

The engine derives actionable guidance from an already built Commercial
Passport. It does not evaluate policies, issue Decisions, guarantee commercial
acceptance or persist a new authoritative object.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from packages.livestock_application.commercial_passport import (
    CommercialPassport,
    CommercialPassportOpportunityAssessment,
    CommercialPassportRequirementStatus,
)
from packages.livestock_application.market_readiness import MarketReadinessStatus

COMMERCIAL_GAP_ANALYSIS_LIMITATIONS = (
    "COMMERCIAL_GAP_ANALYSIS_IS_OPERATIONAL_GUIDANCE",
    "COMMERCIAL_GAP_ANALYSIS_IS_NOT_REGULATORY_DECISION",
    "COMMERCIAL_GAP_ANALYSIS_IS_NOT_COMMERCIAL_GUARANTEE",
    "COMMERCIAL_GAP_ANALYSIS_DOES_NOT_REPLACE_POLICY_EVALUATION_OR_DECISION",
)


class CommercialGapCategory(StrEnum):
    MISSING = "MISSING"
    UNKNOWN = "UNKNOWN"
    EXPIRED = "EXPIRED"
    INSUFFICIENT = "INSUFFICIENT"
    BLOCKING = "BLOCKING"


class CommercialGapActionCode(StrEnum):
    PROVIDE_EVIDENCE = "PROVIDE_EVIDENCE"
    CLARIFY_UNKNOWN = "CLARIFY_UNKNOWN"
    RENEW_OR_REASSESS = "RENEW_OR_REASSESS"
    REVIEW_FAILED_REQUIREMENTS = "REVIEW_FAILED_REQUIREMENTS"
    REMOVE_BLOCKER = "REMOVE_BLOCKER"
    RUN_MARKET_READINESS = "RUN_MARKET_READINESS"
    REVIEW_CONDITIONS = "REVIEW_CONDITIONS"


@dataclass(frozen=True, slots=True)
class CommercialGapRecommendation:
    action_code: CommercialGapActionCode
    description: str

    def to_dict(self) -> dict[str, str]:
        return {
            "action_code": self.action_code.value,
            "description": self.description,
        }


@dataclass(frozen=True, slots=True)
class CommercialActionableGap:
    opportunity_code: str
    opportunity_name: str
    dimension: str
    subject_scope: str
    gap_code: str
    label: str
    category: CommercialGapCategory
    reason: str
    reason_codes: tuple[str, ...]
    recommended_action: CommercialGapRecommendation
    affected_count: int | None = None
    limitations: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "opportunity_code": self.opportunity_code,
            "opportunity_name": self.opportunity_name,
            "dimension": self.dimension,
            "subject_scope": self.subject_scope,
            "gap_code": self.gap_code,
            "label": self.label,
            "category": self.category.value,
            "reason": self.reason,
            "reason_codes": list(self.reason_codes),
            "recommended_action": self.recommended_action.to_dict(),
            "affected_count": self.affected_count,
            "limitations": list(self.limitations),
        }


@dataclass(frozen=True, slots=True)
class CommercialGapAnalysis:
    gaps: tuple[CommercialActionableGap, ...]
    limitations: tuple[str, ...] = COMMERCIAL_GAP_ANALYSIS_LIMITATIONS

    @property
    def category_counts(self) -> dict[CommercialGapCategory, int]:
        counts = Counter(gap.category for gap in self.gaps)
        return {category: counts[category] for category in CommercialGapCategory}

    def to_dict(self) -> dict[str, Any]:
        return {
            "gap_count": len(self.gaps),
            "category_counts": {
                category.value: count for category, count in self.category_counts.items()
            },
            "gaps": [gap.to_dict() for gap in self.gaps],
            "limitations": list(self.limitations),
        }


class CommercialPassportGapAnalyzer:
    """Derive operational next actions from a Commercial Passport projection."""

    def analyze(self, passport: CommercialPassport) -> CommercialGapAnalysis:
        gaps: list[CommercialActionableGap] = []
        for assessment in passport.opportunities:
            gaps.extend(_requirement_gaps(assessment))
            gaps.extend(_population_gaps(assessment))
        return CommercialGapAnalysis(gaps=tuple(gaps))


def _requirement_gaps(
    assessment: CommercialPassportOpportunityAssessment,
) -> tuple[CommercialActionableGap, ...]:
    opportunity = assessment.opportunity
    gaps: list[CommercialActionableGap] = []
    for requirement in assessment.property_readiness.requirements:
        if requirement.status in {
            CommercialPassportRequirementStatus.SATISFIED,
            CommercialPassportRequirementStatus.NOT_APPLICABLE,
        }:
            continue
        category = _requirement_gap_category(
            requirement.status,
            reason_codes=requirement.reason_codes,
            limitations=requirement.limitations,
        )
        gaps.append(
            CommercialActionableGap(
                opportunity_code=opportunity.code,
                opportunity_name=opportunity.name,
                dimension=requirement.dimension.value,
                subject_scope="property",
                gap_code=requirement.requirement_code,
                label=requirement.label,
                category=category,
                reason=requirement.reason,
                reason_codes=requirement.reason_codes,
                recommended_action=_recommendation_for_category(category),
                limitations=requirement.limitations,
            )
        )
    return tuple(gaps)


def _population_gaps(
    assessment: CommercialPassportOpportunityAssessment,
) -> tuple[CommercialActionableGap, ...]:
    population = assessment.population_eligibility
    if population is None:
        return ()
    opportunity = assessment.opportunity
    gaps: list[CommercialActionableGap] = []
    for status, category, action_code in (
        (
            MarketReadinessStatus.NOT_EVALUATED,
            CommercialGapCategory.MISSING,
            CommercialGapActionCode.RUN_MARKET_READINESS,
        ),
        (
            MarketReadinessStatus.INDETERMINATE,
            CommercialGapCategory.UNKNOWN,
            CommercialGapActionCode.CLARIFY_UNKNOWN,
        ),
        (
            MarketReadinessStatus.REASSESSMENT_REQUIRED,
            CommercialGapCategory.EXPIRED,
            CommercialGapActionCode.RENEW_OR_REASSESS,
        ),
        (
            MarketReadinessStatus.NOT_READY,
            CommercialGapCategory.INSUFFICIENT,
            CommercialGapActionCode.REVIEW_FAILED_REQUIREMENTS,
        ),
        (
            MarketReadinessStatus.CONDITIONED,
            CommercialGapCategory.INSUFFICIENT,
            CommercialGapActionCode.REVIEW_CONDITIONS,
        ),
    ):
        count = population.counts_by_status.get(status.value, 0)
        if count <= 0:
            continue
        gaps.append(
            CommercialActionableGap(
                opportunity_code=opportunity.code,
                opportunity_name=opportunity.name,
                dimension="POPULATION_ELIGIBILITY",
                subject_scope=population.subject_type,
                gap_code=f"{opportunity.code}:population:{status.value}",
                label=f"{population.subject_type} population {status.value.lower()}",
                category=category,
                reason=(
                    f"{count} {population.subject_type}(s) are {status.value} for this opportunity."
                ),
                reason_codes=(status.value,),
                recommended_action=_recommendation(action_code),
                affected_count=count,
                limitations=population.limitations,
            )
        )
    return tuple(gaps)


def _requirement_gap_category(
    status: CommercialPassportRequirementStatus,
    *,
    reason_codes: tuple[str, ...],
    limitations: tuple[str, ...],
) -> CommercialGapCategory:
    if _mentions_expiration((*reason_codes, *limitations)):
        return CommercialGapCategory.EXPIRED
    return {
        CommercialPassportRequirementStatus.MISSING: CommercialGapCategory.MISSING,
        CommercialPassportRequirementStatus.UNKNOWN: CommercialGapCategory.UNKNOWN,
        CommercialPassportRequirementStatus.FAILED: CommercialGapCategory.INSUFFICIENT,
        CommercialPassportRequirementStatus.BLOCKED: CommercialGapCategory.BLOCKING,
    }[status]


def _mentions_expiration(values: tuple[str, ...]) -> bool:
    markers = ("EXPIRED", "STALE", "OUTDATED", "VENCID", "REASSESS")
    return any(marker in value.upper() for value in values for marker in markers)


def _recommendation_for_category(
    category: CommercialGapCategory,
) -> CommercialGapRecommendation:
    return _recommendation(
        {
            CommercialGapCategory.MISSING: CommercialGapActionCode.PROVIDE_EVIDENCE,
            CommercialGapCategory.UNKNOWN: CommercialGapActionCode.CLARIFY_UNKNOWN,
            CommercialGapCategory.EXPIRED: CommercialGapActionCode.RENEW_OR_REASSESS,
            CommercialGapCategory.INSUFFICIENT: (
                CommercialGapActionCode.REVIEW_FAILED_REQUIREMENTS
            ),
            CommercialGapCategory.BLOCKING: CommercialGapActionCode.REMOVE_BLOCKER,
        }[category]
    )


def _recommendation(action_code: CommercialGapActionCode) -> CommercialGapRecommendation:
    return CommercialGapRecommendation(
        action_code=action_code,
        description={
            CommercialGapActionCode.PROVIDE_EVIDENCE: (
                "Attach or register the missing evidence before requesting reassessment."
            ),
            CommercialGapActionCode.CLARIFY_UNKNOWN: (
                "Review the unknown facts, inaccessible evidence or limitations before relying "
                "on this opportunity."
            ),
            CommercialGapActionCode.RENEW_OR_REASSESS: (
                "Renew the outdated material or run a new assessment for the current context."
            ),
            CommercialGapActionCode.REVIEW_FAILED_REQUIREMENTS: (
                "Review failed requirements and correct the underlying operational condition."
            ),
            CommercialGapActionCode.REMOVE_BLOCKER: (
                "Resolve the blocking condition before treating this opportunity as available."
            ),
            CommercialGapActionCode.RUN_MARKET_READINESS: (
                "Run MarketReadiness for the affected population before commercial use."
            ),
            CommercialGapActionCode.REVIEW_CONDITIONS: (
                "Review the conditions attached to the eligible population before negotiation."
            ),
        }[action_code],
    )
