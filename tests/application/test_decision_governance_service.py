"""Testes para o ciclo proposta -> revisão -> emissão humana (ADR-0054)."""

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from packages.core_application.decision_governance_service import DecisionGovernanceService
from packages.core_application.decision_service import DecisionService
from packages.core_application.evaluation_service import (
    PolicyEvaluationService,
    RuleEvaluationEngine,
)
from packages.core_domain.decision_authority import DecisionEmissionMethod
from packages.core_domain.decision_governance import (
    DecisionAuthorityProfile,
    ReviewConclusion,
)
from packages.core_domain.evaluation import Evaluation, EvaluationOutcome, compute_evaluation_hash
from packages.core_domain.facts import Fact, FactSnapshot
from packages.core_domain.policy import Policy
from packages.core_domain.rule import ComparisonOperator, Rule, RuleCondition, SeverityLevel
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference


def _policy(org_id: OrganizationId) -> Policy:
    return Policy.create_draft(
        organization_id=org_id, code="pol-sanitaria", name="Política Sanitária"
    ).publish()


def _rule(policy: Policy, code: str, severity: SeverityLevel, expected: str = "approved") -> Rule:
    return Rule.create(
        policy_id=policy.policy_id,
        organization_id=policy.organization_id,
        code=code,
        name=code,
        severity=severity,
        conditions=(
            RuleCondition(
                fact_type="sanitary.attestation",
                payload_key="result",
                operator=ComparisonOperator.EQUALS,
                expected_value=expected,
            ),
        ),
        corrective_action="Reemitir o atestado sanitário.",
    )


def _snapshot(
    org_id: OrganizationId, subject_id: TypedId, as_of: datetime, result: str
) -> FactSnapshot:
    return FactSnapshot.create(
        organization_id=org_id,
        target_id=subject_id,
        as_of=as_of,
        facts=[
            Fact.create(
                fact_type="sanitary.attestation",
                payload={"result": result},
                observed_at=as_of,
            )
        ],
    )


def _evaluate(policy: Policy, rules: list[Rule], snapshot: FactSnapshot) -> Evaluation:
    service = PolicyEvaluationService(engine=RuleEvaluationEngine())
    return service.evaluate_policy(
        policy=policy, rules=rules, snapshot=snapshot, purpose="CONFORMIDADE_SANITARIA"
    )


def _with_outcome(evaluation: Evaluation, outcome: EvaluationOutcome) -> Evaluation:
    """Troca o outcome de uma Evaluation reproduzível, recomputando o hash junto.

    REVISAO_HUMANA_NECESSARIA não é produzida por `aggregate_outcome()` hoje --
    mesmo padrão usado em `tests/application/test_decision_service.py` para
    exercitar o portão de emissão isoladamente do que hoje produz cada outcome.
    """
    new_hash = compute_evaluation_hash(
        context_hash=evaluation.context_hash,
        subject_id=evaluation.subject_id,
        snapshot_hash=evaluation.fact_snapshot.snapshot_hash,
        rule_results=evaluation.rule_results,
        outcome=outcome,
    )
    return replace(evaluation, outcome=outcome, evaluation_hash=new_hash)


def _pending_review_evaluation() -> Evaluation:
    org_id = OrganizationId.new()
    subject_id = TypedId.new("batch")
    now = datetime.now(UTC)
    policy = _policy(org_id)
    rule = _rule(policy, "rule-atestado", SeverityLevel.BLOCKING)
    evaluation = _evaluate(policy, [rule], _snapshot(org_id, subject_id, now, "reprovado"))
    return _with_outcome(evaluation, EvaluationOutcome.REVISAO_HUMANA_NECESSARIA)


def _human_authority(org_id: OrganizationId, purpose: str) -> DecisionAuthorityProfile:
    return DecisionAuthorityProfile(
        authority_id=TypedId.new("authority_profile"),
        organization_id=org_id,
        principal_reference=UniversalReference(
            target_id=TypedId.new("user"),
            organization_id=org_id,
            contract_version=1,
        ),
        role_name="FISCAL_AUDITOR_SENIOR",
        purpose=purpose,
        emission_method=DecisionEmissionMethod.HUMAN,
        approvals_required=0,
    )


def _reviewer_reference(org_id: OrganizationId) -> UniversalReference:
    return UniversalReference(
        target_id=TypedId.new("user"),
        organization_id=org_id,
        contract_version=1,
    )


def test_create_proposal_derives_result_and_reasons_matching_decide() -> None:
    evaluation = _pending_review_evaluation()
    service = DecisionGovernanceService()

    proposal = service.create_proposal(evaluation=evaluation)

    decision_service = DecisionService()
    assert proposal.proposed_result == decision_service.derive_result(evaluation)
    assert proposal.proposed_reasons == decision_service.build_reasons(evaluation)
    assert proposal.evaluation_id == evaluation.evaluation_id
    assert proposal.evaluation_hash == evaluation.evaluation_hash
    assert proposal.organization_id == evaluation.organization_id


def test_create_proposal_rejects_non_reproducible_evaluation() -> None:
    evaluation = _pending_review_evaluation()
    adulterada = replace(evaluation, evaluation_hash="f" * 64)
    service = DecisionGovernanceService()

    with pytest.raises(ValueError, match="não reproduzível"):
        service.create_proposal(evaluation=adulterada)


def test_record_review_happy_path() -> None:
    evaluation = _pending_review_evaluation()
    service = DecisionGovernanceService()
    proposal = service.create_proposal(evaluation=evaluation)
    authority = _human_authority(evaluation.organization_id, evaluation.purpose)

    review = service.record_review(
        proposal=proposal,
        reviewer_reference=_reviewer_reference(evaluation.organization_id),
        reviewer_authority=authority,
        conclusion=ReviewConclusion.APROVA,
        reasoning="Documentação física conferida em vistoria presencial.",
    )

    assert review.proposal_id == proposal.proposal_id
    assert review.conclusion is ReviewConclusion.APROVA
    assert review.reviewer_authority_id == authority.authority_id


def test_record_review_rejects_authority_from_different_organization() -> None:
    evaluation = _pending_review_evaluation()
    service = DecisionGovernanceService()
    proposal = service.create_proposal(evaluation=evaluation)
    outra_org_authority = _human_authority(OrganizationId.new(), evaluation.purpose)

    with pytest.raises(ValueError, match="mesma Organization"):
        service.record_review(
            proposal=proposal,
            reviewer_reference=_reviewer_reference(evaluation.organization_id),
            reviewer_authority=outra_org_authority,
            conclusion=ReviewConclusion.APROVA,
            reasoning="Análise concluída.",
        )


def test_emit_after_approval_happy_path_produces_human_decision() -> None:
    evaluation = _pending_review_evaluation()
    service = DecisionGovernanceService()
    proposal = service.create_proposal(evaluation=evaluation)
    authority = _human_authority(evaluation.organization_id, evaluation.purpose)
    review = service.record_review(
        proposal=proposal,
        reviewer_reference=_reviewer_reference(evaluation.organization_id),
        reviewer_authority=authority,
        conclusion=ReviewConclusion.APROVA,
        reasoning="Documentação física conferida em vistoria presencial.",
    )

    decision = service.emit_after_approval(
        evaluation=evaluation,
        proposal=proposal,
        review=review,
        authority_profile=authority,
    )

    assert decision.emission_method is DecisionEmissionMethod.HUMAN
    assert decision.result == proposal.proposed_result
    assert decision.evaluation_id == evaluation.evaluation_id
    assert decision.authority_profile_id == authority.authority_id
    assert decision.is_reproducible()


@pytest.mark.parametrize("conclusion", [ReviewConclusion.REJEITA, ReviewConclusion.DEVOLVE])
def test_emit_after_approval_never_emits_for_non_approving_conclusions(
    conclusion: ReviewConclusion,
) -> None:
    evaluation = _pending_review_evaluation()
    service = DecisionGovernanceService()
    proposal = service.create_proposal(evaluation=evaluation)
    authority = _human_authority(evaluation.organization_id, evaluation.purpose)
    review = service.record_review(
        proposal=proposal,
        reviewer_reference=_reviewer_reference(evaluation.organization_id),
        reviewer_authority=authority,
        conclusion=conclusion,
        reasoning="Fundamentação da revisão.",
    )

    with pytest.raises(ValueError, match="não emite Decision"):
        service.emit_after_approval(
            evaluation=evaluation,
            proposal=proposal,
            review=review,
            authority_profile=authority,
        )


def test_emit_after_approval_rejects_review_referencing_wrong_proposal() -> None:
    evaluation = _pending_review_evaluation()
    service = DecisionGovernanceService()
    proposal_a = service.create_proposal(evaluation=evaluation)
    proposal_b = service.create_proposal(evaluation=evaluation)
    authority = _human_authority(evaluation.organization_id, evaluation.purpose)
    review_of_a = service.record_review(
        proposal=proposal_a,
        reviewer_reference=_reviewer_reference(evaluation.organization_id),
        reviewer_authority=authority,
        conclusion=ReviewConclusion.APROVA,
        reasoning="Análise da proposta A.",
    )

    with pytest.raises(ValueError, match="não referencia esta proposta"):
        service.emit_after_approval(
            evaluation=evaluation,
            proposal=proposal_b,
            review=review_of_a,
            authority_profile=authority,
        )


def test_emit_after_approval_rejects_proposal_referencing_wrong_evaluation() -> None:
    evaluation_a = _pending_review_evaluation()
    evaluation_b = _pending_review_evaluation()
    service = DecisionGovernanceService()
    proposal_from_a = service.create_proposal(evaluation=evaluation_a)
    authority = _human_authority(evaluation_a.organization_id, evaluation_a.purpose)
    review = service.record_review(
        proposal=proposal_from_a,
        reviewer_reference=_reviewer_reference(evaluation_a.organization_id),
        reviewer_authority=authority,
        conclusion=ReviewConclusion.APROVA,
        reasoning="Análise concluída.",
    )

    with pytest.raises(ValueError, match="não referencia esta Evaluation"):
        service.emit_after_approval(
            evaluation=evaluation_b,
            proposal=proposal_from_a,
            review=review,
            authority_profile=authority,
        )


def test_emit_after_approval_detects_stale_evaluation_hash() -> None:
    evaluation = _pending_review_evaluation()
    service = DecisionGovernanceService()
    proposal = service.create_proposal(evaluation=evaluation)
    authority = _human_authority(evaluation.organization_id, evaluation.purpose)
    review = service.record_review(
        proposal=proposal,
        reviewer_reference=_reviewer_reference(evaluation.organization_id),
        reviewer_authority=authority,
        conclusion=ReviewConclusion.APROVA,
        reasoning="Análise concluída.",
    )
    evaluation_mudada = replace(evaluation, evaluation_hash="a" * 64)

    with pytest.raises(ValueError, match="mudou desde que a proposta foi criada"):
        service.emit_after_approval(
            evaluation=evaluation_mudada,
            proposal=proposal,
            review=review,
            authority_profile=authority,
        )
