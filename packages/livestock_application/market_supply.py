"""Producer-side Market Supply aggregate analysis (CUT F1).

This module composes existing MarketReadiness outputs. It does not evaluate
Policies, emit Decisions, persist reports, expose buyer visibility, or perform
cross-Organization access.
"""

from dataclasses import dataclass

from packages.livestock_application.market_readiness import (
    MARKET_ELIGIBILITY_RESULT_BOUNDARY,
    MarketReadinessGapSummary,
    MarketReadinessReport,
    MarketReadinessStatus,
)

PRODUCER_SIDE_ANALYSIS_BOUNDARY = "PRODUCER_SIDE_SINGLE_ORGANIZATION_ANALYSIS"


@dataclass(frozen=True, slots=True)
class ProducerMarketSupplyQuestion:
    """Optional producer-side quantity question over an already resolved population."""

    requested_quantity: int | None = None

    def __post_init__(self) -> None:
        if self.requested_quantity is not None and self.requested_quantity < 1:
            raise ValueError("requested_quantity deve ser inteiro >= 1 quando informado.")


@dataclass(frozen=True, slots=True)
class ProducerMarketSupplyGap:
    code: str
    count: int


@dataclass(frozen=True, slots=True)
class ProducerMarketSupplyAnalysis:
    organization_id: str
    purpose: str
    policy_id: str
    policy_version: int
    reference_time: str
    knowledge_cutoff: str
    population_count: int
    readiness_counts: dict[str, int]
    current_capacity: int
    requested_quantity: int | None
    estimated_shortage_now: int | None
    gap_summary: tuple[ProducerMarketSupplyGap, ...]
    limitations: tuple[str, ...]
    analysis_boundary: str = PRODUCER_SIDE_ANALYSIS_BOUNDARY
    source_boundary: str = MARKET_ELIGIBILITY_RESULT_BOUNDARY


class ProducerMarketSupplyAnalysisService:
    """Aggregates readiness for the producer's own Organization."""

    def build_from_readiness(
        self,
        *,
        report: MarketReadinessReport,
        question: ProducerMarketSupplyQuestion | None = None,
    ) -> ProducerMarketSupplyAnalysis:
        question = question or ProducerMarketSupplyQuestion()
        readiness_counts = {
            status.value: report.counts.get(status, 0) for status in MarketReadinessStatus
        }
        current_capacity = readiness_counts[MarketReadinessStatus.READY.value]
        estimated_shortage = (
            None
            if question.requested_quantity is None
            else max(question.requested_quantity - current_capacity, 0)
        )
        limitations = _limitations_from_report(report)
        return ProducerMarketSupplyAnalysis(
            organization_id=str(report.context.organization_id.value),
            purpose=report.context.purpose,
            policy_id=str(report.context.policy_id.value),
            policy_version=report.context.policy_version,
            reference_time=report.context.reference_time.isoformat(),
            knowledge_cutoff=report.context.knowledge_cutoff.isoformat(),
            population_count=len(report.entries),
            readiness_counts=readiness_counts,
            current_capacity=current_capacity,
            requested_quantity=question.requested_quantity,
            estimated_shortage_now=estimated_shortage,
            gap_summary=_aggregate_gaps(report.gap_summary),
            limitations=limitations,
        )


def _aggregate_gaps(
    gaps: tuple[MarketReadinessGapSummary, ...],
) -> tuple[ProducerMarketSupplyGap, ...]:
    return tuple(
        ProducerMarketSupplyGap(code=gap.code, count=gap.count)
        for gap in sorted(gaps, key=lambda item: item.code)
    )


def _limitations_from_report(report: MarketReadinessReport) -> tuple[str, ...]:
    limitations = {
        "producer-side single-Organization analysis",
        "derived from MarketReadiness; not a Decision",
        "not export authorization",
        "not external authority recognition",
        "no forecast included",
        "no buyer visibility",
    }
    if any(entry.status is MarketReadinessStatus.NOT_EVALUATED for entry in report.entries):
        limitations.add("population contains not evaluated subjects")
    if any(entry.status is MarketReadinessStatus.INDETERMINATE for entry in report.entries):
        limitations.add("population contains indeterminate subjects")
    if any(entry.status is MarketReadinessStatus.REASSESSMENT_REQUIRED for entry in report.entries):
        limitations.add("population contains subjects requiring reassessment")
    return tuple(sorted(limitations))
