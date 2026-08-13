from datetime import UTC, datetime, timedelta

from packages.core_domain.evidence import ConfidenceTier
from packages.livestock_domain.medication_classification import (
    MedicationClassificationStatus,
    MedicationClassificationValidation,
    MedicationSanitaryCategory,
    MedicationSanitaryClassificationAssertion,
)
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference

NOW = datetime(2026, 8, 12, tzinfo=UTC)


def assertion(
    status: MedicationClassificationStatus = MedicationClassificationStatus.UNKNOWN,
    observed: datetime = NOW,
    known_at: datetime | None = None,
) -> MedicationSanitaryClassificationAssertion:
    org = OrganizationId.new()
    return MedicationSanitaryClassificationAssertion(
        TypedId.new("medication_classification_assertion"),
        org,
        TypedId.new("medication"),
        MedicationSanitaryCategory.ANTIMICROBIAL,
        status,
        None,
        None,
        observed,
        UniversalReference(TypedId.new("manual_source"), org, 1),
        MedicationClassificationValidation.STRUCTURALLY_VALIDATED,
        ConfidenceTier.DOCUMENTED,
        known_at=observed if known_at is None else known_at,
    )


def test_unknown_assertion_is_distinct_from_no_assertion_and_negative() -> None:
    unknown = assertion()
    assert unknown.status is MedicationClassificationStatus.UNKNOWN
    assert unknown.status.value != MedicationClassificationStatus.DOES_NOT_APPLY.value


def test_validity_is_half_open() -> None:
    item = assertion(MedicationClassificationStatus.APPLIES)
    assert item.known_as_of(NOW)


def test_observacao_anterior_nao_antecipa_conhecimento() -> None:
    observed = NOW
    known_at = NOW + timedelta(days=2)
    item = assertion(observed=observed, known_at=known_at)

    assert item.known_as_of(NOW + timedelta(days=1)) is False
    assert item.known_as_of(known_at) is True
