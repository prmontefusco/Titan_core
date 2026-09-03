"""F1: Market Optionality projection remains pure and non-decisional."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from packages.core_domain.decision import Decision, DecisionReasonCode, DecisionResult
from packages.core_domain.evaluation import (
    EvaluationOutcome,
    RuleResult,
    RuleResultStatus,
    compute_evaluation_hash,
    compute_rule_inputs_hash,
)
from packages.core_domain.policy import Policy
from packages.core_domain.rule import SeverityLevel
from packages.livestock_application.market_optionality import (
    MARKET_ELIGIBILITY_RESULT_BOUNDARY,
    MarketOptionAssessmentService,
    MarketOptionContext,
    MarketOptionInput,
    MarketOptionReversibility,
    MarketOptionState,
    MultiMarketOptionReportService,
)
from packages.shared_kernel import OrganizationId, TypedId
from tests.livestock_application.test_market_readiness import NOW, _artifacts

PURPOSE = "market-test-a"
EU_PURPOSE = "synthetic-eu-market"
US_PURPOSE = "synthetic-us-market"
CN_PURPOSE = "synthetic-cn-market"


def _context_from_artifacts(policy: Policy, decision: Decision) -> MarketOptionContext:
    return MarketOptionContext(
        organization_id=policy.organization_id,
        subject_id=decision.subject_id,
        market_purpose=PURPOSE,
        policy_id=policy.policy_id,
        policy_version=policy.version,
        reference_time=NOW,
        knowledge_cutoff=NOW,
    )


def _context_with_purpose(
    policy: Policy,
    decision: Decision,
    purpose: str,
) -> MarketOptionContext:
    return MarketOptionContext(
        organization_id=policy.organization_id,
        subject_id=decision.subject_id,
        market_purpose=purpose,
        policy_id=policy.policy_id,
        policy_version=policy.version,
        reference_time=NOW,
        knowledge_cutoff=NOW,
    )


def test_ready_decision_preserves_option_without_new_decision() -> None:
    decision, evaluation, policy = _artifacts(purpose=PURPOSE)

    assessment = MarketOptionAssessmentService().assess(
        context=_context_from_artifacts(policy, decision),
        decision=decision,
        evaluation=evaluation,
    )

    assert assessment.state is MarketOptionState.OPTION_OPEN
    assert assessment.reversibility is MarketOptionReversibility.NOT_APPLICABLE
    assert assessment.preserves_option is True
    assert assessment.decision_id == decision.decision_id
    assert assessment.evaluation_id == evaluation.evaluation_id
    assert assessment.result_boundary == MARKET_ELIGIBILITY_RESULT_BOUNDARY


def test_missing_evidence_is_not_incompatible() -> None:
    decision, evaluation, policy = _artifacts(
        purpose=PURPOSE,
        result=DecisionResult.INDETERMINADA,
    )
    pending = RuleResult.create(
        rule_id=TypedId.new("rule"),
        rule_version=1,
        organization_id=policy.organization_id,
        subject_id=decision.subject_id,
        status=RuleResultStatus.PENDENTE,
        severity=SeverityLevel.BLOCKING,
        reason="Documento sintético ausente.",
        evaluated_at=NOW,
        snapshot_hash=evaluation.fact_snapshot.snapshot_hash,
        inputs_hash=compute_rule_inputs_hash(
            TypedId.new("rule"),
            1,
            decision.subject_id,
            evaluation.fact_snapshot.snapshot_hash,
            (),
        ),
        missing_evidence_types=("feed_attestation",),
        rule_code="market-optionality-test-rule",
    )
    evaluation_with_gap = replace(
        evaluation,
        rule_results=(pending,),
        outcome=EvaluationOutcome.INFORMACAO_INSUFICIENTE,
    )
    evaluation_with_gap = replace(
        evaluation_with_gap,
        evaluation_hash=compute_evaluation_hash(
            context_hash=evaluation_with_gap.context_hash,
            subject_id=evaluation_with_gap.subject_id,
            snapshot_hash=evaluation_with_gap.fact_snapshot.snapshot_hash,
            rule_results=evaluation_with_gap.rule_results,
            outcome=evaluation_with_gap.outcome,
        ),
    )
    decision = replace(
        decision,
        evaluation_hash=evaluation_with_gap.evaluation_hash,
    )

    assessment = MarketOptionAssessmentService().assess(
        context=_context_from_artifacts(policy, decision),
        decision=decision,
        evaluation=evaluation_with_gap,
    )

    assert assessment.state is MarketOptionState.MISSING_EVIDENCE
    assert assessment.reversibility is MarketOptionReversibility.POTENTIALLY_RESOLVABLE
    assert assessment.missing_evidence_types == ("feed_attestation",)


def test_policy_change_requires_reassessment_without_mutating_historical_decision() -> None:
    decision, evaluation, policy_v1 = _artifacts(purpose=PURPOSE)
    policy_v2 = replace(policy_v1, policy_id=TypedId.new("policy"), version=2)
    original_decision_hash = decision.decision_hash

    assessment = MarketOptionAssessmentService().assess(
        context=MarketOptionContext(
            organization_id=policy_v1.organization_id,
            subject_id=decision.subject_id,
            market_purpose=PURPOSE,
            policy_id=policy_v2.policy_id,
            policy_version=policy_v2.version,
            reference_time=NOW,
            knowledge_cutoff=NOW,
        ),
        decision=decision,
        evaluation=evaluation,
    )

    assert assessment.state is MarketOptionState.REASSESSMENT_REQUIRED
    assert decision.result is DecisionResult.APROVADA
    assert decision.decision_hash == original_decision_hash


def test_policy_unavailable_is_distinct_from_not_ready_and_unknown() -> None:
    decision, _, policy = _artifacts(purpose=PURPOSE)

    assessment = MarketOptionAssessmentService().assess(
        context=_context_from_artifacts(policy, decision),
        policy_available=False,
    )

    assert assessment.state is MarketOptionState.POLICY_UNAVAILABLE
    assert assessment.decision_id is None
    assert assessment.reason_codes == ("POLICY_UNAVAILABLE",)


def test_rejected_decision_defaults_to_temporary_incompatibility() -> None:
    decision, evaluation, policy = _artifacts(
        purpose=PURPOSE,
        result=DecisionResult.REJEITADA,
    )

    assessment = MarketOptionAssessmentService().assess(
        context=_context_from_artifacts(policy, decision),
        decision=decision,
        evaluation=evaluation,
    )

    assert assessment.state is MarketOptionState.TEMPORARILY_INCOMPATIBLE
    assert assessment.reversibility is MarketOptionReversibility.TEMPORARY


def test_irreversible_marker_keeps_permanent_loss_distinct() -> None:
    decision, evaluation, policy = _artifacts(
        purpose=PURPOSE,
        result=DecisionResult.REJEITADA,
    )
    decision = replace(
        decision,
        reasons=(
            replace(
                decision.reasons[0],
                code=DecisionReasonCode.REGRA_NAO_ATENDIDA,
                message="IRREVERSIBLE_LIFETIME_TRACEABILITY_GAP",
            ),
        ),
    )

    assessment = MarketOptionAssessmentService().assess(
        context=_context_from_artifacts(policy, decision),
        decision=decision,
        evaluation=evaluation,
    )

    assert assessment.state is MarketOptionState.IRREVERSIBLY_INCOMPATIBLE
    assert assessment.reversibility is MarketOptionReversibility.IRREVERSIBLE


def test_context_requires_temporal_coordinates_and_target_window_order() -> None:
    decision, _, policy = _artifacts(purpose=PURPOSE)

    with pytest.raises(ValueError, match="knowledge_cutoff"):
        MarketOptionContext(
            organization_id=policy.organization_id,
            subject_id=decision.subject_id,
            market_purpose=PURPOSE,
            policy_id=policy.policy_id,
            policy_version=policy.version,
            reference_time=NOW,
            knowledge_cutoff=NOW - timedelta(days=1),
        )

    with pytest.raises(ValueError, match="target_window"):
        MarketOptionContext(
            organization_id=policy.organization_id,
            subject_id=decision.subject_id,
            market_purpose=PURPOSE,
            policy_id=policy.policy_id,
            policy_version=policy.version,
            reference_time=NOW,
            knowledge_cutoff=NOW,
            target_window_from=datetime(2027, 1, 2, tzinfo=UTC),
            target_window_until=datetime(2027, 1, 2, tzinfo=UTC),
        )


def test_missing_decision_is_not_evaluated_not_open() -> None:
    decision, _, policy = _artifacts(purpose=PURPOSE)

    assessment = MarketOptionAssessmentService().assess(
        context=_context_from_artifacts(policy, decision),
    )

    assert assessment.state is MarketOptionState.NOT_EVALUATED
    assert assessment.preserves_option is False


def test_multi_market_report_lists_synthetic_markets_deterministically() -> None:
    organization_id = OrganizationId.new()
    subject_id = TypedId.new("animal")
    eu_decision, eu_evaluation, eu_policy = _artifacts(
        organization_id=organization_id,
        subject_id=subject_id,
        purpose=EU_PURPOSE,
    )
    us_decision, us_evaluation, us_policy = _artifacts(
        organization_id=organization_id,
        subject_id=subject_id,
        purpose=US_PURPOSE,
    )
    cn_decision, cn_evaluation, cn_policy = _artifacts(
        organization_id=organization_id,
        subject_id=subject_id,
        purpose=CN_PURPOSE,
    )

    report = MultiMarketOptionReportService().build_report(
        inputs=(
            MarketOptionInput(
                context=_context_with_purpose(cn_policy, cn_decision, CN_PURPOSE),
                decision=cn_decision,
                evaluation=cn_evaluation,
            ),
            MarketOptionInput(
                context=_context_with_purpose(eu_policy, eu_decision, EU_PURPOSE),
                decision=eu_decision,
                evaluation=eu_evaluation,
            ),
            MarketOptionInput(
                context=_context_with_purpose(us_policy, us_decision, US_PURPOSE),
                decision=us_decision,
                evaluation=us_evaluation,
            ),
        ),
    )

    assert report.organization_id == eu_policy.organization_id
    assert report.subject_id == eu_decision.subject_id
    assert report.reference_time == NOW
    assert report.knowledge_cutoff == NOW
    assert report.market_purposes == (CN_PURPOSE, EU_PURPOSE, US_PURPOSE)
    assert report.counts_by_state[MarketOptionState.OPTION_OPEN] == 3
    assert report.counts_by_state[MarketOptionState.POLICY_UNAVAILABLE] == 0
    assert report.limitations == (
        "MULTI_MARKET_OPTIONALITY_IS_DERIVED_NON_DECISIONAL",
        "NO_FORECAST_OR_FUTURE_ELIGIBILITY_GUARANTEE",
    )


def test_multi_market_report_keeps_unsupported_market_distinct() -> None:
    decision, evaluation, policy = _artifacts(purpose=EU_PURPOSE)

    report = MultiMarketOptionReportService().build_report(
        inputs=(
            MarketOptionInput(
                context=_context_with_purpose(policy, decision, EU_PURPOSE),
                decision=decision,
                evaluation=evaluation,
            ),
            MarketOptionInput(
                context=MarketOptionContext(
                    organization_id=policy.organization_id,
                    subject_id=decision.subject_id,
                    market_purpose="synthetic-unsupported-market",
                    policy_id=TypedId.new("policy"),
                    policy_version=1,
                    reference_time=NOW,
                    knowledge_cutoff=NOW,
                ),
                policy_available=False,
            ),
        ),
    )

    assert report.counts_by_state[MarketOptionState.OPTION_OPEN] == 1
    assert report.counts_by_state[MarketOptionState.POLICY_UNAVAILABLE] == 1
    unsupported = report.assessments[1]
    assert unsupported.context.market_purpose == "synthetic-unsupported-market"
    assert unsupported.decision_id is None


def test_multi_market_report_rejects_ambiguous_duplicate_policy_purpose() -> None:
    decision, evaluation, policy = _artifacts(purpose=EU_PURPOSE)
    duplicated_context = _context_with_purpose(policy, decision, EU_PURPOSE)

    with pytest.raises(ValueError, match="duplicado"):
        MultiMarketOptionReportService().build_report(
            inputs=(
                MarketOptionInput(
                    context=duplicated_context,
                    decision=decision,
                    evaluation=evaluation,
                ),
                MarketOptionInput(
                    context=duplicated_context,
                    decision=decision,
                    evaluation=evaluation,
                ),
            ),
        )


def test_multi_market_policy_version_change_affects_only_that_market() -> None:
    organization_id = OrganizationId.new()
    subject_id = TypedId.new("animal")
    eu_decision, eu_evaluation, eu_policy_v1 = _artifacts(
        organization_id=organization_id,
        subject_id=subject_id,
        purpose=EU_PURPOSE,
    )
    us_decision, us_evaluation, us_policy = _artifacts(
        organization_id=organization_id,
        subject_id=subject_id,
        purpose=US_PURPOSE,
    )
    cn_decision, cn_evaluation, cn_policy = _artifacts(
        organization_id=organization_id,
        subject_id=subject_id,
        purpose=CN_PURPOSE,
    )
    eu_policy_v2 = replace(eu_policy_v1, policy_id=TypedId.new("policy"), version=2)

    report = MultiMarketOptionReportService().build_report(
        inputs=(
            MarketOptionInput(
                context=MarketOptionContext(
                    organization_id=eu_policy_v1.organization_id,
                    subject_id=eu_decision.subject_id,
                    market_purpose=EU_PURPOSE,
                    policy_id=eu_policy_v2.policy_id,
                    policy_version=eu_policy_v2.version,
                    reference_time=NOW,
                    knowledge_cutoff=NOW,
                ),
                decision=eu_decision,
                evaluation=eu_evaluation,
            ),
            MarketOptionInput(
                context=_context_with_purpose(us_policy, us_decision, US_PURPOSE),
                decision=us_decision,
                evaluation=us_evaluation,
            ),
            MarketOptionInput(
                context=_context_with_purpose(cn_policy, cn_decision, CN_PURPOSE),
                decision=cn_decision,
                evaluation=cn_evaluation,
            ),
        ),
    )

    states = {
        assessment.context.market_purpose: assessment.state for assessment in report.assessments
    }
    assert states == {
        CN_PURPOSE: MarketOptionState.OPTION_OPEN,
        EU_PURPOSE: MarketOptionState.REASSESSMENT_REQUIRED,
        US_PURPOSE: MarketOptionState.OPTION_OPEN,
    }
    assert report.counts_by_state[MarketOptionState.OPTION_OPEN] == 2
    assert report.counts_by_state[MarketOptionState.REASSESSMENT_REQUIRED] == 1
