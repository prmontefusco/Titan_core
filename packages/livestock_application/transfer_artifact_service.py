"""Registro de artefato recebido para continuidade de proveniencia (ADR-0042)."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from packages.livestock_application.animal_service import AnimalRepositoryPort
from packages.livestock_application.event_recorder import (
    LivestockEventRecorder,
    LivestockOperationContext,
)
from packages.livestock_application.external_counterparty_service import (
    ExternalCounterpartyRepositoryPort,
)
from packages.livestock_domain.events import (
    TRANSFER_ARTIFACT_RECEIVED,
    transfer_artifact_received_payload,
)
from packages.livestock_domain.transfer_artifact import (
    HistoryCoverage,
    ReceivedTransferArtifact,
)
from packages.shared_kernel import OrganizationId, TypedId


class ReceivedTransferArtifactRepositoryPort(Protocol):
    def save(self, artifact: ReceivedTransferArtifact) -> None: ...

    def get_by_id(self, artifact_id: TypedId) -> ReceivedTransferArtifact | None: ...

    def list_by_animal(self, animal_id: TypedId) -> list[ReceivedTransferArtifact]: ...


@dataclass(frozen=True, slots=True)
class ReceivedTransferArtifactService:
    repository: ReceivedTransferArtifactRepositoryPort
    animal_repository: AnimalRepositoryPort
    counterparty_repository: ExternalCounterpartyRepositoryPort
    recorder: LivestockEventRecorder

    def register_received_artifact(
        self,
        context: LivestockOperationContext,
        animal_id: TypedId,
        source_counterparty_id: TypedId,
        bundle_digest: str,
        bundle_issued_at: datetime,
        transfer_effective_at: datetime,
        coverage_known_from: datetime | None,
        coverage_known_until: datetime | None,
        issuer_name: str | None = None,
    ) -> ReceivedTransferArtifact:
        organization_id = context.organization_id
        animal = self.animal_repository.get_by_id(animal_id)
        if animal is None or animal.organization_id != organization_id:
            raise KeyError(f"Animal '{animal_id.value}' nao encontrado.")
        counterparty = self.counterparty_repository.get_by_id(source_counterparty_id)
        if counterparty is None or counterparty.organization_id != organization_id:
            raise KeyError(f"Contraparte '{source_counterparty_id.value}' nao encontrada.")

        coverage = HistoryCoverage.from_transfer(
            known_from=coverage_known_from,
            known_until=coverage_known_until,
            transfer_effective_at=transfer_effective_at,
        )
        artifact = ReceivedTransferArtifact(
            artifact_id=TypedId.new("received_transfer_artifact"),
            organization_id=organization_id,
            animal_id=animal_id,
            source_counterparty_id=source_counterparty_id,
            bundle_digest=bundle_digest,
            bundle_issued_at=bundle_issued_at,
            transfer_effective_at=transfer_effective_at,
            coverage=coverage,
            issuer_name=issuer_name,
            created_at=datetime.now(UTC),
        )
        self.repository.save(artifact)
        self.recorder.record(
            context=context,
            aggregate_id=artifact.artifact_id,
            event_type=TRANSFER_ARTIFACT_RECEIVED,
            payload=transfer_artifact_received_payload(
                artifact_id=artifact.artifact_id,
                animal_id=animal_id,
                source_counterparty_id=source_counterparty_id,
                bundle_digest=bundle_digest,
                bundle_issued_at=bundle_issued_at,
                transfer_effective_at=transfer_effective_at,
                coverage_known_from=coverage.known_from,
                coverage_known_until=coverage.known_until,
                gap_codes=tuple(gap.code.value for gap in coverage.gaps),
                issuer_name=issuer_name,
            ),
            occurred_at=artifact.created_at,
        )
        return artifact

    def list_for_animal(
        self, organization_id: OrganizationId, animal_id: TypedId
    ) -> list[ReceivedTransferArtifact]:
        animal = self.animal_repository.get_by_id(animal_id)
        if animal is None or animal.organization_id != organization_id:
            raise KeyError(f"Animal '{animal_id.value}' nao encontrado.")
        return self.repository.list_by_animal(animal_id)
