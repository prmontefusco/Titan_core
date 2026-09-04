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
from packages.livestock_application.market_change_impact import (
    MarketChangeImpactContext,
    MarketChangeImpactInput,
    MarketChangeImpactService,
)
from packages.livestock_application.market_optionality import (
    MARKET_ELIGIBILITY_RESULT_BOUNDARY,
    DeterministicMarketOptionExplanationDraftProvider,
    MarketOptionAssessmentService,
    MarketOptionChangeImpactService,
    MarketOptionChangeImpactState,
    MarketOptionContext,
    MarketOptionEventContext,
    MarketOptionEventKind,
    MarketOptionExplanationAssertion,
    MarketOptionExplanationClaim,
    MarketOptionExplanationClaimType,
    MarketOptionExplanationDraft,
    MarketOptionExplanationGuardService,
    MarketOptionExplanationPipelineService,
    MarketOptionExplanationRunContext,
    MarketOptionExplanationViolation,
    MarketOptionInput,
    MarketOptionPreservationWarningService,
    MarketOptionPreservationWarningState,
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


def _ai_run_context() -> MarketOptionExplanationRunContext:
    return MarketOptionExplanationRunContext(
        data_contract_id="MARKET_OPTIONALITY_AI_EXPLANATION_SYNTHETIC_V1",
        data_contract_version=1,
        processing_activity="SYNTHETIC_AI_EXPLANATION_VALIDATION",
        provider_profile="LOCAL_DETERMINISTIC_FAKE",
        model_name="deterministic-market-optionality-explainer",
    )


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


def test_policy_change_impact_marks_open_option_as_reassessment_needed() -> None:
    decision, evaluation, policy_v1 = _artifacts(purpose=PURPOSE)
    replacement_policy_id = TypedId.new("policy")
    previous_assessment = MarketOptionAssessmentService().assess(
        context=_context_with_purpose(policy_v1, decision, PURPOSE),
        decision=decision,
        evaluation=evaluation,
    )
    impact = MarketChangeImpactService().assess(
        context=MarketChangeImpactContext(
            organization_id=policy_v1.organization_id,
            purpose=PURPOSE,
            previous_policy_id=policy_v1.policy_id,
            previous_policy_version=policy_v1.version,
            replacement_policy_id=replacement_policy_id,
            replacement_policy_version=2,
            reference_time=NOW,
            knowledge_cutoff=NOW,
        ),
        inputs=(MarketChangeImpactInput(decision, evaluation),),
    )

    report = MarketOptionChangeImpactService().build_report(
        impact_assessment=impact,
        previous_assessments=(previous_assessment,),
    )

    assert report.entries[0].previous_state is MarketOptionState.OPTION_OPEN
    assert report.entries[0].replacement_state is None
    assert report.entries[0].impact_state is MarketOptionChangeImpactState.REASSESSMENT_NEEDED
    assert "REPLACEMENT_OPTIONALITY_ASSESSMENT_UNAVAILABLE" in report.entries[0].limitations
    assert report.counts_by_state[MarketOptionChangeImpactState.REASSESSMENT_NEEDED] == 1


def test_policy_change_impact_can_compose_supplied_replacement_incompatibility() -> None:
    organization_id = OrganizationId.new()
    subject_id = TypedId.new("animal")
    previous_decision, previous_evaluation, policy_v1 = _artifacts(
        organization_id=organization_id,
        subject_id=subject_id,
        purpose=PURPOSE,
    )
    replacement_decision, replacement_evaluation, policy_v3 = _artifacts(
        organization_id=organization_id,
        subject_id=subject_id,
        purpose=PURPOSE,
        policy_version=3,
        result=DecisionResult.REJEITADA,
    )
    previous_assessment = MarketOptionAssessmentService().assess(
        context=_context_with_purpose(policy_v1, previous_decision, PURPOSE),
        decision=previous_decision,
        evaluation=previous_evaluation,
    )
    replacement_assessment = MarketOptionAssessmentService().assess(
        context=_context_with_purpose(policy_v3, replacement_decision, PURPOSE),
        decision=replacement_decision,
        evaluation=replacement_evaluation,
    )
    impact = MarketChangeImpactService().assess(
        context=MarketChangeImpactContext(
            organization_id=organization_id,
            purpose=PURPOSE,
            previous_policy_id=policy_v1.policy_id,
            previous_policy_version=policy_v1.version,
            replacement_policy_id=policy_v3.policy_id,
            replacement_policy_version=3,
            reference_time=NOW,
            knowledge_cutoff=NOW,
        ),
        inputs=(MarketChangeImpactInput(previous_decision, previous_evaluation),),
    )

    report = MarketOptionChangeImpactService().build_report(
        impact_assessment=impact,
        previous_assessments=(previous_assessment,),
        replacement_assessments=(replacement_assessment,),
    )

    assert report.entries[0].previous_state is MarketOptionState.OPTION_OPEN
    assert report.entries[0].replacement_state is MarketOptionState.TEMPORARILY_INCOMPATIBLE
    assert report.entries[0].impact_state is MarketOptionChangeImpactState.OPTIONALITY_LOST
    assert report.counts_by_state[MarketOptionChangeImpactState.OPTIONALITY_LOST] == 1


def test_policy_change_impact_keeps_unrelated_market_unchanged() -> None:
    decision, evaluation, policy = _artifacts(purpose="unrelated-market")
    previous_assessment = MarketOptionAssessmentService().assess(
        context=_context_with_purpose(policy, decision, "unrelated-market"),
        decision=decision,
        evaluation=evaluation,
    )
    impact = MarketChangeImpactService().assess(
        context=MarketChangeImpactContext(
            organization_id=policy.organization_id,
            purpose=PURPOSE,
            previous_policy_id=TypedId.new("policy"),
            previous_policy_version=1,
            replacement_policy_id=TypedId.new("policy"),
            replacement_policy_version=2,
            reference_time=NOW,
            knowledge_cutoff=NOW,
        ),
        inputs=(MarketChangeImpactInput(decision, evaluation),),
    )

    report = MarketOptionChangeImpactService().build_report(
        impact_assessment=impact,
        previous_assessments=(previous_assessment,),
    )

    assert report.entries[0].previous_state is MarketOptionState.OPTION_OPEN
    assert report.entries[0].replacement_state is MarketOptionState.OPTION_OPEN
    assert report.entries[0].impact_state is MarketOptionChangeImpactState.UNCHANGED
    assert report.counts_by_state[MarketOptionChangeImpactState.UNCHANGED] == 1


def _event_context(
    *,
    policy: Policy,
    decision: Decision,
    event_kind: MarketOptionEventKind = MarketOptionEventKind.TREATMENT,
    welfare_or_legal_duty: bool = False,
) -> MarketOptionEventContext:
    return MarketOptionEventContext(
        organization_id=policy.organization_id,
        subject_id=decision.subject_id,
        event_kind=event_kind,
        event_reference="synthetic-event:001",
        occurred_or_proposed_at=NOW,
        knowledge_cutoff=NOW,
        purpose=PURPOSE,
        welfare_or_legal_duty=welfare_or_legal_duty,
    )


def test_preservation_warning_states_welfare_boundary_without_operational_command() -> None:
    before_decision, before_evaluation, policy = _artifacts(purpose=PURPOSE)
    after_decision, after_evaluation, _ = _artifacts(
        organization_id=policy.organization_id,
        subject_id=before_decision.subject_id,
        purpose=PURPOSE,
        policy_id=policy.policy_id,
        result=DecisionResult.REJEITADA,
    )
    before = MarketOptionAssessmentService().assess(
        context=_context_with_purpose(policy, before_decision, PURPOSE),
        decision=before_decision,
        evaluation=before_evaluation,
    )
    after = MarketOptionAssessmentService().assess(
        context=_context_with_purpose(policy, after_decision, PURPOSE),
        decision=after_decision,
        evaluation=after_evaluation,
    )

    warning = MarketOptionPreservationWarningService().explain(
        event_context=_event_context(
            policy=policy,
            decision=before_decision,
            welfare_or_legal_duty=True,
        ),
        before=before,
        after=after,
    )

    assert warning.warning_state is MarketOptionPreservationWarningState.OPTION_LOSS_INDICATED
    assert warning.reversibility is MarketOptionReversibility.TEMPORARY
    assert "ANIMAL_WELFARE_OR_LEGAL_DUTY_OVERRIDES_MARKET_OPTIONALITY" in warning.limitations
    assert "DO_NOT_OMIT_OR_DELAY_REQUIRED_FACT_RECORDING" in warning.limitations


def test_preservation_warning_distinguishes_reversible_risk_from_irreversible_loss() -> None:
    before_decision, before_evaluation, policy = _artifacts(purpose=PURPOSE)
    conditioned_decision, conditioned_evaluation, _ = _artifacts(
        organization_id=policy.organization_id,
        subject_id=before_decision.subject_id,
        purpose=PURPOSE,
        policy_id=policy.policy_id,
        result=DecisionResult.APROVADA_COM_RESTRICOES,
    )
    irreversible_decision, irreversible_evaluation, _ = _artifacts(
        organization_id=policy.organization_id,
        subject_id=before_decision.subject_id,
        purpose=PURPOSE,
        policy_id=policy.policy_id,
        result=DecisionResult.REJEITADA,
    )
    irreversible_decision = replace(
        irreversible_decision,
        reasons=(
            replace(
                irreversible_decision.reasons[0],
                code=DecisionReasonCode.REGRA_NAO_ATENDIDA,
                message="IRREVERSIBLE_SYNTHETIC_TRACEABILITY_LOSS",
            ),
        ),
    )
    service = MarketOptionAssessmentService()
    before = service.assess(
        context=_context_with_purpose(policy, before_decision, PURPOSE),
        decision=before_decision,
        evaluation=before_evaluation,
    )
    conditioned = service.assess(
        context=_context_with_purpose(policy, conditioned_decision, PURPOSE),
        decision=conditioned_decision,
        evaluation=conditioned_evaluation,
    )
    irreversible = service.assess(
        context=_context_with_purpose(policy, irreversible_decision, PURPOSE),
        decision=irreversible_decision,
        evaluation=irreversible_evaluation,
    )

    risk = MarketOptionPreservationWarningService().explain(
        event_context=_event_context(policy=policy, decision=before_decision),
        before=before,
        after=conditioned,
    )
    loss = MarketOptionPreservationWarningService().explain(
        event_context=_event_context(
            policy=policy,
            decision=before_decision,
            event_kind=MarketOptionEventKind.MOVEMENT,
        ),
        before=before,
        after=irreversible,
    )

    assert risk.warning_state is MarketOptionPreservationWarningState.OPTION_AT_RISK
    assert risk.reversibility is MarketOptionReversibility.POTENTIALLY_RESOLVABLE
    assert loss.warning_state is MarketOptionPreservationWarningState.OPTION_LOSS_INDICATED
    assert loss.reversibility is MarketOptionReversibility.IRREVERSIBLE


def test_preservation_warning_missing_material_does_not_recommend_omitting_facts() -> None:
    decision, _, policy = _artifacts(purpose=PURPOSE)

    warning = MarketOptionPreservationWarningService().explain(
        event_context=_event_context(
            policy=policy,
            decision=decision,
            event_kind=MarketOptionEventKind.DOCUMENTARY,
        ),
        before=None,
        after=None,
    )

    assert warning.warning_state is MarketOptionPreservationWarningState.INSUFFICIENT_MATERIAL
    assert warning.before_state is None
    assert warning.after_state is None
    assert "DO_NOT_OMIT_OR_DELAY_REQUIRED_FACT_RECORDING" in warning.limitations


def test_explanation_context_preserves_canonical_source_references() -> None:
    decision, evaluation, policy = _artifacts(purpose=PURPOSE)
    assessment = MarketOptionAssessmentService().assess(
        context=_context_from_artifacts(policy, decision),
        decision=decision,
        evaluation=evaluation,
    )

    context = MarketOptionExplanationGuardService().prepare_context(assessment=assessment)

    assert context.source_references["decision_id"] == str(decision.decision_id)
    assert context.source_references["evaluation_id"] == str(evaluation.evaluation_id)
    assert context.source_references["policy_id"] == str(policy.policy_id)
    assert context.source_references["policy_version"] == str(policy.version)
    assert context.source_references["reference_time"] == NOW.isoformat()
    assert context.source_references["knowledge_cutoff"] == NOW.isoformat()
    assert context.allowed_option_state is MarketOptionState.OPTION_OPEN
    assert (
        MarketOptionExplanationClaim(
            claim_type=MarketOptionExplanationClaimType.STATUS,
            value=MarketOptionState.OPTION_OPEN.value,
            source_reference=str(decision.decision_id),
        )
        in context.allowed_claims
    )
    assert "AI_EXPLANATION_CONTEXT_IS_NOT_DECISION" in context.limitations


def test_explanation_guard_accepts_canonical_summary_draft() -> None:
    decision, evaluation, policy = _artifacts(purpose=PURPOSE)
    assessment = MarketOptionAssessmentService().assess(
        context=_context_from_artifacts(policy, decision),
        decision=decision,
        evaluation=evaluation,
    )
    context = MarketOptionExplanationGuardService().prepare_context(assessment=assessment)

    validation = MarketOptionExplanationGuardService().validate_draft(
        context=context,
        draft=MarketOptionExplanationDraft(
            text="Resumo sintético baseado apenas nas referências canônicas informadas.",
            decision_id=decision.decision_id,
            evaluation_id=evaluation.evaluation_id,
            policy_id=policy.policy_id,
            policy_version=policy.version,
            option_state=MarketOptionState.OPTION_OPEN,
            referenced_claims=context.allowed_claims,
            referenced_reason_codes=assessment.reason_codes,
        ),
    )

    assert validation.accepted is True
    assert validation.violations == ()


def test_explanation_guard_rejects_invented_gap_or_reason() -> None:
    decision, evaluation, policy = _artifacts(purpose=PURPOSE)
    assessment = MarketOptionAssessmentService().assess(
        context=_context_from_artifacts(policy, decision),
        decision=decision,
        evaluation=evaluation,
    )
    context = MarketOptionExplanationGuardService().prepare_context(assessment=assessment)

    validation = MarketOptionExplanationGuardService().validate_draft(
        context=context,
        draft=MarketOptionExplanationDraft(
            text="Resumo sintético com lacuna inventada.",
            decision_id=decision.decision_id,
            evaluation_id=evaluation.evaluation_id,
            policy_id=policy.policy_id,
            policy_version=policy.version,
            option_state=MarketOptionState.OPTION_OPEN,
            referenced_reason_codes=("SYNTHETIC_INVENTED_REASON",),
            referenced_missing_evidence_types=("synthetic_invented_gap",),
        ),
    )

    assert validation.accepted is False
    assert MarketOptionExplanationViolation.INVENTED_REASON_CODE in validation.violations
    assert MarketOptionExplanationViolation.INVENTED_MISSING_EVIDENCE_TYPE in validation.violations


def test_explanation_guard_rejects_ai_originated_structured_claim() -> None:
    decision, evaluation, policy = _artifacts(purpose=PURPOSE)
    assessment = MarketOptionAssessmentService().assess(
        context=_context_from_artifacts(policy, decision),
        decision=decision,
        evaluation=evaluation,
    )
    context = MarketOptionExplanationGuardService().prepare_context(assessment=assessment)

    validation = MarketOptionExplanationGuardService().validate_draft(
        context=context,
        draft=MarketOptionExplanationDraft(
            text="Resumo sintético com claim estrutural inventado.",
            decision_id=decision.decision_id,
            evaluation_id=evaluation.evaluation_id,
            policy_id=policy.policy_id,
            policy_version=policy.version,
            option_state=MarketOptionState.OPTION_OPEN,
            referenced_claims=(
                MarketOptionExplanationClaim(
                    claim_type=MarketOptionExplanationClaimType.MISSING_INFORMATION,
                    value="AI_INVENTED_TREATMENT_HISTORY_GAP",
                    source_reference=str(decision.decision_id),
                ),
            ),
        ),
    )

    assert validation.accepted is False
    assert MarketOptionExplanationViolation.INVENTED_CLAIM in validation.violations


def test_explanation_guard_rejects_authoritative_or_forecast_claims() -> None:
    decision, evaluation, policy = _artifacts(purpose=PURPOSE)
    assessment = MarketOptionAssessmentService().assess(
        context=_context_from_artifacts(policy, decision),
        decision=decision,
        evaluation=evaluation,
    )
    context = MarketOptionExplanationGuardService().prepare_context(assessment=assessment)

    validation = MarketOptionExplanationGuardService().validate_draft(
        context=context,
        draft=MarketOptionExplanationDraft(
            text="Resumo sintético tentando virar forecast e decisão.",
            decision_id=decision.decision_id,
            evaluation_id=evaluation.evaluation_id,
            policy_id=policy.policy_id,
            policy_version=policy.version,
            option_state=MarketOptionState.OPTION_OPEN,
            assertions=(
                MarketOptionExplanationAssertion.CANONICAL_SUMMARY,
                MarketOptionExplanationAssertion.FORECAST,
                MarketOptionExplanationAssertion.DECISION,
            ),
        ),
    )

    assert validation.accepted is False
    assert (
        MarketOptionExplanationViolation.PROHIBITED_AUTHORITATIVE_ASSERTION in validation.violations
    )


def test_explanation_pipeline_releases_only_guarded_deterministic_summary() -> None:
    decision, evaluation, policy = _artifacts(purpose=PURPOSE)
    assessment = MarketOptionAssessmentService().assess(
        context=_context_from_artifacts(policy, decision),
        decision=decision,
        evaluation=evaluation,
    )

    result = MarketOptionExplanationPipelineService().explain(
        assessment=assessment,
        run_context=_ai_run_context(),
    )

    assert result.validation.accepted is True
    assert result.released_text is not None
    assert MarketOptionState.OPTION_OPEN.value in result.released_text
    assert result.canonical_fallback["state"] == MarketOptionState.OPTION_OPEN.value
    assert result.explanation_context.source_references["decision_id"] == str(decision.decision_id)


def test_explanation_pipeline_falls_back_when_provider_invents_material() -> None:
    class InventingProvider(DeterministicMarketOptionExplanationDraftProvider):
        def draft(self, *, explanation_context, run_context):  # type: ignore[no-untyped-def]
            assessment = explanation_context.assessment
            return MarketOptionExplanationDraft(
                text="Resumo sintético com conclusão não canônica.",
                decision_id=assessment.decision_id,
                evaluation_id=assessment.evaluation_id,
                policy_id=assessment.context.policy_id,
                policy_version=assessment.context.policy_version,
                option_state=MarketOptionState.OPTION_OPEN,
                referenced_claims=(
                    MarketOptionExplanationClaim(
                        claim_type=MarketOptionExplanationClaimType.STATUS,
                        value="AI_ORIGINATED_STATUS",
                        source_reference=str(assessment.decision_id),
                    ),
                ),
                referenced_reason_codes=("INVENTED_AI_REASON",),
                assertions=(MarketOptionExplanationAssertion.FORECAST,),
            )

    decision, evaluation, policy = _artifacts(purpose=PURPOSE)
    assessment = MarketOptionAssessmentService().assess(
        context=_context_from_artifacts(policy, decision),
        decision=decision,
        evaluation=evaluation,
    )

    result = MarketOptionExplanationPipelineService(draft_provider=InventingProvider()).explain(
        assessment=assessment,
        run_context=_ai_run_context(),
    )

    assert result.validation.accepted is False
    assert result.released_text is None
    assert result.canonical_fallback["state"] == MarketOptionState.OPTION_OPEN.value
    assert MarketOptionExplanationViolation.INVENTED_CLAIM in result.validation.violations
    assert MarketOptionExplanationViolation.INVENTED_REASON_CODE in result.validation.violations
    assert (
        MarketOptionExplanationViolation.PROHIBITED_AUTHORITATIVE_ASSERTION
        in result.validation.violations
    )


def test_explanation_run_context_requires_governance_references() -> None:
    with pytest.raises(ValueError, match="data_contract_id"):
        MarketOptionExplanationRunContext(
            data_contract_id="",
            data_contract_version=1,
            processing_activity="SYNTHETIC_AI_EXPLANATION_VALIDATION",
            provider_profile="LOCAL_DETERMINISTIC_FAKE",
            model_name="deterministic-market-optionality-explainer",
        )

    with pytest.raises(ValueError, match="data_contract_version"):
        MarketOptionExplanationRunContext(
            data_contract_id="MARKET_OPTIONALITY_AI_EXPLANATION_SYNTHETIC_V1",
            data_contract_version=0,
            processing_activity="SYNTHETIC_AI_EXPLANATION_VALIDATION",
            provider_profile="LOCAL_DETERMINISTIC_FAKE",
            model_name="deterministic-market-optionality-explainer",
        )
