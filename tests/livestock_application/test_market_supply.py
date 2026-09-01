import pytest

from packages.core_domain.decision import DecisionResult
from packages.livestock_application.market_readiness import (
    MarketReadinessInput,
    MarketReadinessService,
    MarketReadinessStatus,
)
from packages.livestock_application.market_supply import (
    PRODUCER_SIDE_ANALYSIS_BOUNDARY,
    ProducerMarketSupplyAnalysisService,
    ProducerMarketSupplyQuestion,
)
from tests.livestock_application.test_market_readiness import _artifacts, _context


def test_producer_market_supply_aggregates_readiness_without_new_decision() -> None:
    ready, ready_evaluation, policy = _artifacts()
    not_ready, not_ready_evaluation, _ = _artifacts(
        organization_id=policy.organization_id,
        policy_id=policy.policy_id,
        result=DecisionResult.REJEITADA,
    )
    conditioned, conditioned_evaluation, _ = _artifacts(
        organization_id=policy.organization_id,
        policy_id=policy.policy_id,
        result=DecisionResult.APROVADA_COM_RESTRICOES,
    )
    report = MarketReadinessService().build_report(
        context=_context(policy),
        inputs=(
            MarketReadinessInput(ready.subject_id, ready, ready_evaluation),
            MarketReadinessInput(not_ready.subject_id, not_ready, not_ready_evaluation),
            MarketReadinessInput(conditioned.subject_id, conditioned, conditioned_evaluation),
        ),
    )

    analysis = ProducerMarketSupplyAnalysisService().build_from_readiness(
        report=report,
        question=ProducerMarketSupplyQuestion(requested_quantity=2),
    )

    assert analysis.analysis_boundary == PRODUCER_SIDE_ANALYSIS_BOUNDARY
    assert analysis.population_count == 3
    assert analysis.readiness_counts[MarketReadinessStatus.READY.value] == 1
    assert analysis.readiness_counts[MarketReadinessStatus.CONDITIONED.value] == 1
    assert analysis.readiness_counts[MarketReadinessStatus.NOT_READY.value] == 1
    assert analysis.current_capacity == 1
    assert analysis.estimated_shortage_now == 1
    assert ready.decision_id in {entry.decision_id for entry in report.entries}


def test_producer_market_supply_keeps_temporal_and_policy_context() -> None:
    decision, evaluation, policy = _artifacts()
    report = MarketReadinessService().build_report(
        context=_context(policy),
        inputs=(MarketReadinessInput(decision.subject_id, decision, evaluation),),
    )

    analysis = ProducerMarketSupplyAnalysisService().build_from_readiness(report=report)

    assert analysis.organization_id == str(policy.organization_id.value)
    assert analysis.policy_id == str(policy.policy_id.value)
    assert analysis.policy_version == policy.version
    assert analysis.reference_time == report.context.reference_time.isoformat()
    assert analysis.knowledge_cutoff == report.context.knowledge_cutoff.isoformat()


def test_producer_market_supply_exposes_only_aggregate_gap_counts() -> None:
    not_ready, not_ready_evaluation, policy = _artifacts(result=DecisionResult.REJEITADA)
    indeterminate, indeterminate_evaluation, _ = _artifacts(
        organization_id=policy.organization_id,
        policy_id=policy.policy_id,
        result=DecisionResult.INDETERMINADA,
    )
    report = MarketReadinessService().build_report(
        context=_context(policy),
        inputs=(
            MarketReadinessInput(not_ready.subject_id, not_ready, not_ready_evaluation),
            MarketReadinessInput(
                indeterminate.subject_id,
                indeterminate,
                indeterminate_evaluation,
            ),
        ),
    )

    analysis = ProducerMarketSupplyAnalysisService().build_from_readiness(report=report)

    assert analysis.gap_summary
    assert all(isinstance(gap.code, str) for gap in analysis.gap_summary)
    assert all(gap.count >= 1 for gap in analysis.gap_summary)
    assert all(not hasattr(gap, "example_subject_ids") for gap in analysis.gap_summary)


def test_producer_market_supply_marks_unknown_and_reassessment_limitations() -> None:
    decision, evaluation, policy = _artifacts(purpose="another-purpose")
    report = MarketReadinessService().build_report(
        context=_context(policy),
        inputs=(
            MarketReadinessInput(decision.subject_id, decision, evaluation),
            MarketReadinessInput(_artifacts(organization_id=policy.organization_id)[0].subject_id),
        ),
    )

    analysis = ProducerMarketSupplyAnalysisService().build_from_readiness(report=report)

    assert "derived from MarketReadiness; not a Decision" in analysis.limitations
    assert "no buyer visibility" in analysis.limitations
    assert "population contains not evaluated subjects" in analysis.limitations
    assert "population contains subjects requiring reassessment" in analysis.limitations


def test_producer_market_supply_rejects_invalid_quantity() -> None:
    with pytest.raises(ValueError, match="requested_quantity"):
        ProducerMarketSupplyQuestion(requested_quantity=0)
