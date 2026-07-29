"""Registro append-only da qualificacao de estabelecimento por mercado."""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from packages.core_domain.evidence import ConfidenceTier
from packages.livestock_application.event_recorder import (
    LivestockEventRecorder,
    LivestockOperationContext,
)
from packages.livestock_application.external_counterparty_service import (
    ExternalCounterpartyRepositoryPort,
)
from packages.livestock_domain.establishment_qualification import (
    EstablishmentQualification,
    EstablishmentQualificationStatus,
)
from packages.livestock_domain.establishment_qualification_assertion import (
    AssertionStatus,
    EstablishmentQualificationAssertion,
)
from packages.livestock_domain.events import (
    ESTABLISHMENT_QUALIFICATION_RECORDED,
    establishment_qualification_recorded_payload,
)
from packages.livestock_domain.external_counterparty import CounterpartyType
from packages.livestock_domain.qualification_source_artifact import (
    QualificationSourceArtifact,
    SourceCoverage,
)
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference


def establishment_qualification_fact_type(market_purpose: str) -> str:
    sufixo = market_purpose.strip().lower().replace(".", "_")
    return f"livestock.establishment_qualification.{sufixo}"


class EstablishmentQualificationRepositoryPort(Protocol):
    def save(self, qualification: EstablishmentQualification) -> None: ...

    def list_by_counterparty(
        self, organization_id: OrganizationId, counterparty_id: TypedId
    ) -> list[EstablishmentQualification]: ...


class QualificationSourceArtifactWriterPort(Protocol):
    def save(self, artifact: QualificationSourceArtifact) -> None: ...


class EstablishmentQualificationAssertionWriterPort(Protocol):
    def save(self, assertion: EstablishmentQualificationAssertion) -> None: ...


def _assertion_status_from_manual_status(
    status: EstablishmentQualificationStatus,
) -> AssertionStatus:
    if status is EstablishmentQualificationStatus.HABILITADO:
        return AssertionStatus.QUALIFIED
    return AssertionStatus.NOT_QUALIFIED


def _manual_content_hash(
    *,
    counterparty_id: TypedId,
    market_purpose: str,
    status: EstablishmentQualificationStatus,
    source_name: str,
    source_version: str,
    assessed_at: datetime,
) -> str:
    payload = {
        "counterparty_id": str(counterparty_id.value),
        "market_purpose": market_purpose,
        "status": status.value,
        "source_name": source_name,
        "source_version": source_version,
        "assessed_at": assessed_at.isoformat(),
    }
    material = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(material).hexdigest()}"


@dataclass(frozen=True, slots=True)
class EstablishmentQualificationService:
    repository: EstablishmentQualificationRepositoryPort
    counterparty_repository: ExternalCounterpartyRepositoryPort
    recorder: LivestockEventRecorder
    source_artifact_repository: QualificationSourceArtifactWriterPort | None = None
    assertion_repository: EstablishmentQualificationAssertionWriterPort | None = None

    def record_qualification(
        self,
        *,
        context: LivestockOperationContext,
        counterparty_id: TypedId,
        market_purpose: str,
        status: EstablishmentQualificationStatus,
        source_name: str,
        source_version: str | None,
        assessed_at: datetime,
        evidence_references: tuple[UniversalReference, ...] = (),
    ) -> EstablishmentQualification:
        counterparty = self.counterparty_repository.get_by_id(counterparty_id)
        if counterparty is None or counterparty.organization_id != context.organization_id:
            raise KeyError(f"Contraparte '{counterparty_id.value}' nao encontrada.")
        if counterparty.counterparty_type is not CounterpartyType.SLAUGHTERHOUSE:
            raise ValueError(
                "A qualificacao de estabelecimento exige contraparte do tipo SLAUGHTERHOUSE."
            )
        qualification = EstablishmentQualification.create(
            organization_id=context.organization_id,
            counterparty_id=counterparty_id,
            market_purpose=market_purpose,
            status=status,
            source_name=source_name,
            source_version=source_version,
            assessed_at=assessed_at,
            evidence_references=evidence_references,
        )
        self.repository.save(qualification)
        self._record_manual_assertion(
            context=context,
            qualification=qualification,
        )
        self.recorder.record(
            context=context,
            aggregate_id=qualification.qualification_id,
            event_type=ESTABLISHMENT_QUALIFICATION_RECORDED,
            payload=establishment_qualification_recorded_payload(
                qualification_id=qualification.qualification_id,
                counterparty_id=counterparty_id,
                market_purpose=qualification.market_purpose,
                status=qualification.status.value,
                source_name=qualification.source_name,
                source_version=qualification.source_version,
                assessed_at=qualification.assessed_at,
                evidence_references=qualification.evidence_references,
            ),
            occurred_at=qualification.recorded_at,
        )
        return qualification

    def list_for_counterparty(
        self, organization_id: OrganizationId, counterparty_id: TypedId
    ) -> list[EstablishmentQualification]:
        counterparty = self.counterparty_repository.get_by_id(counterparty_id)
        if counterparty is None or counterparty.organization_id != organization_id:
            raise KeyError(f"Contraparte '{counterparty_id.value}' nao encontrada.")
        return self.repository.list_by_counterparty(organization_id, counterparty_id)

    def _record_manual_assertion(
        self,
        *,
        context: LivestockOperationContext,
        qualification: EstablishmentQualification,
    ) -> None:
        if self.source_artifact_repository is None or self.assertion_repository is None:
            return

        declared_source_version = (
            qualification.source_version or qualification.assessed_at.isoformat()
        )
        artifact = QualificationSourceArtifact.create(
            organization_id=context.organization_id,
            source=qualification.source_name,
            source_version=qualification.qualification_id.value.hex,
            content_hash=_manual_content_hash(
                counterparty_id=qualification.counterparty_id,
                market_purpose=qualification.market_purpose,
                status=qualification.status,
                source_name=qualification.source_name,
                source_version=declared_source_version,
                assessed_at=qualification.assessed_at,
            ),
            snapshot_semantics=SourceCoverage.PARTIAL,
            observed_at=qualification.assessed_at,
        )
        self.source_artifact_repository.save(artifact)
        self.assertion_repository.save(
            EstablishmentQualificationAssertion.create(
                organization_id=context.organization_id,
                establishment_id=qualification.counterparty_id,
                qualification_type=qualification.market_purpose,
                asserted_status=_assertion_status_from_manual_status(qualification.status),
                effective_from=None,
                effective_until=None,
                observed_at=qualification.assessed_at,
                source_artifact_id=artifact.artifact_id,
                confidence_tier=ConfidenceTier.DOCUMENTED,
            )
        )
