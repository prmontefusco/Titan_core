"""Cadastro local de contraparte externa da vertical Livestock (ADR-0042)."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from packages.livestock_application.event_recorder import (
    LivestockEventRecorder,
    LivestockOperationContext,
)
from packages.livestock_domain.events import (
    EXTERNAL_COUNTERPARTY_REGISTERED,
    external_counterparty_registered_payload,
)
from packages.livestock_domain.external_counterparty import (
    CounterpartyType,
    ExternalCounterparty,
)
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference


class ExternalCounterpartyRepositoryPort(Protocol):
    def save(self, counterparty: ExternalCounterparty) -> None: ...

    def get_by_id(self, counterparty_id: TypedId) -> ExternalCounterparty | None: ...

    def list_by_organization(
        self, organization_id: OrganizationId
    ) -> list[ExternalCounterparty]: ...


@dataclass(frozen=True, slots=True)
class ExternalCounterpartyService:
    repository: ExternalCounterpartyRepositoryPort
    recorder: LivestockEventRecorder

    def register_counterparty(
        self,
        context: LivestockOperationContext,
        name: str,
        counterparty_type: CounterpartyType,
        identifiers: tuple[str, ...] = (),
        notes: str | None = None,
        evidence_references: tuple[UniversalReference, ...] = (),
    ) -> ExternalCounterparty:
        counterparty = ExternalCounterparty(
            counterparty_id=TypedId.new("external_counterparty"),
            organization_id=context.organization_id,
            name=name,
            counterparty_type=counterparty_type,
            identifiers=identifiers,
            notes=notes,
            evidence_references=evidence_references,
            created_at=datetime.now(UTC),
        )
        self.repository.save(counterparty)
        self.recorder.record(
            context=context,
            aggregate_id=counterparty.counterparty_id,
            event_type=EXTERNAL_COUNTERPARTY_REGISTERED,
            payload=external_counterparty_registered_payload(
                counterparty_id=counterparty.counterparty_id,
                name=counterparty.name,
                counterparty_type=counterparty.counterparty_type.value,
                identifiers=counterparty.identifiers,
                notes=counterparty.notes,
                evidence_references=counterparty.evidence_references,
            ),
            occurred_at=counterparty.created_at,
        )
        return counterparty

    def get_counterparty(
        self, organization_id: OrganizationId, counterparty_id: TypedId
    ) -> ExternalCounterparty | None:
        counterparty = self.repository.get_by_id(counterparty_id)
        if counterparty is None or counterparty.organization_id != organization_id:
            return None
        return counterparty

    def list_counterparties(self, organization_id: OrganizationId) -> list[ExternalCounterparty]:
        return self.repository.list_by_organization(organization_id)
