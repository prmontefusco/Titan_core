"""Synthetic Market Supply Intelligence prototype.

Non-production CUT F0 artifact:

python -m uv run --locked python -m apps.validacao.market_supply_synthetic
python -m uv run --locked python -m apps.validacao.market_supply_synthetic --json-only

This script intentionally uses only in-memory synthetic data. It does not call the
API, database, repositories, external integrations, grants, Dossiers or
VerificationBundles.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class SyntheticReadinessStatus(StrEnum):
    READY = "READY"
    CONDITIONED = "CONDITIONED"
    INDETERMINATE = "INDETERMINATE"
    NOT_READY = "NOT_READY"
    NOT_EVALUATED = "NOT_EVALUATED"


class SyntheticGapCategory(StrEnum):
    SANITARY_HISTORY_GAP = "SANITARY_HISTORY_GAP"
    TERRITORIAL_EVIDENCE_GAP = "TERRITORIAL_EVIDENCE_GAP"
    DOCUMENTATION_GAP = "DOCUMENTATION_GAP"
    WITHDRAWAL_PERIOD = "WITHDRAWAL_PERIOD"
    IDENTITY_COVERAGE_GAP = "IDENTITY_COVERAGE_GAP"
    UNKNOWN_SOURCE = "UNKNOWN_SOURCE"


@dataclass(frozen=True)
class SyntheticCandidate:
    synthetic_subject_ref: str
    status: SyntheticReadinessStatus
    gaps: tuple[SyntheticGapCategory, ...] = ()
    potential_in_window: bool = False
    exclusion_reason: str | None = None


@dataclass(frozen=True)
class SyntheticCommercialDemand:
    demand_ref: str
    buyer_organization_label: str
    purpose: str
    requested_quantity: int
    commercial_window_start: str
    commercial_window_end: str
    policy_code: str
    policy_version: str


@dataclass(frozen=True)
class SyntheticPopulationSnapshot:
    criteria_digest: str
    reference_time: str
    knowledge_cutoff: str
    resolved_at: str
    included_count: int
    excluded_count: int
    exclusion_reason_summary: dict[str, int]
    authorization_context: str
    population_digest: str


def _synthetic_candidates() -> tuple[SyntheticCandidate, ...]:
    return (
        SyntheticCandidate("subject-001", SyntheticReadinessStatus.READY),
        SyntheticCandidate("subject-002", SyntheticReadinessStatus.READY),
        SyntheticCandidate("subject-003", SyntheticReadinessStatus.READY),
        SyntheticCandidate(
            "subject-004",
            SyntheticReadinessStatus.CONDITIONED,
            (SyntheticGapCategory.WITHDRAWAL_PERIOD,),
            potential_in_window=True,
        ),
        SyntheticCandidate(
            "subject-005",
            SyntheticReadinessStatus.CONDITIONED,
            (SyntheticGapCategory.DOCUMENTATION_GAP,),
            potential_in_window=True,
        ),
        SyntheticCandidate(
            "subject-006",
            SyntheticReadinessStatus.INDETERMINATE,
            (SyntheticGapCategory.UNKNOWN_SOURCE,),
        ),
        SyntheticCandidate(
            "subject-007",
            SyntheticReadinessStatus.NOT_READY,
            (SyntheticGapCategory.SANITARY_HISTORY_GAP,),
        ),
        SyntheticCandidate(
            "subject-008",
            SyntheticReadinessStatus.NOT_EVALUATED,
            (SyntheticGapCategory.TERRITORIAL_EVIDENCE_GAP,),
        ),
        SyntheticCandidate(
            "subject-009",
            SyntheticReadinessStatus.NOT_EVALUATED,
            exclusion_reason="not_authorized_for_aggregate_assessment",
        ),
    )


def build_synthetic_supply_intelligence_report() -> dict[str, Any]:
    generated_at = datetime(2026, 8, 28, 18, 0, tzinfo=UTC)
    reference_time = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)
    knowledge_cutoff = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)
    candidates = _synthetic_candidates()
    included = tuple(candidate for candidate in candidates if candidate.exclusion_reason is None)
    excluded = tuple(
        candidate for candidate in candidates if candidate.exclusion_reason is not None
    )

    demand = SyntheticCommercialDemand(
        demand_ref="synthetic-demand-001",
        buyer_organization_label="Synthetic Buyer Organization",
        purpose="MARKET_SUPPLY_AGGREGATE_ASSESSMENT",
        requested_quantity=7,
        commercial_window_start="2026-09-15",
        commercial_window_end="2026-09-30",
        policy_code="SYNTHETIC_MARKET_POLICY_A",
        policy_version="v0.synthetic",
    )
    population = SyntheticPopulationSnapshot(
        criteria_digest="sha256:synthetic-criteria-v0",
        reference_time=reference_time.isoformat(),
        knowledge_cutoff=knowledge_cutoff.isoformat(),
        resolved_at=generated_at.isoformat(),
        included_count=len(included),
        excluded_count=len(excluded),
        exclusion_reason_summary=_count_exclusion_reasons(excluded),
        authorization_context="synthetic-opt-in-aggregate-only",
        population_digest="sha256:synthetic-population-v0-without-buyer-visible-membership",
    )

    readiness_counts = {
        status.value: sum(1 for candidate in included if candidate.status is status)
        for status in SyntheticReadinessStatus
    }
    high_level_gaps = _count_gaps(included)
    ready_now = readiness_counts[SyntheticReadinessStatus.READY.value]
    potential_in_window = sum(1 for candidate in included if candidate.potential_in_window)
    estimated_capacity = ready_now + potential_in_window

    return {
        "report_type": "SupplyIntelligenceReport",
        "status": "SYNTHETIC_PROTOTYPE_NOT_FOR_PRODUCTION",
        "generated_at": generated_at.isoformat(),
        "commercial_demand": asdict(demand),
        "candidate_population_snapshot": asdict(population),
        "market_readiness_summary": readiness_counts,
        "gap_analysis": {
            "source": "derived_from_synthetic_readiness_and_gap_material",
            "high_level_gaps": high_level_gaps,
            "missing_information_policy": "missing_information_is_not_negative_evidence",
        },
        "supply_forecast": {
            "included": True,
            "forecast_type": "deterministic_synthetic_scenario",
            "assumption_version": "synthetic-assumptions-v0",
            "assumptions": (
                "no additional incompatible treatment occurs before the window",
                "conditioned documentation gap can be resolved before window start",
            ),
            "potential_in_window": potential_in_window,
            "limitations": (
                "synthetic data only",
                "not a Decision",
                "not future eligibility",
                "not a guarantee of availability",
            ),
        },
        "supply_demand_analysis": {
            "requested_quantity": demand.requested_quantity,
            "ready_now": ready_now,
            "potential_in_window": potential_in_window,
            "estimated_capacity": estimated_capacity,
            "estimated_shortage": max(demand.requested_quantity - estimated_capacity, 0),
            "indeterminate": readiness_counts[SyntheticReadinessStatus.INDETERMINATE.value],
            "not_evaluated": readiness_counts[SyntheticReadinessStatus.NOT_EVALUATED.value],
        },
        "buyer_visible_fields": (
            "total_authorized_population_considered",
            "readiness_counts",
            "high_level_gaps",
            "current_capacity",
            "potential_capacity_in_window",
            "estimated_shortage",
            "limitations",
            "generated_at",
            "reference_time",
            "knowledge_cutoff",
            "policy_code",
            "policy_version",
        ),
        "explicitly_not_disclosed": (
            "producer_names",
            "property_identity",
            "animal_identifiers",
            "treatments",
            "raw_evidence",
            "dossiers",
            "individual_evaluations",
            "individual_decisions",
            "candidate_membership",
        ),
        "limitations": (
            "synthetic internal validation artifact",
            "no production API",
            "no persistence",
            "no real cross-tenant access",
            "no grant evaluation",
            "no export authorization",
        ),
    }


def _count_exclusion_reasons(candidates: tuple[SyntheticCandidate, ...]) -> dict[str, int]:
    reasons: dict[str, int] = {}
    for candidate in candidates:
        if candidate.exclusion_reason is None:
            continue
        reasons[candidate.exclusion_reason] = reasons.get(candidate.exclusion_reason, 0) + 1
    return reasons


def _count_gaps(candidates: tuple[SyntheticCandidate, ...]) -> dict[str, int]:
    gaps: dict[str, int] = {}
    for candidate in candidates:
        for gap in candidate.gaps:
            gaps[gap.value] = gaps.get(gap.value, 0) + 1
    return dict(sorted(gaps.items()))


def _validation_questions() -> tuple[str, ...]:
    return (
        "Buyer: the aggregate report answers whether capacity is sufficient without exposing "
        "identities?",
        "Buyer: the distinction between ready now, potential in window and shortage is clear?",
        "Buyer: unknowns and limitations are visible enough to avoid overclaiming?",
        "Producer: the disclosed aggregate fields feel acceptable before detailed authorization?",
        "Producer: the report makes clear which details remain undisclosed?",
        "Product: does this vocabulary justify moving to a single-Organization producer-side F1?",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-only", action="store_true")
    args = parser.parse_args()

    report = build_synthetic_supply_intelligence_report()
    print(json.dumps(report, indent=2, sort_keys=True))
    if args.json_only:
        return
    print("\nValidation questions:")
    for question in _validation_questions():
        print(f"- {question}")


if __name__ == "__main__":
    main()
