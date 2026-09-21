"""Producer evidence vault planning for Livestock commercial readiness.

This module does not create a new Evidence store. It derives an operational
view from existing Commercial Passport material so the producer can see which
evidence types are expected, what is already referenced and where gaps remain.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from packages.livestock_application.commercial_gap_engine import (
    CommercialGapCategory,
    CommercialPassportGapAnalyzer,
)
from packages.livestock_application.commercial_passport import (
    CommercialPassport,
)
from packages.livestock_application.market_readiness import MarketReadinessStatus

PRODUCER_EVIDENCE_VAULT_LIMITATIONS = (
    "PRODUCER_EVIDENCE_VAULT_IS_OPERATIONAL_INDEX",
    "PRODUCER_EVIDENCE_VAULT_DOES_NOT_STORE_DOCUMENT_BYTES",
    "PRODUCER_EVIDENCE_VAULT_DOES_NOT_REPLACE_CORE_EVIDENCE",
    "PRODUCER_EVIDENCE_VAULT_IS_NOT_REGULATORY_DECISION",
)


class ProducerEvidenceNeedStatus(StrEnum):
    SATISFIED = "SATISFIED"
    MISSING = "MISSING"
    UNKNOWN = "UNKNOWN"
    EXPIRED = "EXPIRED"
    INSUFFICIENT = "INSUFFICIENT"
    BLOCKING = "BLOCKING"


@dataclass(frozen=True, slots=True)
class ProducerEvidenceNeed:
    need_code: str
    opportunity_code: str
    opportunity_name: str
    evidence_type: str
    purpose: str
    subject_scope: str
    status: ProducerEvidenceNeedStatus
    source_gap_code: str | None
    expected_coverage: str
    recommended_action: str
    referenced_evidence_ids: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "need_code": self.need_code,
            "opportunity_code": self.opportunity_code,
            "opportunity_name": self.opportunity_name,
            "evidence_type": self.evidence_type,
            "purpose": self.purpose,
            "subject_scope": self.subject_scope,
            "status": self.status.value,
            "source_gap_code": self.source_gap_code,
            "expected_coverage": self.expected_coverage,
            "recommended_action": self.recommended_action,
            "referenced_evidence_ids": list(self.referenced_evidence_ids),
            "limitations": list(self.limitations),
        }


@dataclass(frozen=True, slots=True)
class ProducerEvidenceVaultAnalysis:
    needs: tuple[ProducerEvidenceNeed, ...]
    limitations: tuple[str, ...] = PRODUCER_EVIDENCE_VAULT_LIMITATIONS

    @property
    def status_counts(self) -> dict[ProducerEvidenceNeedStatus, int]:
        counts = Counter(need.status for need in self.needs)
        return {status: counts[status] for status in ProducerEvidenceNeedStatus}

    @property
    def missing_count(self) -> int:
        return sum(
            count
            for status, count in self.status_counts.items()
            if status is not ProducerEvidenceNeedStatus.SATISFIED
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "need_count": len(self.needs),
            "missing_count": self.missing_count,
            "status_counts": {status.value: count for status, count in self.status_counts.items()},
            "needs": [need.to_dict() for need in self.needs],
            "limitations": list(self.limitations),
        }


class ProducerEvidenceVaultAnalyzer:
    """Build an operational evidence index from Commercial Passport material."""

    def analyze(self, passport: CommercialPassport) -> ProducerEvidenceVaultAnalysis:
        needs: list[ProducerEvidenceNeed] = []
        gap_analysis = CommercialPassportGapAnalyzer().analyze(passport)
        gap_by_code = {gap.gap_code: gap for gap in gap_analysis.gaps}

        for assessment in passport.opportunities:
            opportunity = assessment.opportunity
            for requirement in assessment.property_readiness.requirements:
                gap = gap_by_code.get(requirement.requirement_code)
                need_status = (
                    _status_from_gap_category(gap.category)
                    if gap is not None
                    else ProducerEvidenceNeedStatus.SATISFIED
                )
                needs.append(
                    ProducerEvidenceNeed(
                        need_code=f"{opportunity.code}:{requirement.requirement_code}",
                        opportunity_code=opportunity.code,
                        opportunity_name=opportunity.name,
                        evidence_type=_evidence_type_for_requirement(
                            requirement.requirement_code,
                            requirement.reason_codes,
                            requirement.label,
                        ),
                        purpose=opportunity.purpose,
                        subject_scope="property",
                        status=need_status,
                        source_gap_code=None if gap is None else gap.gap_code,
                        expected_coverage="property at Commercial Passport reference_time",
                        recommended_action=(
                            "Evidence already referenced for this requirement."
                            if gap is None
                            else gap.recommended_action.description
                        ),
                        referenced_evidence_ids=tuple(
                            str(reference.target_id.value)
                            for reference in requirement.evidence_references
                        ),
                        limitations=requirement.limitations,
                    )
                )

            population = assessment.population_eligibility
            if population is None:
                continue
            for status in (
                MarketReadinessStatus.NOT_EVALUATED,
                MarketReadinessStatus.INDETERMINATE,
                MarketReadinessStatus.REASSESSMENT_REQUIRED,
                MarketReadinessStatus.NOT_READY,
                MarketReadinessStatus.CONDITIONED,
            ):
                count = population.counts_by_status.get(status.value, 0)
                if count <= 0:
                    continue
                gap_code = f"{opportunity.code}:population:{status.value}"
                gap = gap_by_code.get(gap_code)
                needs.append(
                    ProducerEvidenceNeed(
                        need_code=gap_code,
                        opportunity_code=opportunity.code,
                        opportunity_name=opportunity.name,
                        evidence_type=_evidence_type_for_population_status(status),
                        purpose=opportunity.purpose,
                        subject_scope=population.subject_type,
                        status=(
                            ProducerEvidenceNeedStatus.UNKNOWN
                            if gap is None
                            else _status_from_gap_category(gap.category)
                        ),
                        source_gap_code=gap_code,
                        expected_coverage=(
                            f"{count} {population.subject_type}(s) in population eligibility"
                        ),
                        recommended_action=(
                            "Review population readiness evidence before negotiation."
                            if gap is None
                            else gap.recommended_action.description
                        ),
                        limitations=population.limitations,
                    )
                )

        return ProducerEvidenceVaultAnalysis(needs=tuple(needs))


def _status_from_gap_category(
    category: CommercialGapCategory,
) -> ProducerEvidenceNeedStatus:
    return {
        CommercialGapCategory.MISSING: ProducerEvidenceNeedStatus.MISSING,
        CommercialGapCategory.UNKNOWN: ProducerEvidenceNeedStatus.UNKNOWN,
        CommercialGapCategory.EXPIRED: ProducerEvidenceNeedStatus.EXPIRED,
        CommercialGapCategory.INSUFFICIENT: ProducerEvidenceNeedStatus.INSUFFICIENT,
        CommercialGapCategory.BLOCKING: ProducerEvidenceNeedStatus.BLOCKING,
    }[category]


def _evidence_type_for_requirement(
    requirement_code: str,
    reason_codes: tuple[str, ...],
    label: str,
) -> str:
    tokens = " ".join((requirement_code, label, *reason_codes)).casefold()
    if "gta" in tokens:
        return "livestock.gta"
    if "car" in tokens or "environment" in tokens or "territorial" in tokens:
        return "livestock.property_environmental_evidence"
    if "treatment" in tokens or "withdrawal" in tokens or "medication" in tokens:
        return "livestock.treatment_or_withdrawal_evidence"
    if "market-readiness" in tokens or "readiness" in tokens:
        return "livestock.market_readiness_report"
    if "sisbov" in tokens:
        return "livestock.sisbov_evidence"
    return "livestock.supporting_document"


def _evidence_type_for_population_status(status: MarketReadinessStatus) -> str:
    if status is MarketReadinessStatus.NOT_EVALUATED:
        return "livestock.market_readiness_evaluation"
    if status is MarketReadinessStatus.REASSESSMENT_REQUIRED:
        return "livestock.current_market_readiness_evaluation"
    if status is MarketReadinessStatus.INDETERMINATE:
        return "livestock.clarifying_evidence"
    return "livestock.corrective_evidence"
