"""Corte 2 do NEXT-03: Policy sintética consume suficiência de autoridade."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

from packages.core_application.evaluation_service import RuleEvaluationEngine
from packages.core_domain.evaluation import RuleResultStatus
from packages.core_domain.facts import FactSnapshot
from packages.core_domain.normative import (
    NormativeBasisSnapshot,
    NormativeReferenceSnapshot,
    NormativeSourceClassification,
)
from packages.livestock_application.requirement_authority import (
    AUTHORITY_TEST_A_CAPABILITY,
    AUTHORITY_TEST_A_POLICY_CODE,
    AUTHORITY_TEST_A_PURPOSE,
    AUTHORITY_TEST_A_REQUIREMENT,
    AuthorityTestARequirementService,
    RecognitionBoundary,
    RequirementAuthorityAssessment,
    RequirementAuthorityAssessmentService,
    RequirementAuthorityValidation,
    RequirementEvidenceAdmissibility,
    SourceCompetenceAssertion,
    SourceCompetenceStatus,
)
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference


def _reference(entity_type: str, organization_id: OrganizationId) -> UniversalReference:
    return UniversalReference(TypedId.new(entity_type), organization_id, 1)


def _assertion(
    organization_id: OrganizationId,
    reference_time: datetime,
    **changes: object,
) -> SourceCompetenceAssertion:
    values: dict[str, object] = {
        "source_reference": _reference("source", organization_id),
        "requirement_code": AUTHORITY_TEST_A_REQUIREMENT,
        "purpose": AUTHORITY_TEST_A_PURPOSE,
        "capability_code": AUTHORITY_TEST_A_CAPABILITY,
        "status": SourceCompetenceStatus.COMPETENT,
        "valid_from": reference_time - timedelta(days=1),
        "valid_until": reference_time + timedelta(days=1),
        "known_at": reference_time,
        "authority_basis_references": (_reference("document", organization_id),),
        "evidence_references": (_reference("evidence", organization_id),),
        "validation": RequirementAuthorityValidation.VALIDATED,
        "admissibility": RequirementEvidenceAdmissibility.ADMISSIBLE,
        "recognition_boundary": RecognitionBoundary.INTERNAL_ONLY,
    }
    values.update(changes)
    return SourceCompetenceAssertion(**values)  # type: ignore[arg-type]


def _assessment(
    organization_id: OrganizationId,
    reference_time: datetime,
    assertions: tuple[SourceCompetenceAssertion, ...],
) -> RequirementAuthorityAssessment:
    return RequirementAuthorityAssessmentService().assess(
        subject_reference=_reference("animal", organization_id),
        policy_code=AUTHORITY_TEST_A_POLICY_CODE,
        requirement_code=AUTHORITY_TEST_A_REQUIREMENT,
        purpose=AUTHORITY_TEST_A_PURPOSE,
        required_capability=AUTHORITY_TEST_A_CAPABILITY,
        reference_time=reference_time,
        knowledge_cutoff=reference_time,
        assertions=assertions,
    )


def _evaluate(
    assessment: RequirementAuthorityAssessment,
    organization_id: OrganizationId,
) -> RuleResultStatus:
    service = AuthorityTestARequirementService()
    fact = service.build_fact(assessment)
    snapshot = FactSnapshot.create(
        organization_id=organization_id,
        target_id=assessment.subject_reference.target_id,
        as_of=assessment.reference_time,
        facts=(fact,),
    )
    rule = service.build_rule(TypedId.new("policy"), organization_id)
    return RuleEvaluationEngine().evaluate(rule, snapshot).status


def test_admissible_competence_satisfies_the_controlled_policy() -> None:
    organization_id = OrganizationId.new()
    reference_time = datetime(2026, 8, 12, tzinfo=UTC)
    assessment = _assessment(
        organization_id,
        reference_time,
        (_assertion(organization_id, reference_time),),
    )

    assert _evaluate(assessment, organization_id) is RuleResultStatus.ATENDIDA


def test_indeterminate_authority_cannot_produce_positive_policy_result() -> None:
    organization_id = OrganizationId.new()
    reference_time = datetime(2026, 8, 12, tzinfo=UTC)
    assessment = _assessment(organization_id, reference_time, ())

    assert _evaluate(assessment, organization_id) is RuleResultStatus.INDETERMINADA


def test_explicit_incompetence_is_not_satisfied_by_the_controlled_policy() -> None:
    organization_id = OrganizationId.new()
    reference_time = datetime(2026, 8, 12, tzinfo=UTC)
    assessment = _assessment(
        organization_id,
        reference_time,
        (
            _assertion(
                organization_id,
                reference_time,
                status=SourceCompetenceStatus.NOT_COMPETENT,
            ),
        ),
    )

    assert _evaluate(assessment, organization_id) is RuleResultStatus.NAO_ATENDIDA


def test_recognition_boundary_is_preservable_in_normative_snapshot_identity() -> None:
    organization_id = OrganizationId.new()
    reference_time = datetime(2026, 8, 12, tzinfo=UTC)
    assessment = _assessment(
        organization_id,
        reference_time,
        (
            _assertion(
                organization_id,
                reference_time,
                recognition_boundary=RecognitionBoundary.EXTERNAL_RECOGNITION_NOT_DEMONSTRATED,
            ),
        ),
    )
    service = AuthorityTestARequirementService()
    base = NormativeBasisSnapshot(
        schema_version=1,
        normative_basis_id=TypedId.new("normative_basis"),
        normative_basis_code="AUTHORITY-TEST-BASIS-A",
        normative_basis_version=1,
        policy_id=TypedId.new("policy"),
        policy_code=AUTHORITY_TEST_A_POLICY_CODE,
        policy_version=1,
        rule_versions=(("authority-test-a-sanitary-attestation", 1),),
        purpose=AUTHORITY_TEST_A_PURPOSE,
        jurisdiction="TEST-JURISDICTION",
        intended_use="INTERNAL_TEST_ONLY",
        reference_time=reference_time,
        knowledge_cutoff=reference_time,
        approved_by="actor:test-reviewer",
        approval_authority="INTERNAL_TEST_AUTHORITY",
        approved_at=reference_time,
        references=(
            NormativeReferenceSnapshot(
                instrument_code="AUTHORITY-TEST-INSTRUMENT-A",
                instrument_version="1",
                provision="section-1",
                content_digest="a" * 64,
                digest_algorithm="sha256",
                source_classification=NormativeSourceClassification.INTERNAL_TEST,
            ),
        ),
    )
    with_boundary = replace(
        base,
        limitations=service.normative_snapshot_limitations(assessment),
        snapshot_digest="",
    )

    assert "RECOGNITION_BOUNDARY:EXTERNAL_RECOGNITION_NOT_DEMONSTRATED" in with_boundary.limitations
    assert with_boundary.snapshot_digest != base.snapshot_digest
