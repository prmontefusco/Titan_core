"""F1: Commercial Passport application contracts only."""

from datetime import UTC, datetime, timedelta

import pytest

from packages.livestock_application.commercial_passport import (
    CommercialOpportunity,
    CommercialOpportunityKind,
    CommercialPassport,
    CommercialPassportContext,
    CommercialPassportOpportunityAssessment,
    CommercialPassportRequirementDimension,
    CommercialPassportRequirementStatus,
    CommercialReadinessBreakdown,
    CommercialReadinessInterpretation,
    CommercialRequirementAssessment,
    PopulationEligibilitySummary,
    PropertyCommercialPassportOpportunityInput,
    PropertyCommercialPassportService,
    PropertyCommercialReadiness,
)
from packages.shared_kernel import OrganizationId, TypedId

NOW = datetime(2026, 9, 11, tzinfo=UTC)


def _context() -> CommercialPassportContext:
    return CommercialPassportContext(
        organization_id=OrganizationId.new(),
        property_id=TypedId.new("rural_property"),
        reference_time=NOW,
        knowledge_cutoff=NOW,
        evaluated_at=NOW,
    )


def _opportunity(code: str = "synthetic-eu") -> CommercialOpportunity:
    return CommercialOpportunity(
        code=code,
        kind=CommercialOpportunityKind.MARKET,
        name="Synthetic EU",
        purpose="exportacao-uniao-europeia",
        policy_id=TypedId.new("policy"),
        policy_version=1,
    )


def _requirement(
    code: str,
    status: CommercialPassportRequirementStatus,
    dimension: CommercialPassportRequirementDimension = (
        CommercialPassportRequirementDimension.PROPERTY_READINESS
    ),
) -> CommercialRequirementAssessment:
    return CommercialRequirementAssessment(
        requirement_code=code,
        label=f"Requirement {code}",
        dimension=dimension,
        status=status,
        reason=f"Reason for {code}",
    )


def test_context_preserves_temporal_coordinates_without_current_state_shortcut() -> None:
    context = _context()

    assert context.reference_time == NOW
    assert context.knowledge_cutoff == NOW
    assert context.evaluated_at == NOW

    with pytest.raises(ValueError, match="knowledge_cutoff"):
        CommercialPassportContext(
            organization_id=OrganizationId.new(),
            property_id=TypedId.new("rural_property"),
            reference_time=NOW,
            knowledge_cutoff=NOW - timedelta(days=1),
            evaluated_at=NOW,
        )


def test_property_readiness_counts_are_derived_and_not_single_score() -> None:
    readiness = PropertyCommercialReadiness(
        requirements=(
            _requirement("traceability", CommercialPassportRequirementStatus.SATISFIED),
            _requirement("document", CommercialPassportRequirementStatus.MISSING),
            _requirement("feed", CommercialPassportRequirementStatus.UNKNOWN),
            _requirement("reconciliation", CommercialPassportRequirementStatus.FAILED),
            _requirement("private-protocol", CommercialPassportRequirementStatus.NOT_APPLICABLE),
            _requirement("withdrawal", CommercialPassportRequirementStatus.BLOCKED),
        ),
    )

    assert readiness.breakdown == CommercialReadinessBreakdown(
        satisfied=1,
        missing=1,
        unknown=1,
        failed=1,
        not_applicable=1,
        blocked=1,
    )
    assert readiness.breakdown.applicable_count == 5
    assert readiness.breakdown.total_count == 6
    assert readiness.breakdown.derived_ratio == 1 / 5
    assert readiness.breakdown.has_blocker is True
    assert readiness.breakdown.interpretation is (
        CommercialReadinessInterpretation.UNAVAILABLE_BLOCKED
    )


def test_not_applicable_stays_out_of_readiness_denominator() -> None:
    readiness = PropertyCommercialReadiness(
        requirements=(
            _requirement("satisfied", CommercialPassportRequirementStatus.SATISFIED),
            _requirement("not-applicable", CommercialPassportRequirementStatus.NOT_APPLICABLE),
        ),
    )

    assert readiness.breakdown.applicable_count == 1
    assert readiness.breakdown.derived_ratio == 1.0


def test_requirement_status_semantics_preserve_distinctions() -> None:
    missing = CommercialPassportRequirementStatus.MISSING
    unknown = CommercialPassportRequirementStatus.UNKNOWN
    failed = CommercialPassportRequirementStatus.FAILED
    blocked = CommercialPassportRequirementStatus.BLOCKED
    not_applicable = CommercialPassportRequirementStatus.NOT_APPLICABLE

    assert missing.is_missing_evidence is True
    assert missing.is_unknown is False
    assert unknown.is_unknown is True
    assert unknown.is_missing_evidence is False
    assert failed.is_failed is True
    assert failed.is_missing_evidence is False
    assert blocked.blocks_opportunity is True
    assert blocked.is_failed is False
    assert not_applicable.applies_to_readiness_denominator is False
    assert "not false" in unknown.semantic_description


def test_readiness_interpretation_is_derived_with_blocker_precedence() -> None:
    blocked = PropertyCommercialReadiness(
        requirements=(
            _requirement("satisfied", CommercialPassportRequirementStatus.SATISFIED),
            _requirement("blocker", CommercialPassportRequirementStatus.BLOCKED),
        ),
    )
    failed = PropertyCommercialReadiness(
        requirements=(
            _requirement("satisfied", CommercialPassportRequirementStatus.SATISFIED),
            _requirement("failed", CommercialPassportRequirementStatus.FAILED),
        ),
    )
    unknown = PropertyCommercialReadiness(
        requirements=(
            _requirement("satisfied", CommercialPassportRequirementStatus.SATISFIED),
            _requirement("unknown", CommercialPassportRequirementStatus.UNKNOWN),
        ),
    )
    missing = PropertyCommercialReadiness(
        requirements=(
            _requirement("satisfied", CommercialPassportRequirementStatus.SATISFIED),
            _requirement("missing", CommercialPassportRequirementStatus.MISSING),
        ),
    )
    available = PropertyCommercialReadiness(
        requirements=(_requirement("satisfied", CommercialPassportRequirementStatus.SATISFIED),),
    )
    not_assessed = PropertyCommercialReadiness(
        requirements=(
            _requirement("not-applicable", CommercialPassportRequirementStatus.NOT_APPLICABLE),
        ),
    )

    assert blocked.breakdown.derived_ratio == 0.5
    assert blocked.breakdown.interpretation is (
        CommercialReadinessInterpretation.UNAVAILABLE_BLOCKED
    )
    assert failed.breakdown.interpretation is (CommercialReadinessInterpretation.UNAVAILABLE_FAILED)
    assert unknown.breakdown.interpretation is CommercialReadinessInterpretation.UNKNOWN
    assert missing.breakdown.interpretation is CommercialReadinessInterpretation.PARTIALLY_READY
    assert available.breakdown.interpretation is CommercialReadinessInterpretation.AVAILABLE
    assert not_assessed.breakdown.interpretation is CommercialReadinessInterpretation.NOT_ASSESSED


def test_property_readiness_refuses_population_dimension() -> None:
    with pytest.raises(ValueError, match="propriedade"):
        PropertyCommercialReadiness(
            requirements=(
                _requirement(
                    "animal-readiness",
                    CommercialPassportRequirementStatus.SATISFIED,
                    CommercialPassportRequirementDimension.POPULATION_ELIGIBILITY,
                ),
            ),
        )


def test_population_eligibility_is_separate_from_property_readiness() -> None:
    property_readiness = PropertyCommercialReadiness(
        requirements=(
            _requirement("property-document", CommercialPassportRequirementStatus.SATISFIED),
        ),
    )
    population = PopulationEligibilitySummary(
        subject_type="animal",
        counts_by_status={
            "READY": 742,
            "INDETERMINATE": 103,
            "NOT_READY": 377,
            "BLOCKED": 28,
        },
        limitations=("derived from MarketReadiness; not a Decision",),
    )
    assessment = CommercialPassportOpportunityAssessment(
        opportunity=_opportunity(),
        property_readiness=property_readiness,
        population_eligibility=population,
    )

    assert assessment.property_readiness.breakdown.satisfied == 1
    assert assessment.population_eligibility is not None
    assert assessment.population_eligibility.total_count == 1250


def test_dynamic_passport_is_projection_not_issued_snapshot() -> None:
    passport = CommercialPassport(
        context=_context(),
        opportunities=(
            CommercialPassportOpportunityAssessment(
                opportunity=_opportunity(),
                property_readiness=PropertyCommercialReadiness(
                    requirements=(
                        _requirement(
                            "property-document",
                            CommercialPassportRequirementStatus.SATISFIED,
                        ),
                    ),
                ),
            ),
        ),
    )

    assert "COMMERCIAL_PASSPORT_IS_NOT_DECISION" in passport.limitations
    assert "COMMERCIAL_PASSPORT_IS_NOT_MARKET_ELIGIBILITY" in passport.limitations
    assert "FORMAL_DISCLOSURE_REQUIRES_ISSUED_SNAPSHOT" in passport.limitations


def test_passport_rejects_duplicate_opportunities() -> None:
    opportunity = _opportunity()
    readiness = PropertyCommercialReadiness(
        requirements=(
            _requirement("property-document", CommercialPassportRequirementStatus.SATISFIED),
        ),
    )

    with pytest.raises(ValueError, match="duplicada"):
        CommercialPassport(
            context=_context(),
            opportunities=(
                CommercialPassportOpportunityAssessment(opportunity, readiness),
                CommercialPassportOpportunityAssessment(opportunity, readiness),
            ),
        )


def test_property_passport_service_builds_dynamic_projection() -> None:
    context = _context()
    service = PropertyCommercialPassportService()

    passport = service.build(
        context=context,
        opportunities=(
            PropertyCommercialPassportOpportunityInput(
                opportunity=_opportunity("synthetic-buyer"),
                requirements=(
                    _requirement(
                        "property-document",
                        CommercialPassportRequirementStatus.SATISFIED,
                    ),
                    _requirement(
                        "environmental-evidence",
                        CommercialPassportRequirementStatus.MISSING,
                    ),
                ),
                limitations=("buyer-specific requirement represented in Livestock",),
            ),
        ),
    )

    assert passport.context is context
    assert len(passport.opportunities) == 1
    assessment = passport.opportunities[0]
    assert assessment.opportunity.code == "synthetic-buyer"
    assert assessment.population_eligibility is None
    assert assessment.property_readiness.breakdown.satisfied == 1
    assert assessment.property_readiness.breakdown.missing == 1
    assert assessment.property_readiness.breakdown.interpretation is (
        CommercialReadinessInterpretation.PARTIALLY_READY
    )
    assert "PROPERTY_COMMERCIAL_PASSPORT_IS_DYNAMIC_PROJECTION" in passport.limitations
    assert "FORMAL_ISSUANCE_REQUIRES_DOSSIER_OR_VERIFICATION_BUNDLE" in passport.limitations


def test_property_passport_service_orders_opportunities_deterministically() -> None:
    service = PropertyCommercialPassportService()

    passport = service.build(
        context=_context(),
        opportunities=(
            PropertyCommercialPassportOpportunityInput(
                opportunity=_opportunity("z-market"),
                requirements=(
                    _requirement("z-document", CommercialPassportRequirementStatus.SATISFIED),
                ),
            ),
            PropertyCommercialPassportOpportunityInput(
                opportunity=_opportunity("a-market"),
                requirements=(
                    _requirement("a-document", CommercialPassportRequirementStatus.SATISFIED),
                ),
            ),
        ),
    )

    assert [item.opportunity.code for item in passport.opportunities] == [
        "a-market",
        "z-market",
    ]


def test_property_passport_service_keeps_population_dimension_out_until_f4() -> None:
    service = PropertyCommercialPassportService()

    with pytest.raises(ValueError, match="propriedade"):
        service.build(
            context=_context(),
            opportunities=(
                PropertyCommercialPassportOpportunityInput(
                    opportunity=_opportunity(),
                    requirements=(
                        _requirement(
                            "animal-requirement",
                            CommercialPassportRequirementStatus.SATISFIED,
                            CommercialPassportRequirementDimension.POPULATION_ELIGIBILITY,
                        ),
                    ),
                ),
            ),
        )


def test_property_passport_service_rejects_duplicate_opportunity_codes() -> None:
    service = PropertyCommercialPassportService()

    with pytest.raises(ValueError, match="duplicada"):
        service.build(
            context=_context(),
            opportunities=(
                PropertyCommercialPassportOpportunityInput(
                    opportunity=_opportunity("same-market"),
                    requirements=(
                        _requirement("first", CommercialPassportRequirementStatus.SATISFIED),
                    ),
                ),
                PropertyCommercialPassportOpportunityInput(
                    opportunity=_opportunity("same-market"),
                    requirements=(
                        _requirement("second", CommercialPassportRequirementStatus.SATISFIED),
                    ),
                ),
            ),
        )
