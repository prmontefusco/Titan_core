"""F1: Market Optionality projection remains pure and non-decisional."""

import hashlib
from collections.abc import Mapping
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
    MARKET_OPTIONALITY_AI_EXPLANATION_DISCLOSURE_RESTRICTIONS,
    MARKET_OPTIONALITY_AI_EXPLANATION_OUTPUT_CLASSIFICATION,
    MARKET_OPTIONALITY_AI_EXPLANATION_SYNTHETIC_CONTRACT_ID,
    DeterministicMarketOptionExplanationTextProvider,
    InMemoryMarketOptionExplanationAuditRepository,
    MarketOptionAssessmentService,
    MarketOptionChangeImpactService,
    MarketOptionChangeImpactState,
    MarketOptionContext,
    MarketOptionEventContext,
    MarketOptionEventKind,
    MarketOptionExplanationAssertion,
    MarketOptionExplanationAuditEnvelope,
    MarketOptionExplanationAuditRecord,
    MarketOptionExplanationAuditRecordContext,
    MarketOptionExplanationClaim,
    MarketOptionExplanationClaimType,
    MarketOptionExplanationDataContractService,
    MarketOptionExplanationDraft,
    MarketOptionExplanationDraftSection,
    MarketOptionExplanationGuardService,
    MarketOptionExplanationOpaqueAuditReference,
    MarketOptionExplanationPipelineService,
    MarketOptionExplanationPromptTemplate,
    MarketOptionExplanationProviderProcessingAuthorization,
    MarketOptionExplanationProviderProfile,
    MarketOptionExplanationProviderProfileState,
    MarketOptionExplanationReleaseDisposition,
    MarketOptionExplanationRequestIdentity,
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


def _draft_sections(
    text: str, claim_refs: tuple[str, ...] = ("claim:1",)
) -> tuple[MarketOptionExplanationDraftSection, ...]:
    return (MarketOptionExplanationDraftSection(claim_refs=claim_refs, text=text),)


def _ai_run_context(
    organization_id: OrganizationId,
    purpose: str = PURPOSE,
    idempotency_key: str | None = None,
) -> MarketOptionExplanationRunContext:
    return MarketOptionExplanationRunContext(
        data_contract_id=MARKET_OPTIONALITY_AI_EXPLANATION_SYNTHETIC_CONTRACT_ID,
        data_contract_version=1,
        processing_activity="SYNTHETIC_AI_EXPLANATION_VALIDATION",
        processing_authorization_organization_id=organization_id,
        processing_authorization_purpose=purpose,
        provider_profile="LOCAL_DETERMINISTIC_FAKE",
        model_name="deterministic-market-optionality-explainer",
        idempotency_key=idempotency_key,
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
            sections=_draft_sections(
                "Resumo sintético baseado apenas nas referências canônicas informadas."
            ),
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
            sections=_draft_sections("Resumo sintético com lacuna inventada."),
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
            sections=_draft_sections("Resumo sintético com claim estrutural inventado."),
        ),
    )

    assert validation.accepted is False
    assert MarketOptionExplanationViolation.INVENTED_CLAIM in validation.violations


def test_explanation_guard_rejects_unknown_structured_claim_ref() -> None:
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
            text="Resumo sintético apontando para claim não autorizado.",
            decision_id=decision.decision_id,
            evaluation_id=evaluation.evaluation_id,
            policy_id=policy.policy_id,
            policy_version=policy.version,
            option_state=MarketOptionState.OPTION_OPEN,
            referenced_claims=context.allowed_claims,
            sections=_draft_sections(
                "Resumo sintético apontando para claim não autorizado.",
                claim_refs=("claim:999",),
            ),
        ),
    )

    assert validation.accepted is False
    assert MarketOptionExplanationViolation.UNKNOWN_CLAIM_REFERENCE in validation.violations


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
            sections=_draft_sections("Resumo sintético tentando virar forecast e decisão."),
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


def test_explanation_data_contract_builds_need_to_know_payload_without_raw_ids() -> None:
    decision, evaluation, policy = _artifacts(purpose=PURPOSE)
    assessment = MarketOptionAssessmentService().assess(
        context=_context_from_artifacts(policy, decision),
        decision=decision,
        evaluation=evaluation,
    )
    context = MarketOptionExplanationGuardService().prepare_context(assessment=assessment)

    payload = MarketOptionExplanationDataContractService().build_prompt_payload(
        explanation_context=context,
        run_context=_ai_run_context(policy.organization_id),
    )

    assert payload.data_contract_id == MARKET_OPTIONALITY_AI_EXPLANATION_SYNTHETIC_CONTRACT_ID
    assert payload.data_contract_version == 1
    assert payload.prompt_template_id == "market-optionality-explanation-canonical-summary"
    assert payload.prompt_template_version == 1
    assert len(payload.prompt_template_digest) == 64
    assert payload.guard_version == 1
    assert len(payload.guard_digest) == 64
    assert len(payload.payload_digest) == 64
    assert set(payload.fields) == {
        "audience",
        "subject_type",
        "market_purpose",
        "policy_version",
        "reference_time",
        "knowledge_cutoff",
        "option_state",
        "reversibility",
        "claims",
        "reason_aliases",
        "missing_evidence_aliases",
        "limitation_aliases",
        "context_limitation_aliases",
        "output_classification",
        "disclosure_restrictions",
    }
    assert payload.fields["subject_type"] == "animal"
    assert payload.fields["option_state"] == MarketOptionState.OPTION_OPEN.value
    assert payload.source_reference_aliases

    provider_visible_json = repr(payload.fields)
    assert "reason_codes" not in payload.fields
    assert "missing_evidence_types" not in payload.fields
    assert "limitations" not in payload.fields
    assert "context_limitations" not in payload.fields
    assert payload.fields["reason_aliases"] == ({"alias": "reason:1"},)
    claims = payload.fields["claims"]
    assert isinstance(claims, tuple)
    first_claim = claims[0]
    assert isinstance(first_claim, Mapping)
    assert first_claim["claim_ref"] == "claim:1"
    assert first_claim["source_alias"] == "claim_source:1"
    assert "READY_DECISION" not in provider_visible_json
    assert str(policy.organization_id) not in provider_visible_json
    assert str(decision.subject_id) not in provider_visible_json
    assert str(decision.decision_id) not in provider_visible_json
    assert str(evaluation.evaluation_id) not in provider_visible_json
    assert str(policy.policy_id) not in provider_visible_json


def test_explanation_prompt_template_rejects_digest_mismatch() -> None:
    with pytest.raises(ValueError, match="template_digest"):
        MarketOptionExplanationPromptTemplate(template_digest="0" * 64)

    with pytest.raises(ValueError, match="guard_digest"):
        MarketOptionExplanationPromptTemplate(guard_digest="0" * 64)


def test_explanation_provider_profile_denies_retention_telemetry_and_secondary_use() -> None:
    profile = MarketOptionExplanationProviderProfile()

    assert profile.profile_id == "LOCAL_DETERMINISTIC_FAKE"
    assert profile.profile_version == 1
    assert profile.lifecycle_state is MarketOptionExplanationProviderProfileState.APPROVED
    assert profile.provider_side_retention == "NONE"
    assert profile.telemetry == "NONE"
    assert profile.abuse_logging == "NONE"
    assert profile.secondary_use == "PROHIBITED"
    assert profile.training_use == "PROHIBITED"
    assert profile.tool_execution == "PROHIBITED"
    assert profile.browsing == "PROHIBITED"
    assert profile.retrieval == "PROHIBITED"
    assert profile.grounding == "PROHIBITED"
    assert profile.code_execution == "PROHIBITED"
    assert profile.file_search == "PROHIBITED"
    assert profile.persistent_memory == "PROHIBITED"
    assert profile.connectors == "PROHIBITED"
    assert profile.agentic_actions == "PROHIBITED"
    assert profile.external_side_effects == "PROHIBITED"
    assert len(profile.profile_digest) == 64

    with pytest.raises(ValueError, match="provider_side_retention"):
        MarketOptionExplanationProviderProfile(provider_side_retention="PROVIDER_DEFAULT")
    with pytest.raises(ValueError, match="telemetry"):
        MarketOptionExplanationProviderProfile(telemetry="PROVIDER_DEFAULT")
    with pytest.raises(ValueError, match="secondary_use"):
        MarketOptionExplanationProviderProfile(secondary_use="ALLOWED")
    with pytest.raises(ValueError, match="browsing"):
        MarketOptionExplanationProviderProfile(browsing="ALLOWED")
    with pytest.raises(ValueError, match="retrieval"):
        MarketOptionExplanationProviderProfile(retrieval="ALLOWED")
    with pytest.raises(ValueError, match="persistent_memory"):
        MarketOptionExplanationProviderProfile(persistent_memory="ALLOWED")
    with pytest.raises(ValueError, match="agentic_actions"):
        MarketOptionExplanationProviderProfile(agentic_actions="ALLOWED")


def test_explanation_provider_profile_lifecycle_and_effective_period_are_digestable() -> None:
    effective_from = NOW - timedelta(days=1)
    effective_until = NOW + timedelta(days=1)
    profile = MarketOptionExplanationProviderProfile(
        effective_from=effective_from,
        effective_until=effective_until,
    )
    suspended = MarketOptionExplanationProviderProfile(
        lifecycle_state=MarketOptionExplanationProviderProfileState.SUSPENDED,
        effective_from=effective_from,
        effective_until=effective_until,
    )

    assert profile.is_available_at(NOW) is True
    assert suspended.is_available_at(NOW) is False
    assert suspended.profile_digest != profile.profile_digest
    assert MarketOptionExplanationProviderProfile(effective_until=NOW).is_available_at(NOW) is False
    with pytest.raises(ValueError, match="effective_until"):
        MarketOptionExplanationProviderProfile(
            effective_from=NOW,
            effective_until=NOW,
        )


def test_explanation_provider_profile_rejects_digest_mismatch() -> None:
    with pytest.raises(ValueError, match="profile_digest"):
        MarketOptionExplanationProviderProfile(profile_digest="0" * 64)


def test_explanation_provider_processing_authorization_is_bounded_and_digestable() -> None:
    organization_id = OrganizationId.new()
    authorization = MarketOptionExplanationProviderProcessingAuthorization(
        organization_id=organization_id,
        purpose=PURPOSE,
        provider_profile="LOCAL_DETERMINISTIC_FAKE",
        provider_profile_version=1,
        data_contract_id=MARKET_OPTIONALITY_AI_EXPLANATION_SYNTHETIC_CONTRACT_ID,
        data_contract_version=1,
        effective_from=NOW - timedelta(days=1),
        effective_until=NOW + timedelta(days=1),
    )
    other_purpose = MarketOptionExplanationProviderProcessingAuthorization(
        organization_id=organization_id,
        purpose="other-purpose",
        provider_profile="LOCAL_DETERMINISTIC_FAKE",
        provider_profile_version=1,
        data_contract_id=MARKET_OPTIONALITY_AI_EXPLANATION_SYNTHETIC_CONTRACT_ID,
        data_contract_version=1,
    )

    assert authorization.is_effective_at(NOW) is True
    assert authorization.authorization_version == 1
    assert len(authorization.authorization_digest) == 64
    assert other_purpose.authorization_digest != authorization.authorization_digest
    assert (
        MarketOptionExplanationProviderProcessingAuthorization(
            organization_id=organization_id,
            purpose=PURPOSE,
            provider_profile="LOCAL_DETERMINISTIC_FAKE",
            provider_profile_version=1,
            data_contract_id=MARKET_OPTIONALITY_AI_EXPLANATION_SYNTHETIC_CONTRACT_ID,
            data_contract_version=1,
            effective_until=NOW,
        ).is_effective_at(NOW)
        is False
    )
    with pytest.raises(ValueError, match="authorization_digest"):
        MarketOptionExplanationProviderProcessingAuthorization(
            organization_id=organization_id,
            purpose=PURPOSE,
            provider_profile="LOCAL_DETERMINISTIC_FAKE",
            provider_profile_version=1,
            data_contract_id=MARKET_OPTIONALITY_AI_EXPLANATION_SYNTHETIC_CONTRACT_ID,
            data_contract_version=1,
            authorization_digest="0" * 64,
        )


def test_explanation_request_identity_is_semantic_and_digestable() -> None:
    decision, evaluation, policy = _artifacts(purpose=PURPOSE)
    assessment = MarketOptionAssessmentService().assess(
        context=_context_from_artifacts(policy, decision),
        decision=decision,
        evaluation=evaluation,
    )
    context = MarketOptionExplanationGuardService().prepare_context(assessment=assessment)
    run_context = _ai_run_context(policy.organization_id, idempotency_key="idem-123")
    payload = MarketOptionExplanationDataContractService().build_prompt_payload(
        explanation_context=context,
        run_context=run_context,
    )

    identity = run_context.request_identity(assessment=assessment, prompt_payload=payload)
    changed_purpose_identity = MarketOptionExplanationRequestIdentity(
        organization_id=policy.organization_id,
        purpose="other-purpose",
        policy_id=policy.policy_id,
        policy_version=policy.version,
        reference_time=NOW,
        knowledge_cutoff=NOW,
        data_contract_id=MARKET_OPTIONALITY_AI_EXPLANATION_SYNTHETIC_CONTRACT_ID,
        data_contract_version=1,
        provider_profile="LOCAL_DETERMINISTIC_FAKE",
        provider_profile_version=1,
        prompt_template_id=payload.prompt_template_id,
        prompt_template_version=payload.prompt_template_version,
        idempotency_key="idem-123",
    )

    assert identity is not None
    assert len(identity.semantic_digest) == 64
    assert changed_purpose_identity.semantic_digest != identity.semantic_digest
    assert (
        MarketOptionExplanationRequestIdentity(
            organization_id=policy.organization_id,
            purpose=PURPOSE,
            policy_id=policy.policy_id,
            policy_version=policy.version,
            reference_time=NOW,
            knowledge_cutoff=NOW,
            data_contract_id=MARKET_OPTIONALITY_AI_EXPLANATION_SYNTHETIC_CONTRACT_ID,
            data_contract_version=1,
            provider_profile="LOCAL_DETERMINISTIC_FAKE",
            provider_profile_version=1,
            prompt_template_id=payload.prompt_template_id,
            prompt_template_version=payload.prompt_template_version,
            idempotency_key="idem-123",
            semantic_digest=identity.semantic_digest,
        ).semantic_digest
        == identity.semantic_digest
    )
    with pytest.raises(ValueError, match="semantic_digest"):
        MarketOptionExplanationRequestIdentity(
            organization_id=policy.organization_id,
            purpose=PURPOSE,
            policy_id=policy.policy_id,
            policy_version=policy.version,
            reference_time=NOW,
            knowledge_cutoff=NOW,
            data_contract_id=MARKET_OPTIONALITY_AI_EXPLANATION_SYNTHETIC_CONTRACT_ID,
            data_contract_version=1,
            provider_profile="LOCAL_DETERMINISTIC_FAKE",
            provider_profile_version=1,
            prompt_template_id=payload.prompt_template_id,
            prompt_template_version=payload.prompt_template_version,
            idempotency_key="idem-123",
            semantic_digest="0" * 64,
        )


def test_explanation_prompt_payload_digest_changes_with_template_version() -> None:
    decision, evaluation, policy = _artifacts(purpose=PURPOSE)
    assessment = MarketOptionAssessmentService().assess(
        context=_context_from_artifacts(policy, decision),
        decision=decision,
        evaluation=evaluation,
    )
    context = MarketOptionExplanationGuardService().prepare_context(assessment=assessment)

    payload_v1 = MarketOptionExplanationDataContractService().build_prompt_payload(
        explanation_context=context,
        run_context=_ai_run_context(policy.organization_id),
    )
    payload_v2 = MarketOptionExplanationDataContractService(
        prompt_template=MarketOptionExplanationPromptTemplate(template_version=2)
    ).build_prompt_payload(
        explanation_context=context,
        run_context=MarketOptionExplanationRunContext(
            data_contract_id=MARKET_OPTIONALITY_AI_EXPLANATION_SYNTHETIC_CONTRACT_ID,
            data_contract_version=1,
            processing_activity="SYNTHETIC_AI_EXPLANATION_VALIDATION",
            processing_authorization_organization_id=policy.organization_id,
            processing_authorization_purpose=PURPOSE,
            provider_profile="LOCAL_DETERMINISTIC_FAKE",
            provider_profile_version=1,
            model_name="deterministic-market-optionality-explainer",
        ),
    )

    assert payload_v2.prompt_template_version == 2
    assert payload_v1.prompt_template_digest != payload_v2.prompt_template_digest
    assert payload_v1.payload_digest != payload_v2.payload_digest


def test_explanation_data_contract_rejects_unapproved_contract() -> None:
    decision, evaluation, policy = _artifacts(purpose=PURPOSE)
    assessment = MarketOptionAssessmentService().assess(
        context=_context_from_artifacts(policy, decision),
        decision=decision,
        evaluation=evaluation,
    )
    context = MarketOptionExplanationGuardService().prepare_context(assessment=assessment)

    with pytest.raises(ValueError, match="data_contract_id"):
        MarketOptionExplanationDataContractService().build_prompt_payload(
            explanation_context=context,
            run_context=MarketOptionExplanationRunContext(
                data_contract_id="UNAPPROVED_AI_EXPLANATION_CONTRACT",
                data_contract_version=1,
                processing_activity="SYNTHETIC_AI_EXPLANATION_VALIDATION",
                processing_authorization_organization_id=policy.organization_id,
                processing_authorization_purpose=PURPOSE,
                provider_profile="LOCAL_DETERMINISTIC_FAKE",
                model_name="deterministic-market-optionality-explainer",
            ),
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
        run_context=_ai_run_context(policy.organization_id),
    )

    assert result.validation.accepted is True
    assert result.released_text is not None
    assert MarketOptionState.OPTION_OPEN.value in result.released_text
    assert result.canonical_fallback.state.value == MarketOptionState.OPTION_OPEN.value
    assert result.explanation_context.source_references["decision_id"] == str(decision.decision_id)
    assert result.prompt_payload.data_contract_id == (
        MARKET_OPTIONALITY_AI_EXPLANATION_SYNTHETIC_CONTRACT_ID
    )
    assert result.prompt_payload.fields["reference_time"] == NOW.isoformat()
    assert result.prompt_payload.fields["output_classification"] == (
        MARKET_OPTIONALITY_AI_EXPLANATION_OUTPUT_CLASSIFICATION
    )
    assert result.prompt_payload.fields["disclosure_restrictions"] == (
        MARKET_OPTIONALITY_AI_EXPLANATION_DISCLOSURE_RESTRICTIONS
    )
    assert result.prompt_payload.prompt_template_digest
    assert result.prompt_payload.guard_digest
    assert result.prompt_payload.payload_digest
    assert result.audit_envelope.accepted is True
    assert (
        result.audit_envelope.release_disposition
        is MarketOptionExplanationReleaseDisposition.RELEASE_APPROVED
    )
    assert result.audit_envelope.prompt_payload_digest == result.prompt_payload.payload_digest
    assert result.audit_envelope.provider_profile == "LOCAL_DETERMINISTIC_FAKE"
    assert result.audit_envelope.provider_profile_version == 1
    assert len(result.audit_envelope.provider_profile_digest) == 64
    assert result.audit_envelope.processing_authorization_reference == (
        "SYNTHETIC_AI_EXPLANATION_PROCESSING_AUTHORIZATION"
    )
    assert result.audit_envelope.processing_authorization_version == 1
    assert len(result.audit_envelope.processing_authorization_digest) == 64
    assert result.audit_envelope.released_output_digest is not None
    assert len(result.audit_envelope.released_output_digest) == 64
    assert result.audit_envelope.violation_codes == ()


def test_explanation_canonical_fallback_is_typed_and_digestable() -> None:
    decision, evaluation, policy = _artifacts(purpose=PURPOSE)
    assessment = MarketOptionAssessmentService().assess(
        context=_context_from_artifacts(policy, decision),
        decision=decision,
        evaluation=evaluation,
    )

    result = MarketOptionExplanationPipelineService().explain(
        assessment=assessment,
        run_context=_ai_run_context(policy.organization_id),
    )

    fallback = result.canonical_fallback
    fallback_mapping = fallback.as_mapping()
    assert fallback.state is MarketOptionState.OPTION_OPEN
    assert fallback.reversibility is MarketOptionReversibility.NOT_APPLICABLE
    assert fallback.policy_id == policy.policy_id
    assert fallback.policy_version == policy.version
    assert fallback.reference_time == NOW
    assert fallback.knowledge_cutoff == NOW
    assert fallback.output_classification == (
        MARKET_OPTIONALITY_AI_EXPLANATION_OUTPUT_CLASSIFICATION
    )
    assert fallback.disclosure_restrictions == (
        MARKET_OPTIONALITY_AI_EXPLANATION_DISCLOSURE_RESTRICTIONS
    )
    assert fallback.result_boundary == MARKET_ELIGIBILITY_RESULT_BOUNDARY
    assert fallback_mapping["state"] == MarketOptionState.OPTION_OPEN.value
    assert fallback_mapping["policy_id"] == str(policy.policy_id)
    assert fallback_mapping["output_classification"] == (
        MARKET_OPTIONALITY_AI_EXPLANATION_OUTPUT_CLASSIFICATION
    )
    assert fallback_mapping["disclosure_restrictions"] == (
        MARKET_OPTIONALITY_AI_EXPLANATION_DISCLOSURE_RESTRICTIONS
    )
    assert len(result.audit_envelope.canonical_fallback_digest) == 64


def test_explanation_audit_envelope_minimizes_prompt_output_and_raw_ids() -> None:
    decision, evaluation, policy = _artifacts(purpose=PURPOSE)
    assessment = MarketOptionAssessmentService().assess(
        context=_context_from_artifacts(policy, decision),
        decision=decision,
        evaluation=evaluation,
    )

    result = MarketOptionExplanationPipelineService().explain(
        assessment=assessment,
        run_context=_ai_run_context(policy.organization_id, idempotency_key="idem-secret"),
    )

    envelope_text = repr(result.audit_envelope)
    assert result.released_text is not None
    assert result.released_text not in envelope_text
    assert str(policy.organization_id) not in envelope_text
    assert str(decision.subject_id) not in envelope_text
    assert str(decision.decision_id) not in envelope_text
    assert str(evaluation.evaluation_id) not in envelope_text
    assert str(policy.policy_id) not in envelope_text
    assert "idem-secret" not in envelope_text
    assert result.audit_envelope.idempotency_reference is not None
    assert len(result.audit_envelope.idempotency_reference) == 64
    assert len(result.audit_envelope.source_reference_digest) == 64
    assert result.audit_envelope.source_reference_audit_references
    assert str(decision.decision_id) not in repr(
        result.audit_envelope.source_reference_audit_references
    )
    assert len(result.audit_envelope.canonical_fallback_digest) == 64


def test_explanation_audit_references_are_opaque_and_not_unkeyed_hashes() -> None:
    decision, evaluation, policy = _artifacts(purpose=PURPOSE)
    assessment = MarketOptionAssessmentService().assess(
        context=_context_from_artifacts(policy, decision),
        decision=decision,
        evaluation=evaluation,
    )

    result = MarketOptionExplanationPipelineService().explain(
        assessment=assessment,
        run_context=_ai_run_context(policy.organization_id),
    )

    references = result.audit_envelope.source_reference_audit_references
    assert references
    assert all(reference.key_version == 1 for reference in references)
    assert all(len(reference.reference) == 64 for reference in references)
    assert all(
        reference.reference != hashlib.sha256(str(decision.decision_id).encode()).hexdigest()
        for reference in references
    )
    assert {reference.alias for reference in references}.issubset(
        result.prompt_payload.source_reference_aliases
    )


def test_explanation_audit_envelope_requires_output_digest_only_for_release() -> None:
    with pytest.raises(ValueError, match="released_output_digest"):
        MarketOptionExplanationAuditEnvelope(
            data_contract_id=MARKET_OPTIONALITY_AI_EXPLANATION_SYNTHETIC_CONTRACT_ID,
            data_contract_version=1,
            processing_activity="SYNTHETIC_AI_EXPLANATION_VALIDATION",
            processing_authorization_reference=(
                "SYNTHETIC_AI_EXPLANATION_PROCESSING_AUTHORIZATION"
            ),
            processing_authorization_version=1,
            processing_authorization_digest="0" * 64,
            provider_profile="LOCAL_DETERMINISTIC_FAKE",
            provider_profile_version=1,
            provider_profile_digest="f" * 64,
            model_name="deterministic-market-optionality-explainer",
            explanation_schema="MARKET_OPTIONALITY_AI_EXPLANATION_CONTEXT_V1",
            prompt_template_id="market-optionality-explanation-canonical-summary",
            prompt_template_version=1,
            prompt_template_digest="a" * 64,
            guard_version=1,
            guard_digest="b" * 64,
            prompt_payload_digest="c" * 64,
            source_reference_digest="d" * 64,
            source_reference_audit_references=(
                MarketOptionExplanationOpaqueAuditReference(
                    alias="claim_source:1",
                    key_version=1,
                    reference="1" * 64,
                ),
            ),
            canonical_fallback_digest="e" * 64,
            idempotency_reference=None,
            released_output_digest=None,
            release_disposition=MarketOptionExplanationReleaseDisposition.RELEASE_APPROVED,
            accepted=True,
            violation_codes=(),
            limitations=(),
        )

    with pytest.raises(ValueError, match="release_disposition"):
        MarketOptionExplanationAuditEnvelope(
            data_contract_id=MARKET_OPTIONALITY_AI_EXPLANATION_SYNTHETIC_CONTRACT_ID,
            data_contract_version=1,
            processing_activity="SYNTHETIC_AI_EXPLANATION_VALIDATION",
            processing_authorization_reference=(
                "SYNTHETIC_AI_EXPLANATION_PROCESSING_AUTHORIZATION"
            ),
            processing_authorization_version=1,
            processing_authorization_digest="0" * 64,
            provider_profile="LOCAL_DETERMINISTIC_FAKE",
            provider_profile_version=1,
            provider_profile_digest="f" * 64,
            model_name="deterministic-market-optionality-explainer",
            explanation_schema="MARKET_OPTIONALITY_AI_EXPLANATION_CONTEXT_V1",
            prompt_template_id="market-optionality-explanation-canonical-summary",
            prompt_template_version=1,
            prompt_template_digest="a" * 64,
            guard_version=1,
            guard_digest="b" * 64,
            prompt_payload_digest="c" * 64,
            source_reference_digest="d" * 64,
            source_reference_audit_references=(
                MarketOptionExplanationOpaqueAuditReference(
                    alias="claim_source:1",
                    key_version=1,
                    reference="1" * 64,
                ),
            ),
            canonical_fallback_digest="e" * 64,
            idempotency_reference=None,
            released_output_digest=None,
            release_disposition=MarketOptionExplanationReleaseDisposition.NOT_RELEASED,
            accepted=True,
            violation_codes=(),
            limitations=(),
        )


def test_explanation_audit_record_is_derived_from_result_and_minimized() -> None:
    decision, evaluation, policy = _artifacts(purpose=PURPOSE)
    assessment = MarketOptionAssessmentService().assess(
        context=_context_from_artifacts(policy, decision),
        decision=decision,
        evaluation=evaluation,
    )
    result = MarketOptionExplanationPipelineService().explain(
        assessment=assessment,
        run_context=_ai_run_context(policy.organization_id, idempotency_key="idem-secret"),
    )

    record = MarketOptionExplanationAuditRecord.from_result(
        audit_id=TypedId.new("ai_explanation_audit"),
        result=result,
        requested_at=NOW,
        evaluated_at=NOW + timedelta(seconds=1),
        correlation_id=TypedId.new("correlation"),
    )

    record_text = repr(record)
    assert record.record_owner_organization_id == policy.organization_id
    assert record.policy_id == policy.policy_id
    assert record.release_disposition is MarketOptionExplanationReleaseDisposition.RELEASE_APPROVED
    assert record.released_output_digest == result.audit_envelope.released_output_digest
    assert record.idempotency_reference == result.audit_envelope.idempotency_reference
    assert len(record.record_digest()) == 64
    assert "idem-secret" not in record_text
    assert result.released_text is not None
    assert result.released_text not in record_text
    assert str(decision.subject_id) not in record_text
    assert str(decision.decision_id) not in record_text
    assert str(evaluation.evaluation_id) not in record_text


def test_explanation_audit_repository_is_append_only_and_owner_scoped() -> None:
    decision, evaluation, policy = _artifacts(purpose=PURPOSE)
    assessment = MarketOptionAssessmentService().assess(
        context=_context_from_artifacts(policy, decision),
        decision=decision,
        evaluation=evaluation,
    )
    result = MarketOptionExplanationPipelineService().explain(
        assessment=assessment,
        run_context=_ai_run_context(policy.organization_id),
    )
    record = MarketOptionExplanationAuditRecord.from_result(
        audit_id=TypedId.new("ai_explanation_audit"),
        result=result,
        requested_at=NOW,
        evaluated_at=NOW,
        correlation_id=TypedId.new("correlation"),
    )
    repository = InMemoryMarketOptionExplanationAuditRepository()

    repository.append(record)

    assert repository.get(record.audit_id) == record
    assert repository.list_for_owner(policy.organization_id) == (record,)
    assert repository.list_for_owner(OrganizationId.new()) == ()
    with pytest.raises(ValueError, match="append-only"):
        repository.append(record)


def test_explanation_audit_repository_queries_are_owner_scoped() -> None:
    decision, evaluation, policy = _artifacts(purpose=PURPOSE)
    assessment = MarketOptionAssessmentService().assess(
        context=_context_from_artifacts(policy, decision),
        decision=decision,
        evaluation=evaluation,
    )
    result = MarketOptionExplanationPipelineService().explain(
        assessment=assessment,
        run_context=_ai_run_context(policy.organization_id, idempotency_key="idem-secret"),
    )
    correlation_id = TypedId.new("correlation")
    record = MarketOptionExplanationAuditRecord.from_result(
        audit_id=TypedId.new("ai_explanation_audit"),
        result=result,
        requested_at=NOW,
        evaluated_at=NOW,
        correlation_id=correlation_id,
    )
    repository = InMemoryMarketOptionExplanationAuditRepository()
    repository.append(record)

    assert repository.find_by_correlation_id(
        record_owner_organization_id=policy.organization_id,
        correlation_id=correlation_id,
    ) == (record,)
    assert (
        repository.find_by_correlation_id(
            record_owner_organization_id=OrganizationId.new(),
            correlation_id=correlation_id,
        )
        == ()
    )
    assert record.idempotency_reference is not None
    assert repository.find_by_idempotency_reference(
        record_owner_organization_id=policy.organization_id,
        idempotency_reference=record.idempotency_reference,
    ) == (record,)
    assert (
        repository.find_by_idempotency_reference(
            record_owner_organization_id=OrganizationId.new(),
            idempotency_reference=record.idempotency_reference,
        )
        == ()
    )


def test_explanation_pipeline_persists_audit_record_before_ai_release() -> None:
    decision, evaluation, policy = _artifacts(purpose=PURPOSE)
    assessment = MarketOptionAssessmentService().assess(
        context=_context_from_artifacts(policy, decision),
        decision=decision,
        evaluation=evaluation,
    )
    repository = InMemoryMarketOptionExplanationAuditRepository()
    audit_context = MarketOptionExplanationAuditRecordContext(
        audit_id=TypedId.new("ai_explanation_audit"),
        requested_at=NOW,
        evaluated_at=NOW,
        correlation_id=TypedId.new("correlation"),
    )

    result = MarketOptionExplanationPipelineService(audit_repository=repository).explain(
        assessment=assessment,
        run_context=_ai_run_context(policy.organization_id),
        audit_record_context=audit_context,
    )

    assert result.released_text is not None
    assert result.audit_record is not None
    assert repository.get(result.audit_record.audit_id) == result.audit_record
    assert repository.list_for_owner(policy.organization_id) == (result.audit_record,)
    assert (
        result.audit_record.release_disposition
        is MarketOptionExplanationReleaseDisposition.RELEASE_APPROVED
    )


def test_explanation_pipeline_requires_audit_context_when_repository_is_configured() -> None:
    decision, evaluation, policy = _artifacts(purpose=PURPOSE)
    assessment = MarketOptionAssessmentService().assess(
        context=_context_from_artifacts(policy, decision),
        decision=decision,
        evaluation=evaluation,
    )

    with pytest.raises(ValueError, match="audit_record_context"):
        MarketOptionExplanationPipelineService(
            audit_repository=InMemoryMarketOptionExplanationAuditRepository()
        ).explain(
            assessment=assessment,
            run_context=_ai_run_context(policy.organization_id),
        )


def test_explanation_pipeline_uses_audit_context_without_owner_override() -> None:
    decision, evaluation, policy = _artifacts(purpose=PURPOSE)
    assessment = MarketOptionAssessmentService().assess(
        context=_context_from_artifacts(policy, decision),
        decision=decision,
        evaluation=evaluation,
    )
    repository = InMemoryMarketOptionExplanationAuditRepository()
    audit_context = MarketOptionExplanationAuditRecordContext(
        audit_id=TypedId.new("ai_explanation_audit"),
        requested_at=NOW,
        evaluated_at=NOW + timedelta(seconds=2),
        correlation_id=TypedId.new("correlation"),
    )

    result = MarketOptionExplanationPipelineService(audit_repository=repository).explain(
        assessment=assessment,
        run_context=_ai_run_context(policy.organization_id),
        audit_record_context=audit_context,
    )

    assert result.audit_record is not None
    assert result.audit_record.audit_id == audit_context.audit_id
    assert result.audit_record.requested_at == audit_context.requested_at
    assert result.audit_record.evaluated_at == audit_context.evaluated_at
    assert result.audit_record.correlation_id == audit_context.correlation_id
    assert result.audit_record.record_owner_organization_id == policy.organization_id


def test_explanation_pipeline_blocks_ai_release_when_audit_append_fails() -> None:
    class FailingAuditRepository(InMemoryMarketOptionExplanationAuditRepository):
        def append(self, record):  # type: ignore[no-untyped-def]
            raise RuntimeError("audit storage unavailable with diagnostics")

    decision, evaluation, policy = _artifacts(purpose=PURPOSE)
    assessment = MarketOptionAssessmentService().assess(
        context=_context_from_artifacts(policy, decision),
        decision=decision,
        evaluation=evaluation,
    )
    audit_context = MarketOptionExplanationAuditRecordContext(
        audit_id=TypedId.new("ai_explanation_audit"),
        requested_at=NOW,
        evaluated_at=NOW,
        correlation_id=TypedId.new("correlation"),
    )

    result = MarketOptionExplanationPipelineService(
        audit_repository=FailingAuditRepository()
    ).explain(
        assessment=assessment,
        run_context=_ai_run_context(policy.organization_id),
        audit_record_context=audit_context,
    )

    assert result.released_text is None
    assert result.audit_record is None
    assert (
        result.audit_envelope.release_disposition
        is MarketOptionExplanationReleaseDisposition.NOT_RELEASED
    )
    assert result.audit_envelope.accepted is False
    assert result.audit_envelope.released_output_digest is None
    assert MarketOptionExplanationViolation.AUDIT_PERSISTENCE_FAILED in (
        result.validation.violations
    )
    assert "storage unavailable" not in repr(result.audit_envelope)


def test_explanation_pipeline_falls_back_when_provider_text_claims_authority() -> None:
    class InventingProvider(DeterministicMarketOptionExplanationTextProvider):
        def generate_text(self, *, prompt_payload, run_context):  # type: ignore[no-untyped-def]
            assert "organization_id" not in prompt_payload.fields
            assert "subject_id" not in prompt_payload.fields
            return "Este animal está certificado e eligible para export allowed."

    decision, evaluation, policy = _artifacts(purpose=PURPOSE)
    assessment = MarketOptionAssessmentService().assess(
        context=_context_from_artifacts(policy, decision),
        decision=decision,
        evaluation=evaluation,
    )

    result = MarketOptionExplanationPipelineService(text_provider=InventingProvider()).explain(
        assessment=assessment,
        run_context=_ai_run_context(policy.organization_id),
    )

    assert result.validation.accepted is False
    assert result.released_text is None
    assert (
        result.audit_envelope.release_disposition
        is MarketOptionExplanationReleaseDisposition.NOT_RELEASED
    )
    assert result.canonical_fallback.state.value == MarketOptionState.OPTION_OPEN.value
    assert result.audit_envelope.accepted is False
    assert result.audit_envelope.released_output_digest is None
    assert result.audit_envelope.prompt_payload_digest == result.prompt_payload.payload_digest
    assert MarketOptionExplanationViolation.PROHIBITED_TEXT_CONTENT in (
        result.validation.violations
    )
    assert MarketOptionExplanationViolation.PROHIBITED_TEXT_CONTENT.value in (
        result.audit_envelope.violation_codes
    )


def test_explanation_pipeline_falls_back_when_provider_is_unavailable() -> None:
    class FailingProvider(DeterministicMarketOptionExplanationTextProvider):
        def generate_text(self, *, prompt_payload, run_context):  # type: ignore[no-untyped-def]
            assert "organization_id" not in prompt_payload.fields
            assert "subject_id" not in prompt_payload.fields
            raise RuntimeError("provider internal timeout with diagnostic token")

    decision, evaluation, policy = _artifacts(purpose=PURPOSE)
    assessment = MarketOptionAssessmentService().assess(
        context=_context_from_artifacts(policy, decision),
        decision=decision,
        evaluation=evaluation,
    )

    result = MarketOptionExplanationPipelineService(text_provider=FailingProvider()).explain(
        assessment=assessment,
        run_context=_ai_run_context(policy.organization_id),
    )

    envelope_text = repr(result.audit_envelope)
    assert result.validation.accepted is False
    assert result.released_text is None
    assert result.canonical_fallback.state.value == MarketOptionState.OPTION_OPEN.value
    assert result.audit_envelope.accepted is False
    assert result.audit_envelope.released_output_digest is None
    assert MarketOptionExplanationViolation.PROVIDER_UNAVAILABLE in (result.validation.violations)
    assert MarketOptionExplanationViolation.PROVIDER_UNAVAILABLE.value in (
        result.audit_envelope.violation_codes
    )
    assert "provider internal timeout" not in envelope_text
    assert "diagnostic token" not in envelope_text


def test_explanation_pipeline_does_not_call_provider_when_profile_is_suspended() -> None:
    class UnexpectedProvider(DeterministicMarketOptionExplanationTextProvider):
        def generate_text(self, *, prompt_payload, run_context):  # type: ignore[no-untyped-def]
            raise AssertionError("provider should not be called")

    decision, evaluation, policy = _artifacts(purpose=PURPOSE)
    assessment = MarketOptionAssessmentService().assess(
        context=_context_from_artifacts(policy, decision),
        decision=decision,
        evaluation=evaluation,
    )

    result = MarketOptionExplanationPipelineService(text_provider=UnexpectedProvider()).explain(
        assessment=assessment,
        run_context=MarketOptionExplanationRunContext(
            data_contract_id=MARKET_OPTIONALITY_AI_EXPLANATION_SYNTHETIC_CONTRACT_ID,
            data_contract_version=1,
            processing_activity="SYNTHETIC_AI_EXPLANATION_VALIDATION",
            model_name="deterministic-market-optionality-explainer",
            processing_authorization_organization_id=policy.organization_id,
            processing_authorization_purpose=PURPOSE,
            provider_profile_state=MarketOptionExplanationProviderProfileState.SUSPENDED,
        ),
    )

    assert result.validation.accepted is False
    assert result.released_text is None
    assert MarketOptionExplanationViolation.PROVIDER_PROFILE_UNAVAILABLE in (
        result.validation.violations
    )
    assert MarketOptionExplanationViolation.PROVIDER_PROFILE_UNAVAILABLE.value in (
        result.audit_envelope.violation_codes
    )


def test_explanation_pipeline_does_not_call_provider_without_processing_authorization() -> None:
    class UnexpectedProvider(DeterministicMarketOptionExplanationTextProvider):
        def generate_text(self, *, prompt_payload, run_context):  # type: ignore[no-untyped-def]
            raise AssertionError("provider should not be called")

    decision, evaluation, policy = _artifacts(purpose=PURPOSE)
    assessment = MarketOptionAssessmentService().assess(
        context=_context_from_artifacts(policy, decision),
        decision=decision,
        evaluation=evaluation,
    )

    result = MarketOptionExplanationPipelineService(text_provider=UnexpectedProvider()).explain(
        assessment=assessment,
        run_context=_ai_run_context(policy.organization_id, purpose="other-purpose"),
    )

    assert result.validation.accepted is False
    assert result.released_text is None
    assert (
        result.audit_envelope.release_disposition
        is MarketOptionExplanationReleaseDisposition.NOT_RELEASED
    )
    assert MarketOptionExplanationViolation.PROVIDER_PROCESSING_UNAUTHORIZED in (
        result.validation.violations
    )
    assert MarketOptionExplanationViolation.PROVIDER_PROCESSING_UNAUTHORIZED.value in (
        result.audit_envelope.violation_codes
    )


def test_explanation_pipeline_does_not_call_provider_when_profile_is_expired() -> None:
    class UnexpectedProvider(DeterministicMarketOptionExplanationTextProvider):
        def generate_text(self, *, prompt_payload, run_context):  # type: ignore[no-untyped-def]
            raise AssertionError("provider should not be called")

    decision, evaluation, policy = _artifacts(purpose=PURPOSE)
    assessment = MarketOptionAssessmentService().assess(
        context=_context_from_artifacts(policy, decision),
        decision=decision,
        evaluation=evaluation,
    )

    result = MarketOptionExplanationPipelineService(text_provider=UnexpectedProvider()).explain(
        assessment=assessment,
        run_context=MarketOptionExplanationRunContext(
            data_contract_id=MARKET_OPTIONALITY_AI_EXPLANATION_SYNTHETIC_CONTRACT_ID,
            data_contract_version=1,
            processing_activity="SYNTHETIC_AI_EXPLANATION_VALIDATION",
            model_name="deterministic-market-optionality-explainer",
            processing_authorization_organization_id=policy.organization_id,
            processing_authorization_purpose=PURPOSE,
            provider_profile_effective_until=NOW,
        ),
    )

    assert result.validation.accepted is False
    assert result.released_text is None
    assert MarketOptionExplanationViolation.PROVIDER_PROFILE_UNAVAILABLE in (
        result.validation.violations
    )


def test_explanation_run_context_requires_governance_references() -> None:
    with pytest.raises(ValueError, match="data_contract_id"):
        MarketOptionExplanationRunContext(
            data_contract_id="",
            data_contract_version=1,
            processing_activity="SYNTHETIC_AI_EXPLANATION_VALIDATION",
            processing_authorization_organization_id=OrganizationId.new(),
            processing_authorization_purpose=PURPOSE,
            provider_profile="LOCAL_DETERMINISTIC_FAKE",
            model_name="deterministic-market-optionality-explainer",
        )

    with pytest.raises(ValueError, match="data_contract_version"):
        MarketOptionExplanationRunContext(
            data_contract_id=MARKET_OPTIONALITY_AI_EXPLANATION_SYNTHETIC_CONTRACT_ID,
            data_contract_version=0,
            processing_activity="SYNTHETIC_AI_EXPLANATION_VALIDATION",
            processing_authorization_organization_id=OrganizationId.new(),
            processing_authorization_purpose=PURPOSE,
            provider_profile="LOCAL_DETERMINISTIC_FAKE",
            model_name="deterministic-market-optionality-explainer",
        )
