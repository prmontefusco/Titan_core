"""Selecao temporal das contribuicoes de coverage no snapshot Livestock."""

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import cast

from packages.core_domain.evidence import ConfidenceTier
from packages.livestock_application.animal_service import AnimalRepositoryPort
from packages.livestock_application.dimensional_coverage import (
    CoverageContribution,
    CoverageContributionAdmissibility,
    CoverageContributionValidation,
    StoredCoverageContribution,
)
from packages.livestock_application.fact_provider import LivestockFactProvider
from packages.livestock_application.property_service import RuralPropertyRepositoryPort
from packages.livestock_application.transfer_artifact_service import (
    ReceivedTransferArtifactRepositoryPort,
)
from packages.livestock_domain.imported_fact import ImportedLivestockFact
from packages.livestock_domain.medication_classification import (
    MedicationClassificationStatus,
    MedicationClassificationValidation,
    MedicationSanitaryCategory,
    MedicationSanitaryClassificationAssertion,
)
from packages.livestock_domain.transfer_artifact import HistoryCoverage, ReceivedTransferArtifact
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference


@dataclass
class CoverageRepository:
    items: list[StoredCoverageContribution]

    def list_by_subject(
        self, organization_id: OrganizationId, subject_id: TypedId
    ) -> list[StoredCoverageContribution]:
        return [
            item
            for item in self.items
            if item.organization_id == organization_id and item.subject_id == subject_id
        ]


@dataclass
class EmptyRepository:
    def get_by_id(self, _entity_id: TypedId) -> None:
        return None


@dataclass
class ImportedFacts:
    items: list[ImportedLivestockFact]

    def list_by_animal(
        self, organization_id: OrganizationId, animal_id: TypedId
    ) -> list[ImportedLivestockFact]:
        return [
            item
            for item in self.items
            if item.organization_id == organization_id and item.animal_id == animal_id
        ]


@dataclass
class TransferArtifacts:
    items: list[ReceivedTransferArtifact]

    def list_by_animal(self, animal_id: TypedId) -> list[ReceivedTransferArtifact]:
        return [item for item in self.items if item.animal_id == animal_id]


@dataclass
class Classifications:
    items: list[MedicationSanitaryClassificationAssertion]

    def save(self, item: MedicationSanitaryClassificationAssertion) -> None:
        self.items.append(item)

    def list_by_medication(
        self, organization_id: OrganizationId, medication_id: TypedId
    ) -> list[MedicationSanitaryClassificationAssertion]:
        return [
            item
            for item in self.items
            if item.organization_id == organization_id and item.medication_id == medication_id
        ]


def _stored(
    *,
    organization_id: OrganizationId,
    animal_id: TypedId,
    known_at: datetime,
) -> StoredCoverageContribution:
    return StoredCoverageContribution.create(
        organization_id=organization_id,
        subject_id=animal_id,
        contribution=CoverageContribution(
            dimension="treatment_history",
            covered_from=datetime(2025, 11, 1, tzinfo=UTC),
            covered_until=datetime(2026, 2, 1, tzinfo=UTC),
            validation=CoverageContributionValidation.VALIDATED,
            admissibility=CoverageContributionAdmissibility.ADMISSIBLE,
        ),
        recorded_by=TypedId.new("actor"),
        known_at=known_at,
    )


def test_temporal_snapshot_excludes_coverage_known_after_cutoff() -> None:
    organization_id = OrganizationId.new()
    animal_id = TypedId.new("animal")
    cutoff = datetime(2026, 2, 5, tzinfo=UTC)
    provider = LivestockFactProvider(
        property_repository=cast(RuralPropertyRepositoryPort, EmptyRepository()),
        animal_repository=cast(AnimalRepositoryPort, EmptyRepository()),
        coverage_contribution_repository=CoverageRepository(
            [
                _stored(
                    organization_id=organization_id,
                    animal_id=animal_id,
                    known_at=cutoff - timedelta(days=1),
                ),
                _stored(
                    organization_id=organization_id,
                    animal_id=animal_id,
                    known_at=cutoff + timedelta(days=1),
                ),
            ]
        ),
    )

    snapshot = provider.get_snapshot_with_temporal_context(
        organization_id,
        animal_id,
        reference_time=datetime(2026, 2, 1, tzinfo=UTC),
        knowledge_cutoff=cutoff,
    )

    coverage_facts = [
        fact
        for fact in snapshot.facts
        if fact.fact_type == "livestock.dimensional_coverage_contribution"
    ]
    assert len(coverage_facts) == 1
    assert coverage_facts[0].known_at == cutoff - timedelta(days=1)


def test_temporal_snapshot_includes_transfer_coverage_known_after_reference_before_cutoff() -> None:
    organization_id = OrganizationId.new()
    animal_id = TypedId.new("animal")
    reference_time = datetime(2026, 2, 1, tzinfo=UTC)
    cutoff = reference_time + timedelta(days=2)
    artifact = ReceivedTransferArtifact(
        artifact_id=TypedId.new("received_transfer_artifact"),
        organization_id=organization_id,
        animal_id=animal_id,
        source_counterparty_id=TypedId.new("external_counterparty"),
        bundle_digest="a" * 64,
        bundle_issued_at=reference_time - timedelta(days=2),
        transfer_effective_at=reference_time - timedelta(days=1),
        coverage=HistoryCoverage(
            known_from=reference_time - timedelta(days=10),
            known_until=reference_time,
        ),
        created_at=reference_time + timedelta(days=1),
    )
    provider = LivestockFactProvider(
        property_repository=cast(RuralPropertyRepositoryPort, EmptyRepository()),
        animal_repository=cast(AnimalRepositoryPort, EmptyRepository()),
        transfer_artifact_repository=cast(
            ReceivedTransferArtifactRepositoryPort, TransferArtifacts([artifact])
        ),
    )

    snapshot = provider.get_snapshot_with_temporal_context(
        organization_id,
        animal_id,
        reference_time=reference_time,
        knowledge_cutoff=cutoff,
    )

    fact = next(item for item in snapshot.facts if item.fact_type == "livestock.history_coverage")
    assert fact.observed_at == artifact.transfer_effective_at
    assert fact.known_at == artifact.created_at


def test_sanitary_fact_requires_classification_known_by_cutoff() -> None:
    organization_id = OrganizationId.new()
    animal_id = TypedId.new("animal")
    medication_id = TypedId.new("medication")
    reference_time = datetime(2026, 2, 1, tzinfo=UTC)
    cutoff = datetime(2026, 2, 5, tzinfo=UTC)
    imported = ImportedLivestockFact.create(
        organization_id=organization_id,
        animal_id=animal_id,
        source_artifact_id=TypedId.new("received_transfer_artifact"),
        fact_type="livestock.treatment_applied",
        occurred_at=reference_time - timedelta(days=2),
        asserted_by="Origem ficticia",
        received_by=TypedId.new("actor"),
        confidence_tier=ConfidenceTier.DOCUMENTED,
        payload={"medication_id": str(medication_id.value)},
    )
    imported = replace(imported, imported_at=cutoff - timedelta(days=1))
    assertion = MedicationSanitaryClassificationAssertion(
        assertion_id=TypedId.new("medication_classification_assertion"),
        organization_id=organization_id,
        medication_id=medication_id,
        category=MedicationSanitaryCategory.ANTIMICROBIAL,
        status=MedicationClassificationStatus.APPLIES,
        valid_from=None,
        valid_to=None,
        observed_at=reference_time - timedelta(days=2),
        source_reference=UniversalReference(
            target_id=TypedId.new("document"),
            organization_id=organization_id,
            contract_version=1,
        ),
        validation_status=MedicationClassificationValidation.STRUCTURALLY_VALIDATED,
        confidence_tier=ConfidenceTier.DOCUMENTED,
        known_at=cutoff + timedelta(days=1),
    )
    provider = LivestockFactProvider(
        property_repository=cast(RuralPropertyRepositoryPort, EmptyRepository()),
        animal_repository=cast(AnimalRepositoryPort, EmptyRepository()),
        coverage_contribution_repository=CoverageRepository(
            [_stored(organization_id=organization_id, animal_id=animal_id, known_at=cutoff)]
        ),
        imported_fact_repository=ImportedFacts([imported]),
        medication_classification_repository=Classifications([assertion]),
    )

    snapshot = provider.get_snapshot_with_temporal_context(
        organization_id,
        animal_id,
        reference_time=reference_time,
        knowledge_cutoff=cutoff,
    )

    fact = next(
        item for item in snapshot.facts if item.fact_type == "livestock.coverage.treatment_history"
    )
    assert fact.payload["medication_classification_coverage_status"] == "INCOMPLETE"
    assert "has_antimicrobial_treatment" not in fact.payload


def test_sanitary_fact_preserves_selected_assertion_provenance() -> None:
    organization_id = OrganizationId.new()
    animal_id = TypedId.new("animal")
    medication_id = TypedId.new("medication")
    reference_time = datetime(2026, 2, 1, tzinfo=UTC)
    cutoff = datetime(2026, 2, 5, tzinfo=UTC)
    imported = replace(
        ImportedLivestockFact.create(
            organization_id=organization_id,
            animal_id=animal_id,
            source_artifact_id=TypedId.new("received_transfer_artifact"),
            fact_type="livestock.treatment_applied",
            occurred_at=reference_time - timedelta(days=2),
            asserted_by="Origem ficticia",
            received_by=TypedId.new("actor"),
            confidence_tier=ConfidenceTier.DOCUMENTED,
            payload={"medication_id": str(medication_id.value)},
        ),
        imported_at=cutoff - timedelta(days=1),
    )
    assertion = MedicationSanitaryClassificationAssertion(
        assertion_id=TypedId.new("medication_classification_assertion"),
        organization_id=organization_id,
        medication_id=medication_id,
        category=MedicationSanitaryCategory.ANTIMICROBIAL,
        status=MedicationClassificationStatus.APPLIES,
        valid_from=None,
        valid_to=None,
        observed_at=reference_time - timedelta(days=2),
        source_reference=UniversalReference(
            target_id=TypedId.new("document"),
            organization_id=organization_id,
            contract_version=1,
        ),
        validation_status=MedicationClassificationValidation.STRUCTURALLY_VALIDATED,
        confidence_tier=ConfidenceTier.DOCUMENTED,
        known_at=cutoff - timedelta(days=1),
    )
    provider = LivestockFactProvider(
        property_repository=cast(RuralPropertyRepositoryPort, EmptyRepository()),
        animal_repository=cast(AnimalRepositoryPort, EmptyRepository()),
        coverage_contribution_repository=CoverageRepository(
            [_stored(organization_id=organization_id, animal_id=animal_id, known_at=cutoff)]
        ),
        imported_fact_repository=ImportedFacts([imported]),
        medication_classification_repository=Classifications([assertion]),
    )

    snapshot = provider.get_snapshot_with_temporal_context(
        organization_id,
        animal_id,
        reference_time=reference_time,
        knowledge_cutoff=cutoff,
    )

    fact = next(
        item for item in snapshot.facts if item.fact_type == "livestock.coverage.treatment_history"
    )
    assert fact.payload["has_antimicrobial_treatment"] is True
    assert fact.payload["medication_classification_assertion_ids"] == [
        assertion.assertion_id.value.hex
    ]
    assert fact.payload["medication_classification_source_references"] == [
        assertion.source_reference.target_id.value.hex
    ]
