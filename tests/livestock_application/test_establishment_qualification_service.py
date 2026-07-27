from datetime import UTC, datetime

import pytest

from packages.livestock_application.establishment_qualification_service import (
    EstablishmentQualificationRepositoryPort,
    EstablishmentQualificationService,
)
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
from packages.livestock_domain.events import ESTABLISHMENT_QUALIFICATION_RECORDED
from packages.livestock_domain.external_counterparty import CounterpartyType, ExternalCounterparty
from packages.shared_kernel import FixedClock, OrganizationId, TypedId
from tests.livestock_application.conftest import RECORDED_AT, FakeEventLog
from tests.livestock_support import operation_context


class InMemoryQualificationRepo(EstablishmentQualificationRepositoryPort):
    def __init__(self) -> None:
        self.items: list[EstablishmentQualification] = []

    def save(self, qualification: EstablishmentQualification) -> None:
        self.items.append(qualification)

    def list_by_counterparty(
        self, organization_id: OrganizationId, counterparty_id: TypedId
    ) -> list[EstablishmentQualification]:
        return [
            item
            for item in self.items
            if item.organization_id == organization_id and item.counterparty_id == counterparty_id
        ]


class InMemoryCounterpartyRepo(ExternalCounterpartyRepositoryPort):
    def __init__(self, counterparty: ExternalCounterparty) -> None:
        self.counterparty = counterparty

    def save(self, counterparty: ExternalCounterparty) -> None:
        self.counterparty = counterparty

    def get_by_id(self, counterparty_id: TypedId) -> ExternalCounterparty | None:
        if self.counterparty.counterparty_id == counterparty_id:
            return self.counterparty
        return None

    def list_by_organization(self, organization_id: OrganizationId) -> list[ExternalCounterparty]:
        if self.counterparty.organization_id == organization_id:
            return [self.counterparty]
        return []


def _context(org_id: OrganizationId) -> LivestockOperationContext:
    return operation_context(org_id)


def test_registra_qualificacao_de_estabelecimento_com_evento() -> None:
    org_id = OrganizationId.new()
    counterparty = ExternalCounterparty(
        counterparty_id=TypedId.new("external_counterparty"),
        organization_id=org_id,
        name="Frigorifico Teste",
        counterparty_type=CounterpartyType.SLAUGHTERHOUSE,
        identifiers=("SIF:1234",),
    )
    event_log = FakeEventLog()
    recorder = LivestockEventRecorder(event_log=event_log, clock=FixedClock(RECORDED_AT))
    repository = InMemoryQualificationRepo()
    service = EstablishmentQualificationService(
        repository=repository,
        counterparty_repository=InMemoryCounterpartyRepo(counterparty),
        recorder=recorder,
    )

    qualification = service.record_qualification(
        context=_context(org_id),
        counterparty_id=counterparty.counterparty_id,
        market_purpose="exportacao-china",
        status=EstablishmentQualificationStatus.HABILITADO,
        source_name="lista-sif",
        source_version="2026-07",
        assessed_at=datetime.now(UTC),
    )

    assert qualification.status is EstablishmentQualificationStatus.HABILITADO
    assert repository.items == [qualification]
    assert event_log.only(ESTABLISHMENT_QUALIFICATION_RECORDED).aggregate_reference.target_id == (
        qualification.qualification_id
    )


def test_recusa_qualificacao_para_contraparte_que_nao_e_frigorifico() -> None:
    org_id = OrganizationId.new()
    counterparty = ExternalCounterparty(
        counterparty_id=TypedId.new("external_counterparty"),
        organization_id=org_id,
        name="Fazenda Teste",
        counterparty_type=CounterpartyType.FARM,
    )
    service = EstablishmentQualificationService(
        repository=InMemoryQualificationRepo(),
        counterparty_repository=InMemoryCounterpartyRepo(counterparty),
        recorder=LivestockEventRecorder(
            event_log=FakeEventLog(),
            clock=FixedClock(RECORDED_AT),
        ),
    )

    with pytest.raises(ValueError, match="SLAUGHTERHOUSE"):
        service.record_qualification(
            context=_context(org_id),
            counterparty_id=counterparty.counterparty_id,
            market_purpose="exportacao-china",
            status=EstablishmentQualificationStatus.HABILITADO,
            source_name="lista-sif",
            source_version=None,
            assessed_at=datetime.now(UTC),
        )
