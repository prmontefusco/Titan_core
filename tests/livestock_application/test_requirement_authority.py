"""Corte 1 do NEXT-03: competência de Source por requisito fictício."""

from datetime import UTC, datetime, timedelta

from packages.livestock_application.requirement_authority import (
    AUTHORITY_TEST_A_CAPABILITY,
    AUTHORITY_TEST_A_POLICY_CODE,
    AUTHORITY_TEST_A_PURPOSE,
    AUTHORITY_TEST_A_REQUIREMENT,
    RecognitionBoundary,
    RequirementAuthorityAssessment,
    RequirementAuthorityAssessmentService,
    RequirementAuthorityOutcome,
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


def _assess(
    assertions: tuple[SourceCompetenceAssertion, ...],
    reference_time: datetime,
) -> RequirementAuthorityAssessment:
    organization_id = OrganizationId.new()
    if assertions:
        asserted_organization_id = assertions[0].source_reference.organization_id
        assert asserted_organization_id is not None
        organization_id = asserted_organization_id
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


def test_documented_validated_and_admissible_source_is_satisfied_internally() -> None:
    reference_time = datetime(2026, 8, 12, tzinfo=UTC)
    result = _assess((_assertion(OrganizationId.new(), reference_time),), reference_time)

    assert result.outcome is RequirementAuthorityOutcome.SATISFIED
    assert result.recognition_boundary is RecognitionBoundary.INTERNAL_ONLY
    assert result.limitations == ()


def test_evidence_without_source_competence_is_indeterminate() -> None:
    reference_time = datetime(2026, 8, 12, tzinfo=UTC)
    result = _assess((), reference_time)

    assert result.outcome is RequirementAuthorityOutcome.INDETERMINATE
    assert result.limitations == ("SOURCE_COMPETENCE_NOT_DEMONSTRATED",)


def test_external_claim_without_recognition_is_indeterminate_not_externally_recognized() -> None:
    reference_time = datetime(2026, 8, 12, tzinfo=UTC)
    assertion = _assertion(
        OrganizationId.new(),
        reference_time,
        recognition_boundary=RecognitionBoundary.EXTERNAL_RECOGNITION_NOT_DEMONSTRATED,
    )

    result = _assess((assertion,), reference_time)

    assert result.outcome is RequirementAuthorityOutcome.INDETERMINATE
    assert result.recognition_boundary is RecognitionBoundary.EXTERNAL_RECOGNITION_NOT_DEMONSTRATED
    assert "EXTERNAL_RECOGNITION_NOT_DEMONSTRATED" in result.limitations


def test_competence_known_after_cutoff_is_not_used_retroactively() -> None:
    reference_time = datetime(2026, 8, 12, tzinfo=UTC)
    assertion = _assertion(
        OrganizationId.new(),
        reference_time,
        known_at=reference_time + timedelta(days=1),
    )

    result = _assess((assertion,), reference_time)

    assert result.outcome is RequirementAuthorityOutcome.INDETERMINATE
    assert result.source_reference is None


def test_explicitly_not_competent_is_not_satisfied() -> None:
    reference_time = datetime(2026, 8, 12, tzinfo=UTC)
    assertion = _assertion(
        OrganizationId.new(), reference_time, status=SourceCompetenceStatus.NOT_COMPETENT
    )

    result = _assess((assertion,), reference_time)

    assert result.outcome is RequirementAuthorityOutcome.NOT_SATISFIED
    assert result.limitations == ("SOURCE_EXPLICITLY_NOT_COMPETENT",)


def test_unknown_or_conflicting_competence_is_indeterminate() -> None:
    reference_time = datetime(2026, 8, 12, tzinfo=UTC)
    organization_id = OrganizationId.new()
    competent = _assertion(organization_id, reference_time)
    unknown = _assertion(organization_id, reference_time, status=SourceCompetenceStatus.UNKNOWN)

    result = _assess((competent, unknown), reference_time)

    assert result.outcome is RequirementAuthorityOutcome.INDETERMINATE
    assert result.limitations == ("SOURCE_COMPETENCE_AMBIGUOUS_OR_UNKNOWN",)


def test_competent_and_explicitly_not_competent_sources_are_ambiguous() -> None:
    reference_time = datetime(2026, 8, 12, tzinfo=UTC)
    organization_id = OrganizationId.new()
    competent = _assertion(organization_id, reference_time)
    not_competent = _assertion(
        organization_id, reference_time, status=SourceCompetenceStatus.NOT_COMPETENT
    )

    result = _assess((competent, not_competent), reference_time)

    assert result.outcome is RequirementAuthorityOutcome.INDETERMINATE
    assert result.limitations == ("SOURCE_COMPETENCE_AMBIGUOUS_OR_UNKNOWN",)


def test_source_without_admissible_evidence_is_indeterminate() -> None:
    reference_time = datetime(2026, 8, 12, tzinfo=UTC)
    assertion = _assertion(
        OrganizationId.new(),
        reference_time,
        admissibility=RequirementEvidenceAdmissibility.NOT_ADMISSIBLE,
    )

    result = _assess((assertion,), reference_time)

    assert result.outcome is RequirementAuthorityOutcome.INDETERMINATE
    assert result.limitations == ("SOURCE_COMPETENCE_NOT_ADMISSIBLE",)


def test_validity_interval_is_semi_open_at_its_end() -> None:
    reference_time = datetime(2026, 8, 12, tzinfo=UTC)
    assertion = _assertion(OrganizationId.new(), reference_time, valid_until=reference_time)

    result = _assess((assertion,), reference_time)

    assert result.outcome is RequirementAuthorityOutcome.INDETERMINATE
