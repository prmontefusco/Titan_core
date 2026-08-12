"""Testes de referência da Policy fictícia SANITARY_TEST_A_v1."""

from datetime import UTC, datetime, timedelta

import pytest

from packages.core_application.evaluation_service import RuleEvaluationEngine
from packages.core_domain.evaluation import RuleResultStatus
from packages.core_domain.evidence import ConfidenceTier
from packages.core_domain.facts import Fact, FactSnapshot
from packages.core_domain.rule import ComparisonOperator, Rule, RuleCondition
from packages.livestock_application.dimensional_coverage import (
    CoverageContribution,
    CoverageContributionAdmissibility,
    CoverageContributionValidation,
)
from packages.livestock_application.sanitary_test_coverage import (
    SANITARY_TEST_A_POLICY_CODE,
    TREATMENT_HISTORY_COVERAGE_FACT_TYPE,
    AntimicrobialTreatmentRecord,
    MedicationTreatmentRecord,
    SanitaryTestACoverageService,
    TreatmentCoverageDeclaration,
    TreatmentCoverageStatus,
    TreatmentMaterialSource,
)
from packages.livestock_domain.medication_classification import (
    MedicationClassificationStatus,
    MedicationClassificationValidation,
    MedicationSanitaryCategory,
    MedicationSanitaryClassificationAssertion,
)
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference


@pytest.fixture
def reference_time() -> datetime:
    return datetime(2026, 8, 12, 12, tzinfo=UTC)


def _rule(organization_id: OrganizationId) -> Rule:
    policy_id = TypedId.new("policy")
    return Rule.create(
        policy_id=policy_id,
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


def _evaluate(fact: Fact, reference_time: datetime) -> RuleResultStatus:
    organization_id = OrganizationId.new()
    snapshot = FactSnapshot.create(
        organization_id=organization_id,
        target_id=TypedId.new("animal"),
        as_of=reference_time,
        facts=(fact,),
    )
    return RuleEvaluationEngine().evaluate(_rule(organization_id), snapshot).status


def _complete(reference_time: datetime) -> TreatmentCoverageDeclaration:
    return TreatmentCoverageDeclaration(
        known_from=reference_time - timedelta(days=90),
        known_until=reference_time,
        source=TreatmentMaterialSource.LOCAL_TREATMENT_APPLICATION,
    )


def test_complete_coverage_with_prohibited_fact_is_not_satisfied(
    reference_time: datetime,
) -> None:
    fact = SanitaryTestACoverageService().build_fact(
        reference_time=reference_time,
        declaration=_complete(reference_time),
        treatments=(
            AntimicrobialTreatmentRecord(
                occurred_at=reference_time - timedelta(days=10),
                source=TreatmentMaterialSource.LOCAL_TREATMENT_APPLICATION,
            ),
        ),
    )

    assert _evaluate(fact, reference_time) is RuleResultStatus.NAO_ATENDIDA


def test_complete_coverage_without_prohibited_fact_is_satisfied(
    reference_time: datetime,
) -> None:
    fact = SanitaryTestACoverageService().build_fact(
        reference_time=reference_time,
        declaration=_complete(reference_time),
    )

    assert _evaluate(fact, reference_time) is RuleResultStatus.ATENDIDA


@pytest.mark.parametrize(
    "declaration, expected_status",
    [
        (None, TreatmentCoverageStatus.ABSENT),
        (
            TreatmentCoverageDeclaration(
                known_from=datetime(2026, 7, 1, tzinfo=UTC),
                known_until=datetime(2026, 8, 12, 12, tzinfo=UTC),
                source=TreatmentMaterialSource.LOCAL_TREATMENT_APPLICATION,
            ),
            TreatmentCoverageStatus.PARTIAL,
        ),
        (
            TreatmentCoverageDeclaration(
                known_from=datetime(2026, 5, 1, tzinfo=UTC),
                known_until=datetime(2026, 8, 12, 12, tzinfo=UTC),
                source=TreatmentMaterialSource.LOCAL_TREATMENT_APPLICATION,
                accessible=False,
            ),
            TreatmentCoverageStatus.INACCESSIBLE,
        ),
        (
            TreatmentCoverageDeclaration(
                known_from=datetime(2026, 5, 1, tzinfo=UTC),
                known_until=datetime(2026, 8, 12, 12, tzinfo=UTC),
                source=TreatmentMaterialSource.LOCAL_TREATMENT_APPLICATION,
                conflicting=True,
            ),
            TreatmentCoverageStatus.CONFLICTING,
        ),
    ],
)
def test_insufficient_coverage_is_indeterminate(
    declaration: TreatmentCoverageDeclaration | None,
    expected_status: TreatmentCoverageStatus,
    reference_time: datetime,
) -> None:
    fact = SanitaryTestACoverageService().build_fact(
        reference_time=reference_time,
        declaration=declaration,
    )

    assert fact.payload["coverage_status"] == expected_status.value
    assert "has_antimicrobial_treatment" not in fact.payload
    assert _evaluate(fact, reference_time) is RuleResultStatus.INDETERMINADA


def test_informed_only_material_is_valid_as_received_but_not_admissible(
    reference_time: datetime,
) -> None:
    fact = SanitaryTestACoverageService().build_fact(
        reference_time=reference_time,
        declaration=TreatmentCoverageDeclaration(
            known_from=reference_time - timedelta(days=90),
            known_until=reference_time,
            source=TreatmentMaterialSource.INFORMED_ONLY,
        ),
    )

    assert fact.payload["coverage_status"] == TreatmentCoverageStatus.COMPLETE.value
    assert fact.payload["admissibility"] == "INSUFFICIENT"
    assert "has_antimicrobial_treatment" not in fact.payload
    assert _evaluate(fact, reference_time) is RuleResultStatus.INDETERMINADA


def test_imported_treatment_requires_source_artifact(reference_time: datetime) -> None:
    with pytest.raises(ValueError, match="source_artifact_id"):
        AntimicrobialTreatmentRecord(
            occurred_at=reference_time,
            source=TreatmentMaterialSource.IMPORTED_DOCUMENTED,
        )


def test_classification_is_independent_and_missing_assertion_is_indeterminate(
    reference_time: datetime,
) -> None:
    medication_id = TypedId.new("medication")
    fact = SanitaryTestACoverageService().build_fact_from_classified_material(
        reference_time=reference_time,
        knowledge_cutoff=reference_time,
        contributions=(
            CoverageContribution(
                "treatment_history",
                reference_time - timedelta(days=90),
                reference_time,
                CoverageContributionValidation.VALIDATED,
                CoverageContributionAdmissibility.ADMISSIBLE,
            ),
        ),
        treatments=(
            MedicationTreatmentRecord(
                medication_id,
                reference_time - timedelta(days=1),
                TreatmentMaterialSource.LOCAL_TREATMENT_APPLICATION,
            ),
        ),
        classifications=(),
    )
    assert fact.payload["coverage_status"] == "COMPLETE"
    assert fact.payload["medication_classification_coverage_status"] == "INCOMPLETE"
    assert "has_antimicrobial_treatment" not in fact.payload
    assert _evaluate(fact, reference_time) is RuleResultStatus.INDETERMINADA


def test_known_antimicrobial_is_not_satisfied(reference_time: datetime) -> None:
    organization_id = OrganizationId.new()
    medication_id = TypedId.new("medication")
    assertion = MedicationSanitaryClassificationAssertion(
        TypedId.new("medication_classification_assertion"),
        organization_id,
        medication_id,
        MedicationSanitaryCategory.ANTIMICROBIAL,
        MedicationClassificationStatus.APPLIES,
        None,
        None,
        reference_time - timedelta(days=2),
        UniversalReference(TypedId.new("manual_source"), organization_id, 1),
        MedicationClassificationValidation.STRUCTURALLY_VALIDATED,
        ConfidenceTier.DOCUMENTED,
    )
    fact = SanitaryTestACoverageService().build_fact_from_classified_material(
        reference_time=reference_time,
        knowledge_cutoff=reference_time,
        contributions=(
            CoverageContribution(
                "treatment_history",
                reference_time - timedelta(days=90),
                reference_time,
                CoverageContributionValidation.VALIDATED,
                CoverageContributionAdmissibility.ADMISSIBLE,
            ),
        ),
        treatments=(
            MedicationTreatmentRecord(
                medication_id,
                reference_time - timedelta(days=1),
                TreatmentMaterialSource.LOCAL_TREATMENT_APPLICATION,
            ),
        ),
        classifications=(assertion,),
    )
    assert fact.payload["medication_classification_coverage_status"] == "COMPLETE"
    assert _evaluate(fact, reference_time) is RuleResultStatus.NAO_ATENDIDA
