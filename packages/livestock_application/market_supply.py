"""Producer-side Market Supply aggregate analysis (CUT F1).

This module composes existing MarketReadiness outputs. It does not evaluate
Policies, emit Decisions, persist reports, expose buyer visibility, or perform
cross-Organization access.
"""

from collections import Counter
from dataclasses import dataclass
from typing import Any

from packages.livestock_application.market_readiness import (
    MARKET_ELIGIBILITY_RESULT_BOUNDARY,
    MarketReadinessContext,
    MarketReadinessDecisionReaderPort,
    MarketReadinessEvaluationReaderPort,
    MarketReadinessGapSummary,
    MarketReadinessPopulationReader,
    MarketReadinessReport,
    MarketReadinessService,
    MarketReadinessStatus,
)
from packages.livestock_application.market_supply_population import (
    AuthorizedCandidatePopulationResult,
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


@dataclass(frozen=True, slots=True)
class MarketSupplyAggregatePayloadBuilder:
    """Builds the public aggregate payload from canonical MarketReadiness reports.

    This is not a disclosure decision and not a Policy/Evaluation engine. The
    returned mapping is still subject to privacy, audit and public response
    mapping before it can be released externally.
    """

    def build_from_readiness_reports(
        self,
        *,
        reports: tuple[MarketReadinessReport, ...],
        requested_quantity: int | None,
    ) -> dict[str, Any]:
        if requested_quantity is not None and requested_quantity < 1:
            raise ValueError("requested_quantity deve ser inteiro >= 1 quando informado.")
        if not reports:
            readiness_counts = {status.value: 0 for status in MarketReadinessStatus}
            return _aggregate_payload(
                readiness_counts=readiness_counts,
                requested_quantity=requested_quantity,
                gap_summary=(),
                limitations=("no authorized candidate population",),
            )
        _assert_homogeneous_context(reports)
        readiness_counts = {
            status.value: sum(report.counts.get(status, 0) for report in reports)
            for status in MarketReadinessStatus
        }
        gap_counts: Counter[str] = Counter()
        limitations = {
            "derived from MarketReadiness; not a Decision",
            "not export authorization",
            "not external authority recognition",
            "no forecast included",
            "aggregate summary only",
        }
        for report in reports:
            for gap in report.gap_summary:
                public_gap_code = _public_gap_code(gap.code)
                if public_gap_code != gap.code:
                    limitations.add("some gap codes use a public general category")
                gap_counts[public_gap_code] += gap.count
            if any(entry.status is MarketReadinessStatus.NOT_EVALUATED for entry in report.entries):
                limitations.add("population contains not evaluated subjects")
            if any(entry.status is MarketReadinessStatus.INDETERMINATE for entry in report.entries):
                limitations.add("population contains indeterminate subjects")
            if any(
                entry.status is MarketReadinessStatus.REASSESSMENT_REQUIRED
                for entry in report.entries
            ):
                limitations.add("population contains subjects requiring reassessment")
        return _aggregate_payload(
            readiness_counts=readiness_counts,
            requested_quantity=requested_quantity,
            gap_summary=tuple(
                ProducerMarketSupplyGap(code=code, count=count)
                for code, count in sorted(gap_counts.items())
            ),
            limitations=tuple(sorted(limitations)),
        )


def _assert_homogeneous_context(reports: tuple[MarketReadinessReport, ...]) -> None:
    first = reports[0].context
    for report in reports[1:]:
        context = report.context
        if (
            context.purpose != first.purpose
            or context.policy_id != first.policy_id
            or context.policy_version != first.policy_version
            or context.reference_time != first.reference_time
            or context.knowledge_cutoff != first.knowledge_cutoff
        ):
            raise ValueError("Market Supply aggregate exige reports com contexto homogeneo.")


def _aggregate_payload(
    *,
    readiness_counts: dict[str, int],
    requested_quantity: int | None,
    gap_summary: tuple[ProducerMarketSupplyGap, ...],
    limitations: tuple[str, ...],
) -> dict[str, Any]:
    ready_now = readiness_counts[MarketReadinessStatus.READY.value]
    return {
        "population_count": sum(readiness_counts.values()),
        "readiness_counts": readiness_counts,
        "ready_now": ready_now,
        "conditioned": readiness_counts[MarketReadinessStatus.CONDITIONED.value],
        "indeterminate": readiness_counts[MarketReadinessStatus.INDETERMINATE.value],
        "not_ready": readiness_counts[MarketReadinessStatus.NOT_READY.value],
        "not_evaluated": readiness_counts[MarketReadinessStatus.NOT_EVALUATED.value],
        "reassessment_required": readiness_counts[
            MarketReadinessStatus.REASSESSMENT_REQUIRED.value
        ],
        "current_capacity": ready_now,
        "requested_quantity": requested_quantity,
        "estimated_shortage_now": (
            None if requested_quantity is None else max(requested_quantity - ready_now, 0)
        ),
        "gap_summary": tuple({"code": gap.code, "count": gap.count} for gap in gap_summary),
        "limitations": limitations,
    }


def _public_gap_code(code: str) -> str:
    normalized = code.casefold()
    blocked_fragments = ("id", "identifier", "producer", "property", "animal")
    if any(fragment in normalized for fragment in blocked_fragments):
        return "GENERAL_GAP"
    return code


@dataclass(frozen=True, slots=True)
class MarketSupplyReadinessCompositionService:
    """Builds MarketReadiness reports for authorized owner-scoped snapshots."""

    decision_reader: MarketReadinessDecisionReaderPort
    evaluation_reader: MarketReadinessEvaluationReaderPort
    readiness_service: MarketReadinessService

    def build_reports(
        self,
        *,
        population_result: AuthorizedCandidatePopulationResult,
    ) -> tuple[MarketReadinessReport, ...]:
        reports: list[MarketReadinessReport] = []
        for snapshot in population_result.snapshots:
            criteria = snapshot.criteria
            context = MarketReadinessContext(
                organization_id=criteria.organization_id,
                purpose=criteria.purpose,
                policy_id=criteria.policy_id,
                policy_version=criteria.policy_version,
                reference_time=criteria.reference_time,
                knowledge_cutoff=criteria.knowledge_cutoff,
            )
            reports.append(
                MarketReadinessPopulationReader(
                    decision_repository=self.decision_reader,
                    evaluation_repository=self.evaluation_reader,
                    readiness_service=self.readiness_service,
                ).build_for_animals(
                    context=context,
                    animal_ids=snapshot.included_subject_ids,
                )
            )
        return tuple(reports)
