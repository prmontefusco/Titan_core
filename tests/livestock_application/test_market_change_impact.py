"""Corte 1 do NEXT-07: impacto potencial, sem reavaliação ou escrita."""

from dataclasses import replace
from datetime import UTC, datetime

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
from packages.livestock_application.market_change_impact import (
    MarketChangeImpactContext,
    MarketChangeImpactInput,
    MarketChangeImpactService,
    MarketChangeImpactStatus,
)
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference

NOW = datetime(2026, 8, 12, tzinfo=UTC)


def _artifact(
    *,
    organization: OrganizationId | None = None,
    purpose: str = "market-test-a",
    legacy: bool = False,
    boundary: str = "INTERNAL_ONLY",
    policy_id: TypedId | None = None,
) -> tuple[Decision, Evaluation, Policy]:
    organization = organization or OrganizationId.new()
    subject = TypedId.new("animal")
    policy = Policy(
        policy_id or TypedId.new("policy"),
        organization,
        "MARKET_TEST_A",
        "v1",
        "test",
        1,
        PolicyStatus.PUBLISHED,
        NOW,
        None,
        NOW,
    )
    snapshot = FactSnapshot.create(organization, subject, NOW, (), NOW, NOW)
    rules = (("rule-test", 1),)
    normative = (
        None
        if legacy
        else NormativeBasisSnapshot(
            schema_version=1,
            normative_basis_id=TypedId.new("normative_basis"),
            normative_basis_code="BASIS",
            normative_basis_version=1,
            policy_id=policy.policy_id,
            policy_code=policy.code,
            policy_version=1,
            rule_versions=rules,
            purpose=purpose,
            jurisdiction="TEST",
            intended_use="TEST",
            reference_time=NOW,
            knowledge_cutoff=NOW,
            approved_by="actor:test",
            approval_authority="internal",
            approved_at=NOW,
            references=(
                NormativeReferenceSnapshot(
                    "TEST",
                    "1",
                    "1",
                    "a" * 64,
                    "sha256",
                    NormativeSourceClassification.INTERNAL_TEST,
                ),
            ),
            limitations=(f"RECOGNITION_BOUNDARY:{boundary}",),
        )
    )
    context_hash = compute_context_hash(
        policy.policy_id,
        1,
        purpose,
        1,
        rules,
        None if normative is None else normative.snapshot_digest,
    )
    evaluation = Evaluation(
        TypedId.new("evaluation"),
        organization,
        subject,
        purpose,
        policy.policy_id,
        1,
        snapshot,
        (),
        EvaluationOutcome.CONDICOES_SATISFEITAS,
        NOW,
        1,
        "b" * 64,
        context_hash,
        normative,
        None,
        rules,
    )
    reason = DecisionReason(DecisionReasonCode.REGRA_ATENDIDA, "teste", "rule-test")
    authority = TypedId.new("authority_profile")
    decision = Decision(
        TypedId.new("decision"),
        organization,
        subject,
        purpose,
        evaluation.evaluation_id,
        evaluation.evaluation_hash,
        policy.policy_id,
        1,
        DecisionResult.APROVADA,
        (reason,),
        snapshot.snapshot_hash,
        NOW,
        1,
        compute_decision_hash(
            evaluation.evaluation_hash,
            subject,
            purpose,
            DecisionResult.APROVADA,
            (reason,),
            authority,
            DecisionEmissionMethod.AUTOMATED,
        ),
        authority,
        UniversalReference(TypedId.new("service_identity"), organization, 1),
        DecisionEmissionMethod.AUTOMATED,
    )
    return decision, evaluation, policy


def _context(policy: Policy) -> MarketChangeImpactContext:
    return MarketChangeImpactContext(
        policy.organization_id,
        "market-test-a",
        policy.policy_id,
        1,
        TypedId.new("policy"),
        2,
        NOW,
        NOW,
    )


def test_policy_change_marks_only_exact_historical_context_as_affected_without_mutation() -> None:
    decision, evaluation, policy = _artifact()
    original_hash, original_result = decision.decision_hash, decision.result
    assessment = MarketChangeImpactService().assess(
        context=_context(policy), inputs=(MarketChangeImpactInput(decision, evaluation),)
    )
    assert assessment.entries[0].status is MarketChangeImpactStatus.AFFECTED
    assert assessment.reassessment_required_count == 1
    assert decision.decision_hash == original_hash
    assert decision.result is original_result


def test_other_purpose_organization_and_legacy_snapshot_are_not_positive_impact() -> None:
    decision, evaluation, policy = _artifact()
    other_purpose, other_purpose_eval, _ = _artifact(
        organization=policy.organization_id, purpose="market-test-b"
    )
    other_org, other_org_eval, _ = _artifact()
    legacy, legacy_eval, _ = _artifact(
        organization=policy.organization_id, legacy=True, policy_id=policy.policy_id
    )
    assessment = MarketChangeImpactService().assess(
        context=_context(policy),
        inputs=(
            MarketChangeImpactInput(decision, evaluation),
            MarketChangeImpactInput(other_purpose, other_purpose_eval),
            MarketChangeImpactInput(other_org, other_org_eval),
            MarketChangeImpactInput(legacy, legacy_eval),
        ),
    )
    assert [item.status for item in assessment.entries].count(
        MarketChangeImpactStatus.AFFECTED
    ) == 1
    assert any(item.status is MarketChangeImpactStatus.LIMITED for item in assessment.entries)
    assert assessment.reassessment_required_count == 1


def test_impact_order_is_stable_and_temporal_or_boundary_mismatch_is_limited() -> None:
    decision, evaluation, policy = _artifact()
    assert evaluation.normative_basis_snapshot is not None
    temporal_normative = replace(
        evaluation.normative_basis_snapshot,
        reference_time=datetime(2026, 8, 11, tzinfo=UTC),
        snapshot_digest="",
    )
    temporal_eval = replace(evaluation, normative_basis_snapshot=temporal_normative)
    temporal_decision = replace(
        decision, decision_id=TypedId.new("decision"), evaluation_id=temporal_eval.evaluation_id
    )
    boundary_decision, boundary_eval, _ = _artifact(
        organization=policy.organization_id,
        boundary="EXTERNAL_RECOGNITION_NOT_DEMONSTRATED",
        policy_id=policy.policy_id,
    )
    context = _context(policy)
    first = MarketChangeImpactService().assess(
        context=context,
        inputs=(
            MarketChangeImpactInput(decision, evaluation),
            MarketChangeImpactInput(boundary_decision, boundary_eval),
        ),
    )
    second = MarketChangeImpactService().assess(
        context=context,
        inputs=(
            MarketChangeImpactInput(boundary_decision, boundary_eval),
            MarketChangeImpactInput(decision, evaluation),
        ),
    )
    assert [(item.subject_id, item.decision_id) for item in first.entries] == [
        (item.subject_id, item.decision_id) for item in second.entries
    ]
    limited = MarketChangeImpactService().assess(
        context=context, inputs=(MarketChangeImpactInput(temporal_decision, temporal_eval),)
    )
    assert limited.entries[0].status is MarketChangeImpactStatus.LIMITED
