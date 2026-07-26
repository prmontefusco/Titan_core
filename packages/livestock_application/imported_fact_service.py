"""Registro de fatos importados de artefato recebido (ADR-0042)."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from packages.core_domain.evidence import ConfidenceTier
from packages.livestock_application.animal_service import AnimalRepositoryPort
from packages.livestock_application.event_recorder import (
    LivestockEventRecorder,
    LivestockOperationContext,
)
from packages.livestock_application.transfer_artifact_service import (
    ReceivedTransferArtifactRepositoryPort,
)
from packages.livestock_domain.events import (
    IMPORTED_FACT_RECORDED,
    imported_fact_recorded_payload,
)
from packages.livestock_domain.imported_fact import ImportedLivestockFact
from packages.shared_kernel import OrganizationId, TypedId


class ImportedLivestockFactRepositoryPort(Protocol):
    def save(self, fact: ImportedLivestockFact) -> None: ...

    def list_by_animal(
        self, organization_id: OrganizationId, animal_id: TypedId
    ) -> list[ImportedLivestockFact]: ...


@dataclass(frozen=True, slots=True)
class ImportedLivestockFactService:
    repository: ImportedLivestockFactRepositoryPort
    artifact_repository: ReceivedTransferArtifactRepositoryPort
    animal_repository: AnimalRepositoryPort
    recorder: LivestockEventRecorder

    def record_imported_fact(
        self,
        context: LivestockOperationContext,
        animal_id: TypedId,
        source_artifact_id: TypedId,
        fact_type: str,
        occurred_at: datetime,
        asserted_by: str,
        confidence_tier: ConfidenceTier,
        payload: dict[str, Any],
    ) -> ImportedLivestockFact:
        animal = self.animal_repository.get_by_id(animal_id)
        if animal is None or animal.organization_id != context.organization_id:
            raise KeyError(f"Animal '{animal_id.value}' nao encontrado.")
        artifact = next(
            (
                candidate
                for candidate in self.artifact_repository.list_by_animal(animal_id)
                if candidate.artifact_id == source_artifact_id
                and candidate.organization_id == context.organization_id
            ),
            None,
        )
        if artifact is None:
            raise KeyError(f"Artefato '{source_artifact_id.value}' nao encontrado.")

        fact = ImportedLivestockFact.create(
            organization_id=context.organization_id,
            animal_id=animal_id,
            source_artifact_id=source_artifact_id,
            fact_type=fact_type,
            occurred_at=occurred_at,
            asserted_by=asserted_by,
            received_by=context.actor_reference.target_id,
            confidence_tier=confidence_tier,
            payload=payload,
        )
        self.repository.save(fact)
        self.recorder.record(
            context=context,
            aggregate_id=fact.imported_fact_id,
            event_type=IMPORTED_FACT_RECORDED,
            payload=imported_fact_recorded_payload(
                imported_fact_id=fact.imported_fact_id,
                animal_id=animal_id,
                source_artifact_id=source_artifact_id,
                fact_type=fact.fact_type,
                occurred_at=occurred_at,
                asserted_by=fact.asserted_by,
                received_by=fact.received_by,
                origin=fact.origin.value,
                confidence_tier=fact.confidence_tier.value,
            ),
            occurred_at=fact.imported_at,
        )
        return fact

    def list_for_animal(
        self, organization_id: OrganizationId, animal_id: TypedId
    ) -> list[ImportedLivestockFact]:
        animal = self.animal_repository.get_by_id(animal_id)
        if animal is None or animal.organization_id != organization_id:
            raise KeyError(f"Animal '{animal_id.value}' nao encontrado.")
        return self.repository.list_by_animal(organization_id, animal_id)
