"""Orquestracao minima de aquisicao documental sobre conceitos existentes."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from packages.core_domain.evidence import ConfidenceTier
from packages.livestock_application.event_recorder import LivestockOperationContext
from packages.livestock_application.imported_fact_service import ImportedLivestockFactService
from packages.livestock_application.transfer_artifact_service import (
    ReceivedTransferArtifactService,
)
from packages.livestock_domain.imported_fact import ImportedLivestockFact
from packages.livestock_domain.transfer_artifact import ReceivedTransferArtifact
from packages.shared_kernel import TypedId


@dataclass(frozen=True, slots=True)
class DocumentaryImportedFactInput:
    fact_type: str
    occurred_at: datetime
    asserted_by: str
    confidence_tier: ConfidenceTier
    payload: dict[str, Any]


@dataclass(frozen=True, slots=True)
class DocumentaryAcquisitionResult:
    artifact: ReceivedTransferArtifact
    imported_facts: tuple[ImportedLivestockFact, ...]


@dataclass(frozen=True, slots=True)
class DocumentaryAcquisitionService:
    artifact_service: ReceivedTransferArtifactService
    imported_fact_service: ImportedLivestockFactService

    def register_documentary_acquisition(
        self,
        *,
        context: LivestockOperationContext,
        animal_id: TypedId,
        source_counterparty_id: TypedId,
        bundle_digest: str,
        bundle_issued_at: datetime,
        transfer_effective_at: datetime,
        coverage_known_from: datetime | None,
        coverage_known_until: datetime | None,
        issuer_name: str | None = None,
        imported_facts: tuple[DocumentaryImportedFactInput, ...] = (),
    ) -> DocumentaryAcquisitionResult:
        artifact = self.artifact_service.register_received_artifact(
            context=context,
            animal_id=animal_id,
            source_counterparty_id=source_counterparty_id,
            bundle_digest=bundle_digest,
            bundle_issued_at=bundle_issued_at,
            transfer_effective_at=transfer_effective_at,
            coverage_known_from=coverage_known_from,
            coverage_known_until=coverage_known_until,
            issuer_name=issuer_name,
        )
        recorded_facts = tuple(
            self.imported_fact_service.record_imported_fact(
                context=context,
                animal_id=animal_id,
                source_artifact_id=artifact.artifact_id,
                fact_type=fact.fact_type,
                occurred_at=fact.occurred_at,
                asserted_by=fact.asserted_by,
                confidence_tier=fact.confidence_tier,
                payload=fact.payload,
            )
            for fact in imported_facts
        )
        return DocumentaryAcquisitionResult(
            artifact=artifact,
            imported_facts=recorded_facts,
        )
