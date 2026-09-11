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
    CommercialRequirementAssessment,
    PopulationEligibilitySummary,
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


def test_not_applicable_stays_out_of_readiness_denominator() -> None:
    readiness = PropertyCommercialReadiness(
        requirements=(
            _requirement("satisfied", CommercialPassportRequirementStatus.SATISFIED),
            _requirement("not-applicable", CommercialPassportRequirementStatus.NOT_APPLICABLE),
        ),
    )

    assert readiness.breakdown.applicable_count == 1
    assert readiness.breakdown.derived_ratio == 1.0


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
