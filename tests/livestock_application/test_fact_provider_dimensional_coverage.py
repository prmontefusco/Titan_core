"""Selecao temporal das contribuicoes de coverage no snapshot Livestock."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import cast

from packages.livestock_application.animal_service import AnimalRepositoryPort
from packages.livestock_application.dimensional_coverage import (
    CoverageContribution,
    CoverageContributionAdmissibility,
    CoverageContributionValidation,
    StoredCoverageContribution,
)
from packages.livestock_application.fact_provider import LivestockFactProvider
from packages.livestock_application.property_service import RuralPropertyRepositoryPort
from packages.shared_kernel import OrganizationId, TypedId


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
            covered_from=datetime(2026, 1, 1, tzinfo=UTC),
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
