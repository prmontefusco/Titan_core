"""Caso de uso de importação source-neutral de coverage dimensional."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from packages.livestock_application.animal_service import AnimalRepositoryPort
from packages.livestock_application.dimensional_coverage import (
    CoverageContribution,
    StoredCoverageContribution,
)
from packages.livestock_application.event_recorder import LivestockOperationContext
from packages.shared_kernel import OrganizationId, TypedId


class CoverageContributionRepositoryPort(Protocol):
    def save(self, item: StoredCoverageContribution) -> None: ...

    def list_by_subject(
        self, organization_id: OrganizationId, subject_id: TypedId
    ) -> list[StoredCoverageContribution]: ...


@dataclass(frozen=True, slots=True)
class CoverageContributionService:
    repository: CoverageContributionRepositoryPort
    animal_repository: AnimalRepositoryPort

    def record(
        self,
        *,
        context: LivestockOperationContext,
        subject_id: TypedId,
        contribution: CoverageContribution,
        known_at: datetime,
    ) -> StoredCoverageContribution:
        animal = self.animal_repository.get_by_id(subject_id)
        if animal is None or animal.organization_id != context.organization_id:
            raise KeyError(f"Animal '{subject_id.value}' nao encontrado.")
        source = contribution.source_reference
        if source is not None and source.organization_id != context.organization_id:
            raise ValueError("A fonte da contribuicao pertence a outra Organization.")
        item = StoredCoverageContribution.create(
            organization_id=context.organization_id,
            subject_id=subject_id,
            contribution=contribution,
            recorded_by=context.actor_reference.target_id,
            known_at=known_at,
        )
        self.repository.save(item)
        return item

    def list_for_subject(
        self, organization_id: OrganizationId, subject_id: TypedId
    ) -> list[StoredCoverageContribution]:
        animal = self.animal_repository.get_by_id(subject_id)
        if animal is None or animal.organization_id != organization_id:
            raise KeyError(f"Animal '{subject_id.value}' nao encontrado.")
        return self.repository.list_by_subject(organization_id, subject_id)
