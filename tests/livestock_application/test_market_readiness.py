"""Corte 1 do NEXT-06: readiness pura e seleção sem efeitos colaterais."""

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from packages.core_domain.decision import (
    Decision,
    DecisionReason,
    DecisionReasonCode,
    DecisionResult,
    compute_decision_hash,
)
from packages.core_domain.decision_authority import DecisionEmissionMethod
from packages.core_domain.evaluation import Evaluation, EvaluationOutcome, compute_context_hash
from packages.core_domain.facts import FactSnapshot
from packages.core_domain.normative import (
    NormativeBasisSnapshot,
    NormativeReferenceSnapshot,
    NormativeSourceClassification,
)
from packages.core_domain.policy import Policy, PolicyStatus
from packages.livestock_application.market_readiness import (
    MARKET_ELIGIBILITY_RESULT_BOUNDARY,
    SELECTION_STRATEGY_STABLE_SUBJECT_ID,
    SELECTION_STRATEGY_VERSION,
    MarketReadinessContext,
    MarketReadinessInput,
    MarketReadinessService,
    MarketReadinessStatus,
)
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference

NOW = datetime(2026, 8, 12, tzinfo=UTC)
PURPOSE = "market-test-a"


def _artifacts(
    *,
    subject_id: TypedId | None = None,
    organization_id: OrganizationId | None = None,
    result: DecisionResult = DecisionResult.APROVADA,
    purpose: str = PURPOSE,
    policy_id: TypedId | None = None,
    policy_version: int = 1,
    reference_time: datetime = NOW,
    knowledge_cutoff: datetime = NOW,
    normative: bool = True,
    boundary: str = "INTERNAL_ONLY",
) -> tuple[Decision, Evaluation, Policy]:
    organization_id = organization_id or OrganizationId.new()
    subject_id = subject_id or TypedId.new("animal")
    policy = Policy(
        policy_id=policy_id or TypedId.new("policy"),
        organization_id=organization_id,
        code="MARKET_TEST_A",
        name="Policy de teste",
        description="Somente para teste.",
        version=policy_version,
        status=PolicyStatus.PUBLISHED,
        valid_from=NOW,
        published_at=NOW,
    )
    snapshot = FactSnapshot.create(
        organization_id=organization_id,
        target_id=subject_id,
        as_of=NOW,
        facts=(),
        reference_time=reference_time,
        knowledge_cutoff=knowledge_cutoff,
    )
    rule_versions = (("market-test-rule", 1),)
    normative_snapshot = (
        NormativeBasisSnapshot(
            schema_version=1,
            normative_basis_id=TypedId.new("normative_basis"),
            normative_basis_code="MARKET_TEST_A_BASIS",
            normative_basis_version=1,
            policy_id=policy.policy_id,
            policy_code=policy.code,
            policy_version=policy.version,
            rule_versions=rule_versions,
            purpose=purpose,
            jurisdiction="TEST",
            intended_use="INTERNAL_TEST_ONLY",
            reference_time=reference_time,
            knowledge_cutoff=knowledge_cutoff,
            approved_by="actor:test",
            approval_authority="internal",
            approved_at=NOW,
            references=(
                NormativeReferenceSnapshot(
                    instrument_code="TEST",
                    instrument_version="1",
                    provision="1",
                    content_digest="a" * 64,
                    digest_algorithm="sha256",
                    source_classification=NormativeSourceClassification.INTERNAL_TEST,
                ),
            ),
            limitations=(f"RECOGNITION_BOUNDARY:{boundary}",),
        )
        if normative
        else None
    )
    context_hash = compute_context_hash(
        policy_id=policy.policy_id,
        policy_version=policy.version,
        purpose=purpose,
        engine_version=1,
        rule_versions=rule_versions,
        normative_basis_snapshot_digest=(
            None if normative_snapshot is None else normative_snapshot.snapshot_digest
        ),
    )
    evaluation = Evaluation(
        evaluation_id=TypedId.new("evaluation"),
        organization_id=organization_id,
        subject_id=subject_id,
        purpose=purpose,
        policy_id=policy.policy_id,
        policy_version=policy.version,
        fact_snapshot=snapshot,
        rule_results=(),
        outcome=EvaluationOutcome.CONDICOES_SATISFEITAS,
        evaluated_at=NOW,
        engine_version=1,
        evaluation_hash="b" * 64,
        context_hash=context_hash,
        normative_basis_snapshot=normative_snapshot,
        rule_versions=rule_versions,
    )
    reason = DecisionReason(
        code=DecisionReasonCode.REGRA_ATENDIDA,
        message="Conclusão de teste.",
        rule_code="market-test-rule",
    )
    authority_profile_id = TypedId.new("authority_profile")
    decision = Decision(
        decision_id=TypedId.new("decision"),
        organization_id=organization_id,
        subject_id=subject_id,
        purpose=purpose,
        evaluation_id=evaluation.evaluation_id,
        evaluation_hash=evaluation.evaluation_hash,
        policy_id=policy.policy_id,
        policy_version=policy.version,
        result=result,
        reasons=(reason,),
        snapshot_hash=snapshot.snapshot_hash,
        issued_at=NOW,
        engine_version=1,
        decision_hash=compute_decision_hash(
            evaluation_hash=evaluation.evaluation_hash,
            subject_id=subject_id,
            purpose=purpose,
            result=result,
            reasons=(reason,),
            authority_profile_id=authority_profile_id,
            emission_method=DecisionEmissionMethod.AUTOMATED,
        ),
        authority_profile_id=authority_profile_id,
        authority_reference=UniversalReference(TypedId.new("service_identity"), organization_id, 1),
        emission_method=DecisionEmissionMethod.AUTOMATED,
    )
    return decision, evaluation, policy


def _context(policy: Policy) -> MarketReadinessContext:
    return MarketReadinessContext(
        organization_id=policy.organization_id,
        purpose=PURPOSE,
        policy_id=policy.policy_id,
        policy_version=policy.version,
        reference_time=NOW,
        knowledge_cutoff=NOW,
    )


def test_report_classifies_decision_results_without_reexecuting_rules() -> None:
    ready, ready_evaluation, policy = _artifacts()
    rejected, rejected_evaluation, _ = _artifacts(
        organization_id=policy.organization_id,
        policy_id=policy.policy_id,
        result=DecisionResult.REJEITADA,
    )
    conditioned, conditioned_evaluation, _ = _artifacts(
        organization_id=policy.organization_id,
        policy_id=policy.policy_id,
        result=DecisionResult.APROVADA_COM_RESTRICOES,
    )
    indeterminate, indeterminate_evaluation, _ = _artifacts(
        organization_id=policy.organization_id,
        policy_id=policy.policy_id,
        result=DecisionResult.INDETERMINADA,
    )

    report = MarketReadinessService().build_report(
        context=_context(policy),
        inputs=(
            MarketReadinessInput(ready.subject_id, ready, ready_evaluation),
            MarketReadinessInput(rejected.subject_id, rejected, rejected_evaluation),
            MarketReadinessInput(conditioned.subject_id, conditioned, conditioned_evaluation),
            MarketReadinessInput(indeterminate.subject_id, indeterminate, indeterminate_evaluation),
            MarketReadinessInput(TypedId.new("animal")),
        ),
    )

    assert {entry.status for entry in report.entries} == {
        MarketReadinessStatus.READY,
        MarketReadinessStatus.NOT_READY,
        MarketReadinessStatus.CONDITIONED,
        MarketReadinessStatus.INDETERMINATE,
        MarketReadinessStatus.NOT_EVALUATED,
    }
    assert report.counts[MarketReadinessStatus.READY] == 1
    assert report.result_boundary == MARKET_ELIGIBILITY_RESULT_BOUNDARY


def test_mismatched_policy_requires_reassessment_without_changing_decision() -> None:
    decision, evaluation, policy_v1 = _artifacts()
    policy_v2 = replace(policy_v1, policy_id=TypedId.new("policy"), version=2)
    context = _context(policy_v2)

    report = MarketReadinessService().build_report(
        context=context,
        inputs=(MarketReadinessInput(decision.subject_id, decision, evaluation),),
    )

    assert report.entries[0].status is MarketReadinessStatus.REASSESSMENT_REQUIRED
    assert decision.result is DecisionResult.APROVADA


def test_decision_for_another_market_purpose_does_not_contribute_as_ready() -> None:
    decision, evaluation, policy = _artifacts(purpose="market-test-b")

    report = MarketReadinessService().build_report(
        context=_context(policy),
        inputs=(MarketReadinessInput(decision.subject_id, decision, evaluation),),
    )

    assert report.entries[0].status is MarketReadinessStatus.REASSESSMENT_REQUIRED


def test_missing_normative_anchor_or_boundary_is_indeterminate_not_recomputed() -> None:
    legacy, legacy_evaluation, policy = _artifacts(normative=False)
    missing_boundary, missing_boundary_evaluation, _ = _artifacts(
        organization_id=policy.organization_id,
        policy_id=policy.policy_id,
        boundary="EXTERNAL_RECOGNITION_NOT_DEMONSTRATED",
    )

    report = MarketReadinessService().build_report(
        context=_context(policy),
        inputs=(
            MarketReadinessInput(legacy.subject_id, legacy, legacy_evaluation),
            MarketReadinessInput(
                missing_boundary.subject_id, missing_boundary, missing_boundary_evaluation
            ),
        ),
    )

    assert all(entry.status is MarketReadinessStatus.INDETERMINATE for entry in report.entries)
    assert {gap.code for gap in report.gap_summary} == {
        "NORMATIVE_BASIS_SNAPSHOT_LEGACY_ABSENT",
        "NORMATIVE_BASIS_SNAPSHOT_UNAVAILABLE",
        "RECOGNITION_BOUNDARY_UNAVAILABLE",
    }


def test_selection_is_stable_versioned_and_never_selects_non_ready() -> None:
    organization = OrganizationId.new()
    policy_id = TypedId.new("policy")
    artifacts = [
        _artifacts(
            subject_id=TypedId("animal", value),
            organization_id=organization,
            policy_id=policy_id,
        )
        for value in sorted(
            [TypedId.new("animal").value for _ in range(3)],
            reverse=True,
        )
    ]
    policy = artifacts[0][2]
    inputs = tuple(
        MarketReadinessInput(decision.subject_id, decision, evaluation)
        for decision, evaluation, _ in reversed(artifacts)
    )
    report = MarketReadinessService().build_report(context=_context(policy), inputs=inputs)
    selection = MarketReadinessService().select_candidates(report=report, requested_count=5)
    report_in_original_order = MarketReadinessService().build_report(
        context=_context(policy),
        inputs=tuple(
            MarketReadinessInput(decision.subject_id, decision, evaluation)
            for decision, evaluation, _ in artifacts
        ),
    )
    selection_in_original_order = MarketReadinessService().select_candidates(
        report=report_in_original_order,
        requested_count=5,
    )

    selected_ids = [str(item.subject_id.value) for item in selection.selected_entries]
    assert selected_ids == sorted(
        str(decision.subject_id.value) for decision, _evaluation, _policy in artifacts
    )
    assert selected_ids == [
        str(item.subject_id.value) for item in selection_in_original_order.selected_entries
    ]
    assert selection.shortage == 2
    assert selection.selection_strategy == SELECTION_STRATEGY_STABLE_SUBJECT_ID
    assert selection.selection_strategy_version == SELECTION_STRATEGY_VERSION
    assert all(item.status is MarketReadinessStatus.READY for item in selection.selected_entries)


def test_duplicate_population_and_invalid_selection_size_are_rejected() -> None:
    decision, evaluation, policy = _artifacts()
    service = MarketReadinessService()
    entry = MarketReadinessInput(decision.subject_id, decision, evaluation)

    with pytest.raises(ValueError, match="repetido"):
        service.build_report(context=_context(policy), inputs=(entry, entry))

    report = service.build_report(context=_context(policy), inputs=(entry,))
    with pytest.raises(ValueError, match="requested_count"):
        service.select_candidates(report=report, requested_count=0)
