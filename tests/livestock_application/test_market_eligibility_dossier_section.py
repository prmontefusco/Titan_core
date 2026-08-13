"""Corte 1 do NEXT-05: seção pura para uma Decision de mercado por vez."""

from datetime import UTC, datetime

import pytest

from packages.core_application.dossier_service import DossierService
from packages.core_application.verification_service import VerificationBundleService
from packages.core_domain.decision import (
    Decision,
    DecisionReason,
    DecisionReasonCode,
    DecisionResult,
    compute_decision_hash,
)
from packages.core_domain.decision_authority import DecisionEmissionMethod
from packages.core_domain.dossier import Dossier
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
from packages.core_domain.verification import (
    BundleVerifier,
    SignatureMaterial,
    SignaturePurpose,
    SignatureTarget,
    VerificationStatus,
)
from packages.livestock_application.dossier_template import (
    MARKET_ELIGIBILITY_RESULT_BOUNDARY,
    MARKET_TEST_A_CODE,
    MarketEligibilityDossierSectionBuilder,
    MarketEligibilityDossierTemplate,
)
from packages.livestock_application.requirement_authority import RecognitionBoundary
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference

NOW = datetime(2026, 8, 12, tzinfo=UTC)
PURPOSE = "market-test-a"


class _DossierRepository:
    def __init__(self) -> None:
        self.saved: list[Dossier] = []

    def save(self, dossier: Dossier) -> None:
        self.saved.append(dossier)

    def get_by_id(self, dossier_id: TypedId) -> Dossier | None:
        return next((item for item in self.saved if item.dossier_id == dossier_id), None)

    def list_by_subject(
        self, organization_id: OrganizationId, subject_id: TypedId
    ) -> list[Dossier]:
        return [
            item
            for item in self.saved
            if item.organization_id == organization_id
            and item.subject_reference.target_id == subject_id
        ]


def _artifacts(
    *,
    market_code: str = "MARKET_TEST_A",
    purpose: str = PURPOSE,
    policy_version: int = 1,
    valid_from: datetime = NOW,
    valid_to: datetime | None = None,
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
        version=policy_version,
        status=PolicyStatus.PUBLISHED,
        valid_from=valid_from,
        valid_to=valid_to,
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


def test_satisfied_synthetic_policy_does_not_assert_external_recognition() -> None:
    decision, evaluation, policy = _artifacts()

    section = MarketEligibilityDossierSectionBuilder(
        market_code="MARKET_TEST_A", purpose=PURPOSE
    ).build(decision=decision, evaluation=evaluation, policy=policy)

    assert decision.result is DecisionResult.APROVADA
    market = section.content["market_eligibility"]
    assert market["market_profile"]["synthetic"] is True
    assert market["authority_boundary"]["recognition_boundary"] == "INTERNAL_ONLY"
    assert market["result_boundary"] == MARKET_ELIGIBILITY_RESULT_BOUNDARY


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


def test_market_test_a_dossier_uses_existing_persistence_path() -> None:
    decision, evaluation, policy = _artifacts(market_code=MARKET_TEST_A_CODE)
    repository = _DossierRepository()
    template = MarketEligibilityDossierTemplate(
        section_builder=MarketEligibilityDossierSectionBuilder(
            market_code=MARKET_TEST_A_CODE,
            purpose=PURPOSE,
        ),
        dossier_service=DossierService(repository=repository),
    )

    dossier = template.build_and_store(
        decision=decision,
        evaluation=evaluation,
        policy=policy,
        generated_at=NOW,
    )

    assert repository.saved == [dossier]
    assert dossier.verify()
    assert (
        dossier.document["vertical"]["content"]["market_eligibility"]["market_profile"]["code"]
        == MARKET_TEST_A_CODE
    )


def test_later_policy_version_does_not_change_the_prior_dossier() -> None:
    organization_id = OrganizationId.new()
    animal_id = TypedId.new("animal")
    repository = _DossierRepository()
    template = MarketEligibilityDossierTemplate(
        section_builder=MarketEligibilityDossierSectionBuilder(
            market_code=MARKET_TEST_A_CODE,
            purpose=PURPOSE,
        ),
        dossier_service=DossierService(repository=repository),
    )
    decision_v1, evaluation_v1, policy_v1 = _artifacts(
        market_code=MARKET_TEST_A_CODE,
        organization_id=organization_id,
        animal_id=animal_id,
        policy_version=1,
        valid_from=datetime(2026, 1, 1, tzinfo=UTC),
        valid_to=datetime(2026, 7, 1, tzinfo=UTC),
    )
    dossier_v1 = template.build_and_store(
        decision=decision_v1,
        evaluation=evaluation_v1,
        policy=policy_v1,
        generated_at=NOW,
    )
    preserved_hash = dossier_v1.dossier_hash
    preserved_document = dossier_v1.document

    decision_v2, evaluation_v2, policy_v2 = _artifacts(
        market_code=MARKET_TEST_A_CODE,
        organization_id=organization_id,
        animal_id=animal_id,
        policy_version=2,
        valid_from=datetime(2026, 7, 1, tzinfo=UTC),
    )
    dossier_v2 = template.build_and_store(
        decision=decision_v2,
        evaluation=evaluation_v2,
        policy=policy_v2,
        generated_at=datetime(2026, 8, 1, tzinfo=UTC),
    )

    assert dossier_v1.dossier_hash == preserved_hash
    assert dossier_v1.document == preserved_document
    assert dossier_v1.document["policy"]["version"] == 1
    assert dossier_v2.document["policy"]["version"] == 2
    assert dossier_v1.dossier_hash != dossier_v2.dossier_hash


def test_second_cut_refuses_another_market_profile() -> None:
    with pytest.raises(ValueError, match="somente o perfil sintético MARKET_TEST_A"):
        MarketEligibilityDossierTemplate(
            section_builder=MarketEligibilityDossierSectionBuilder(
                market_code="MARKET_TEST_B",
                purpose="market-test-b",
            ),
            dossier_service=DossierService(repository=_DossierRepository()),
        )


def test_market_test_a_dossier_is_verifiable_in_the_existing_bundle() -> None:
    decision, evaluation, policy = _artifacts(market_code=MARKET_TEST_A_CODE)
    dossier = MarketEligibilityDossierTemplate(
        section_builder=MarketEligibilityDossierSectionBuilder(
            market_code=MARKET_TEST_A_CODE,
            purpose=PURPOSE,
        ),
        dossier_service=DossierService(repository=_DossierRepository()),
    ).build_and_store(
        decision=decision,
        evaluation=evaluation,
        policy=policy,
        generated_at=NOW,
    )
    bundle_service = VerificationBundleService()
    bundle = bundle_service.build_from_dossier(
        dossier=dossier,
        audience="auditoria-interna",
        created_at=NOW,
        signature=SignatureMaterial(
            key_id="market-test-key",
            algorithm="sha256",
            profile="INTERNAL_TEST_SIGNATURE",
            signature_target=SignatureTarget(
                target_type="bundle_manifest",
                target_identifier="pending",
                domain="titan.verification_bundle",
                contract_version=1,
                purpose=SignaturePurpose.EMISSAO,
            ),
            signature_value="market-test-signature",
            signed_at=NOW,
            certificate_chain=("market-test-certificate",),
            revocation_material=("market-test-crl",),
        ),
        verification_policy={"profile": "INTERNAL_TEST_SIGNATURE"},
        profiles=("INTERNAL_TEST_SIGNATURE",),
    )

    received = VerificationBundleService.load(bundle_service.export(bundle))
    report = BundleVerifier().verify(
        received,
        verified_at=NOW,
        trust_anchors={"market-test-key": "market-test-signature"},
    )

    assert report.status is VerificationStatus.VALIDA
    assert received.manifest.purpose == PURPOSE
    assert b"MARKET_TEST_A" in received.payloads["dossier.json"]
    assert b"MARKET_TEST_B" not in received.payloads["dossier.json"]
