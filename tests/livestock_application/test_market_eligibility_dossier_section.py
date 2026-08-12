"""Corte 1 do NEXT-05: seção pura para uma Decision de mercado por vez."""

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
from packages.core_domain.evaluation import (
    Evaluation,
    EvaluationOutcome,
    RuleResult,
    RuleResultStatus,
    compute_context_hash,
    compute_evaluation_hash,
)
from packages.core_domain.facts import Fact, FactSnapshot
from packages.core_domain.normative import (
    NormativeBasisSnapshot,
    NormativeReferenceSnapshot,
    NormativeSourceClassification,
)
from packages.core_domain.policy import Policy, PolicyStatus
from packages.core_domain.rule import SeverityLevel
from packages.livestock_application.dossier_template import (
    MARKET_ELIGIBILITY_RESULT_BOUNDARY,
    MarketEligibilityDossierSectionBuilder,
)
from packages.livestock_application.requirement_authority import RecognitionBoundary
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference

NOW = datetime(2026, 8, 12, tzinfo=UTC)
PURPOSE = "market-test-a"


def _artifacts(
    *,
    market_code: str = "MARKET_TEST_A",
    purpose: str = PURPOSE,
    classification_status: str = "COMPLETE",
    organization_id: OrganizationId | None = None,
    animal_id: TypedId | None = None,
) -> tuple[Decision, Evaluation, Policy]:
    organization_id = organization_id or OrganizationId.new()
    animal_id = animal_id or TypedId.new("animal")
    policy = Policy(
        policy_id=TypedId.new("policy"),
        organization_id=organization_id,
        code=market_code,
        name="Policy de teste",
        description="Somente para teste.",
        version=1,
        status=PolicyStatus.PUBLISHED,
        valid_from=NOW,
        published_at=NOW,
    )
    coverage = Fact.create(
        fact_type="livestock.coverage.treatment_history",
        payload={
            "dimension": "treatment_history",
            "coverage_status": "COMPLETE",
            "required_from": "2026-05-14T00:00:00+00:00",
            "required_until": NOW.isoformat(),
            "medication_classification_coverage_status": classification_status,
        },
        observed_at=NOW,
    )
    snapshot = FactSnapshot.create(
        organization_id=organization_id,
        target_id=animal_id,
        as_of=NOW,
        facts=(coverage,),
        reference_time=NOW,
        knowledge_cutoff=NOW,
    )
    rule_id = TypedId.new("rule")
    rule_versions = (("authority-test-a-sanitary-attestation", 1),)
    normative = NormativeBasisSnapshot(
        schema_version=1,
        normative_basis_id=TypedId.new("normative_basis"),
        normative_basis_code=f"{market_code}-BASIS",
        normative_basis_version=1,
        policy_id=policy.policy_id,
        policy_code=policy.code,
        policy_version=policy.version,
        rule_versions=rule_versions,
        purpose=purpose,
        jurisdiction="TEST-JURISDICTION",
        intended_use="INTERNAL_TEST_ONLY",
        reference_time=NOW,
        knowledge_cutoff=NOW,
        approved_by="actor:test-reviewer",
        approval_authority="INTERNAL_TEST_AUTHORITY",
        approved_at=NOW,
        references=(
            NormativeReferenceSnapshot(
                instrument_code="MARKET-TEST-INSTRUMENT",
                instrument_version="1",
                provision="section-1",
                content_digest="a" * 64,
                digest_algorithm="sha256",
                source_classification=NormativeSourceClassification.INTERNAL_TEST,
            ),
        ),
        limitations=("RECOGNITION_BOUNDARY:INTERNAL_ONLY",),
    )
    context_hash = compute_context_hash(
        policy_id=policy.policy_id,
        policy_version=policy.version,
        purpose=purpose,
        engine_version=1,
        rule_versions=rule_versions,
        normative_basis_snapshot_digest=normative.snapshot_digest,
    )
    result = RuleResult(
        result_id=TypedId.new("rule_result"),
        rule_id=rule_id,
        rule_version=1,
        organization_id=organization_id,
        subject_id=animal_id,
        status=RuleResultStatus.ATENDIDA,
        severity=SeverityLevel.BLOCKING,
        reason="Requisito sintético atendido.",
        corrective_action="Nenhuma ação necessária.",
        missing_evidence_types=(),
        evaluated_at=NOW,
        snapshot_hash=snapshot.snapshot_hash,
        inputs_hash="b" * 64,
        rule_code=rule_versions[0][0],
    )
    evaluation_hash = compute_evaluation_hash(
        context_hash=context_hash,
        subject_id=animal_id,
        snapshot_hash=snapshot.snapshot_hash,
        rule_results=(result,),
        outcome=EvaluationOutcome.CONDICOES_SATISFEITAS,
    )
    evaluation = Evaluation(
        evaluation_id=TypedId.new("evaluation"),
        organization_id=organization_id,
        subject_id=animal_id,
        purpose=purpose,
        policy_id=policy.policy_id,
        policy_version=policy.version,
        fact_snapshot=snapshot,
        rule_results=(result,),
        outcome=EvaluationOutcome.CONDICOES_SATISFEITAS,
        evaluated_at=NOW,
        engine_version=1,
        evaluation_hash=evaluation_hash,
        context_hash=context_hash,
        normative_basis_snapshot=normative,
        rule_versions=rule_versions,
    )
    reason = DecisionReason(
        code=DecisionReasonCode.REGRA_ATENDIDA,
        message="A Policy sintética foi satisfeita.",
        rule_code=result.rule_code,
        rule_id=rule_id,
        rule_version=1,
    )
    authority_profile_id = TypedId.new("authority_profile")
    decision = Decision(
        decision_id=TypedId.new("decision"),
        organization_id=organization_id,
        subject_id=animal_id,
        purpose=purpose,
        evaluation_id=evaluation.evaluation_id,
        evaluation_hash=evaluation.evaluation_hash,
        policy_id=policy.policy_id,
        policy_version=policy.version,
        result=DecisionResult.APROVADA,
        reasons=(reason,),
        snapshot_hash=snapshot.snapshot_hash,
        issued_at=NOW,
        engine_version=1,
        decision_hash=compute_decision_hash(
            evaluation_hash=evaluation_hash,
            subject_id=animal_id,
            purpose=purpose,
            result=DecisionResult.APROVADA,
            reasons=(reason,),
            authority_profile_id=authority_profile_id,
            emission_method=DecisionEmissionMethod.AUTOMATED,
        ),
        authority_profile_id=authority_profile_id,
        authority_reference=UniversalReference(TypedId.new("service_identity"), organization_id, 1),
        emission_method=DecisionEmissionMethod.AUTOMATED,
    )
    return decision, evaluation, policy


def test_section_declares_real_dimensional_coverage_and_result_boundary() -> None:
    decision, evaluation, policy = _artifacts()

    section = MarketEligibilityDossierSectionBuilder(
        market_code="MARKET_TEST_A", purpose=PURPOSE
    ).build(decision=decision, evaluation=evaluation, policy=policy)

    market = section.content["market_eligibility"]
    assert market["market_profile"] == {
        "code": "MARKET_TEST_A",
        "profile": "STANDARD",
        "synthetic": True,
    }
    assert market["coverage"]["dimensions"] == [
        {
            "code": "treatment_history",
            "status": "COMPLETE",
            "interval": {"from": "2026-05-14T00:00:00+00:00", "to": NOW.isoformat()},
        },
        {
            "code": "medication_classification",
            "status": "COMPLETE",
            "interval": {"from": "2026-05-14T00:00:00+00:00", "to": NOW.isoformat()},
        },
    ]
    assert market["result_boundary"] == MARKET_ELIGIBILITY_RESULT_BOUNDARY
    assert market["authority_boundary"] == {
        "recognition_boundary": "INTERNAL_ONLY",
        "statement": "Titan assessment; external recognition is not asserted.",
    }
    assert market["limitations"] == []


def test_incomplete_coverage_remains_a_gap_in_its_existing_dimension() -> None:
    decision, evaluation, policy = _artifacts(classification_status="INCOMPLETE")

    section = MarketEligibilityDossierSectionBuilder(
        market_code="MARKET_TEST_A", purpose=PURPOSE
    ).build(decision=decision, evaluation=evaluation, policy=policy)

    dimensions = section.content["market_eligibility"]["coverage"]["dimensions"]
    assert dimensions[1]["status"] == "INCOMPLETE"
    assert section.content["market_eligibility"]["limitations"] == []


def test_same_animal_under_two_policies_builds_isolated_sections() -> None:
    organization_id = OrganizationId.new()
    animal_id = TypedId.new("animal")
    decision_a, evaluation_a, policy_a = _artifacts(
        organization_id=organization_id, animal_id=animal_id
    )
    decision_b, evaluation_b, policy_b = _artifacts(
        market_code="MARKET_TEST_B",
        purpose="market-test-b",
        organization_id=organization_id,
        animal_id=animal_id,
    )

    section_a = MarketEligibilityDossierSectionBuilder(
        market_code="MARKET_TEST_A", purpose=PURPOSE
    ).build(decision=decision_a, evaluation=evaluation_a, policy=policy_a)
    section_b = MarketEligibilityDossierSectionBuilder(
        market_code="MARKET_TEST_B", purpose="market-test-b"
    ).build(decision=decision_b, evaluation=evaluation_b, policy=policy_b)

    assert "MARKET_TEST_B" not in str(section_a.content)
    assert "MARKET_TEST_A" not in str(section_b.content)


def test_section_refuses_policy_from_another_market() -> None:
    decision, evaluation, policy = _artifacts()

    with pytest.raises(ValueError, match="código do perfil de mercado"):
        MarketEligibilityDossierSectionBuilder(market_code="MARKET_TEST_B", purpose=PURPOSE).build(
            decision=decision, evaluation=evaluation, policy=policy
        )


def test_only_internal_boundary_is_accepted_by_the_first_cut_builder() -> None:
    decision, evaluation, policy = _artifacts()

    section = MarketEligibilityDossierSectionBuilder(
        market_code="MARKET_TEST_A",
        purpose=PURPOSE,
        recognition_boundary=RecognitionBoundary.INTERNAL_ONLY,
    ).build(decision=decision, evaluation=evaluation, policy=policy)

    assert (
        section.content["market_eligibility"]["authority_boundary"]["recognition_boundary"]
        == "INTERNAL_ONLY"
    )


def test_external_recognition_boundary_is_not_supported_in_the_first_cut() -> None:
    with pytest.raises(ValueError, match="somente a boundary INTERNAL_ONLY"):
        MarketEligibilityDossierSectionBuilder(
            market_code="MARKET_TEST_A",
            purpose=PURPOSE,
            recognition_boundary=RecognitionBoundary.EXTERNAL_RECOGNITION_NOT_DEMONSTRATED,
        )
