from dataclasses import dataclass, field
from datetime import UTC, datetime

import pytest

from packages.livestock_application.coverage_contribution_service import CoverageContributionService
from packages.livestock_application.dimensional_coverage import (
    CoverageContribution,
    CoverageContributionAdmissibility,
    CoverageContributionValidation,
    StoredCoverageContribution,
)
from packages.livestock_application.event_recorder import LivestockOperationContext
from packages.livestock_domain.animal import Animal, AnimalSex, BirthPropertySource
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference


@dataclass
class Repo:
    items: list[StoredCoverageContribution] = field(default_factory=list)

    def save(self, item: StoredCoverageContribution) -> None:
        self.items.append(item)

    def list_by_subject(
        self, organization_id: OrganizationId, subject_id: TypedId
    ) -> list[StoredCoverageContribution]:
        return [
            item
            for item in self.items
            if item.organization_id == organization_id and item.subject_id == subject_id
        ]


@dataclass
class Animals:
    animal: Animal

    def get_by_id(self, animal_id: TypedId) -> Animal | None:
        return self.animal if self.animal.animal_id == animal_id else None

    def save(self, animal: Animal) -> None:
        pass

    def update(self, animal: Animal) -> None:
        pass

    def find_by_identifier(self, *args: object, **kwargs: object) -> Animal | None:
        return None

    def list_by_organization(self, *args: object, **kwargs: object) -> list[Animal]:
        return [self.animal]

    def get_exit(self, animal_id: TypedId) -> None:
        return None


def test_records_source_neutral_contribution() -> None:
    org = OrganizationId.new()
    animal_id = TypedId.new("animal")
    actor = TypedId.new("actor")
    animal = Animal(
        animal_id=animal_id,
        organization_id=org,
        sex=AnimalSex.FEMALE,
        birth_property_id=None,
        birth_property_source=BirthPropertySource.UNKNOWN,
    )
    repo = Repo()
    context = LivestockOperationContext(
        organization_id=org,
        actor_reference=UniversalReference(
            target_id=actor, organization_id=org, contract_version=1
        ),
        source_reference=UniversalReference(
            target_id=actor, organization_id=org, contract_version=1
        ),
        correlation_id=TypedId.new("correlation"),
    )
    contribution = CoverageContribution(
        dimension="treatment_history",
        covered_from=datetime(2026, 1, 1, tzinfo=UTC),
        covered_until=datetime(2026, 2, 1, tzinfo=UTC),
        validation=CoverageContributionValidation.VALIDATED,
        admissibility=CoverageContributionAdmissibility.ADMISSIBLE,
    )
    saved = CoverageContributionService(repo, Animals(animal)).record(
        context=context, subject_id=animal_id, contribution=contribution
    )
    assert saved.contribution.source_reference is None
    assert repo.items == [saved]


def test_rejects_cross_organization_source() -> None:
    org = OrganizationId.new()
    animal_id = TypedId.new("animal")
    actor = TypedId.new("actor")
    animal = Animal(
        animal_id=animal_id,
        organization_id=org,
        sex=AnimalSex.FEMALE,
        birth_property_id=None,
        birth_property_source=BirthPropertySource.UNKNOWN,
    )
    context = LivestockOperationContext(
        organization_id=org,
        actor_reference=UniversalReference(
            target_id=actor, organization_id=org, contract_version=1
        ),
        source_reference=UniversalReference(
            target_id=actor, organization_id=org, contract_version=1
        ),
        correlation_id=TypedId.new("correlation"),
    )
    contribution = CoverageContribution(
        dimension="treatment_history",
        covered_from=datetime(2026, 1, 1, tzinfo=UTC),
        covered_until=datetime(2026, 2, 1, tzinfo=UTC),
        validation=CoverageContributionValidation.VALIDATED,
        admissibility=CoverageContributionAdmissibility.ADMISSIBLE,
        source_reference=UniversalReference(
            target_id=TypedId.new("document"),
            organization_id=OrganizationId.new(),
            contract_version=1,
        ),
    )
    with pytest.raises(ValueError, match="outra Organization"):
        CoverageContributionService(Repo(), Animals(animal)).record(
            context=context, subject_id=animal_id, contribution=contribution
        )
