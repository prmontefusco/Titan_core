"""Registro append-only da qualificacao de estabelecimento por mercado."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

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
from packages.livestock_domain.events import (
    ESTABLISHMENT_QUALIFICATION_RECORDED,
    establishment_qualification_recorded_payload,
)
from packages.livestock_domain.external_counterparty import CounterpartyType
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference


def establishment_qualification_fact_type(market_purpose: str) -> str:
    sufixo = market_purpose.strip().lower().replace(".", "_")
    return f"livestock.establishment_qualification.{sufixo}"


class EstablishmentQualificationRepositoryPort(Protocol):
    def save(self, qualification: EstablishmentQualification) -> None: ...

    def list_by_counterparty(
        self, organization_id: OrganizationId, counterparty_id: TypedId
    ) -> list[EstablishmentQualification]: ...


@dataclass(frozen=True, slots=True)
class EstablishmentQualificationService:
    repository: EstablishmentQualificationRepositoryPort
    counterparty_repository: ExternalCounterpartyRepositoryPort
    recorder: LivestockEventRecorder

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
