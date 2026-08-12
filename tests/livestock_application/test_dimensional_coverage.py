"""Contrato source-neutral e primeiro adapter de coverage dimensional."""

from datetime import UTC, datetime, timedelta

import pytest

from packages.core_application.evaluation_service import RuleEvaluationEngine
from packages.core_domain.evaluation import RuleResultStatus
from packages.core_domain.facts import Fact, FactSnapshot
from packages.core_domain.rule import ComparisonOperator, Rule, RuleCondition
from packages.livestock_application.dimensional_coverage import (
    CoverageContribution,
    CoverageContributionAdmissibility,
    CoverageContributionValidation,
    DimensionalCoverageService,
    DimensionalCoverageStatus,
    ReceivedTransferArtifactCoverageAdapter,
    ReceivedTransferCoverageDeclaration,
)
from packages.livestock_application.sanitary_test_coverage import (
    SANITARY_TEST_A_POLICY_CODE,
    TREATMENT_HISTORY_COVERAGE_FACT_TYPE,
    AntimicrobialTreatmentRecord,
    SanitaryTestACoverageService,
    TreatmentMaterialSource,
)
from packages.livestock_domain.transfer_artifact import (
    HistoryCoverage,
    ReceivedTransferArtifact,
)
from packages.shared_kernel import OrganizationId, TypedId

REFERENCE_TIME = datetime(2026, 8, 12, 12, tzinfo=UTC)
REQUIRED_FROM = REFERENCE_TIME - timedelta(days=90)


def _contribution(start: datetime, end: datetime) -> CoverageContribution:
    return CoverageContribution(
        dimension="treatment_history",
        covered_from=start,
        covered_until=end,
        validation=CoverageContributionValidation.VALIDATED,
        admissibility=CoverageContributionAdmissibility.ADMISSIBLE,
    )


def _artifact() -> ReceivedTransferArtifact:
    organization_id = OrganizationId.new()
    return ReceivedTransferArtifact(
        artifact_id=TypedId.new("received_transfer_artifact"),
        organization_id=organization_id,
        animal_id=TypedId.new("animal"),
        source_counterparty_id=TypedId.new("external_counterparty"),
        bundle_digest="a" * 64,
        bundle_issued_at=REFERENCE_TIME - timedelta(days=1),
        transfer_effective_at=REFERENCE_TIME,
        coverage=HistoryCoverage(
            known_from=REQUIRED_FROM,
            known_until=REFERENCE_TIME,
        ),
    )


def _evaluate(fact: Fact) -> RuleResultStatus:
    organization_id = OrganizationId.new()
    rule = Rule.create(
        policy_id=TypedId.new("policy"),
        organization_id=organization_id,
        code=SANITARY_TEST_A_POLICY_CODE,
        name="Ausencia conhecida de tratamento antimicrobiano em 90 dias",
        required_evidence_types=(TREATMENT_HISTORY_COVERAGE_FACT_TYPE,),
        conditions=(
            RuleCondition(
                fact_type=TREATMENT_HISTORY_COVERAGE_FACT_TYPE,
                payload_key="has_antimicrobial_treatment",
                operator=ComparisonOperator.EQUALS,
                expected_value=False,
            ),
        ),
    )
    snapshot = FactSnapshot.create(
        organization_id=organization_id,
        target_id=TypedId.new("animal"),
        as_of=REFERENCE_TIME,
        facts=(fact,),
    )
    return RuleEvaluationEngine().evaluate(rule, snapshot).status


def test_two_source_neutral_contributions_can_form_complete_coverage() -> None:
    midpoint = REQUIRED_FROM + timedelta(days=45)

    assessment = DimensionalCoverageService().assess(
        dimension="treatment_history",
        required_from=REQUIRED_FROM,
        required_until=REFERENCE_TIME,
        contributions=(
            _contribution(REQUIRED_FROM, midpoint),
            _contribution(midpoint, REFERENCE_TIME),
        ),
    )

    assert assessment.status is DimensionalCoverageStatus.COMPLETE
    assert assessment.accepted_intervals == ((REQUIRED_FROM, REFERENCE_TIME),)


def test_gap_between_contributions_remains_partial() -> None:
    assessment = DimensionalCoverageService().assess(
        dimension="treatment_history",
        required_from=REQUIRED_FROM,
        required_until=REFERENCE_TIME,
        contributions=(
            _contribution(REQUIRED_FROM, REQUIRED_FROM + timedelta(days=30)),
            _contribution(REQUIRED_FROM + timedelta(days=31), REFERENCE_TIME),
        ),
    )

    assert assessment.status is DimensionalCoverageStatus.PARTIAL
    assert assessment.limitations == ("COVERAGE_INTERVAL_GAP",)


def test_received_transfer_artifact_without_declaration_contributes_nothing() -> None:
    assert ReceivedTransferArtifactCoverageAdapter().adapt(_artifact()) == ()


def test_received_transfer_artifact_is_first_explicit_adapter() -> None:
    artifact = _artifact()

    contributions = ReceivedTransferArtifactCoverageAdapter().adapt(
        artifact,
        declarations=(
            ReceivedTransferCoverageDeclaration(
                dimension="treatment_history",
                covered_from=REQUIRED_FROM,
                covered_until=REFERENCE_TIME,
                validation=CoverageContributionValidation.VALIDATED,
                admissibility=CoverageContributionAdmissibility.ADMISSIBLE,
            ),
        ),
    )

    assert len(contributions) == 1
    assert contributions[0].source_reference is not None
    assert contributions[0].source_reference.target_id == artifact.artifact_id
    assessment = DimensionalCoverageService().assess(
        dimension="treatment_history",
        required_from=REQUIRED_FROM,
        required_until=REFERENCE_TIME,
        contributions=contributions,
    )
    assert assessment.source_references == (contributions[0].source_reference,)


def test_adapter_rejects_contribution_beyond_artifact_interval() -> None:
    with pytest.raises(ValueError, match="excede"):
        ReceivedTransferArtifactCoverageAdapter().adapt(
            _artifact(),
            declarations=(
                ReceivedTransferCoverageDeclaration(
                    dimension="treatment_history",
                    covered_from=REQUIRED_FROM - timedelta(days=1),
                    covered_until=REFERENCE_TIME,
                    validation=CoverageContributionValidation.VALIDATED,
                    admissibility=CoverageContributionAdmissibility.ADMISSIBLE,
                ),
            ),
        )


def test_composed_complete_coverage_without_treatment_is_satisfied() -> None:
    midpoint = REQUIRED_FROM + timedelta(days=45)
    fact = SanitaryTestACoverageService().build_fact_from_contributions(
        reference_time=REFERENCE_TIME,
        contributions=(
            _contribution(REQUIRED_FROM, midpoint),
            _contribution(midpoint, REFERENCE_TIME),
        ),
    )

    assert _evaluate(fact) is RuleResultStatus.ATENDIDA


def test_composed_complete_coverage_with_treatment_is_not_satisfied() -> None:
    fact = SanitaryTestACoverageService().build_fact_from_contributions(
        reference_time=REFERENCE_TIME,
        contributions=(_contribution(REQUIRED_FROM, REFERENCE_TIME),),
        treatments=(
            AntimicrobialTreatmentRecord(
                occurred_at=REFERENCE_TIME - timedelta(days=10),
                source=TreatmentMaterialSource.IMPORTED_DOCUMENTED,
                source_artifact_id="artifact-1",
            ),
        ),
    )

    assert _evaluate(fact) is RuleResultStatus.NAO_ATENDIDA


def test_partial_composed_coverage_is_indeterminate() -> None:
    fact = SanitaryTestACoverageService().build_fact_from_contributions(
        reference_time=REFERENCE_TIME,
        contributions=(_contribution(REQUIRED_FROM + timedelta(days=1), REFERENCE_TIME),),
    )

    assert "has_antimicrobial_treatment" not in fact.payload
    assert _evaluate(fact) is RuleResultStatus.INDETERMINADA
