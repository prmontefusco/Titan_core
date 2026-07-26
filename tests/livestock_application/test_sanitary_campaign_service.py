"""Testes unitarios para SanitaryCampaignService (Passo 14.2)."""

from datetime import UTC, datetime

import pytest

from packages.livestock_application.event_recorder import (
    LivestockEventRecorder,
    LivestockOperationContext,
)
from packages.livestock_application.sanitary_campaign_service import (
    SanitaryCampaignRepositoryPort,
    SanitaryCampaignService,
)
from packages.livestock_domain.events import SANITARY_CAMPAIGN_REGISTERED
from packages.livestock_domain.sanitary_campaign import SanitaryCampaign
from packages.shared_kernel import OrganizationId, TypedId
from tests.livestock_application.conftest import FakeEventLog


class InMemoryCampaignRepo(SanitaryCampaignRepositoryPort):
    def __init__(self) -> None:
        self.campaigns: dict[str, SanitaryCampaign] = {}

    def save(self, campaign: SanitaryCampaign) -> None:
        self.campaigns[campaign.campaign_id.value.hex] = campaign

    def get_by_id(self, campaign_id: TypedId) -> SanitaryCampaign | None:
        return self.campaigns.get(campaign_id.value.hex)

    def get_by_code(self, organization_id: OrganizationId, code: str) -> SanitaryCampaign | None:
        for campaign in self.campaigns.values():
            if campaign.organization_id == organization_id and campaign.code == code:
                return campaign
        return None

    def list_by_organization(
        self, organization_id: OrganizationId, limit: int = 50, offset: int = 0
    ) -> list[SanitaryCampaign]:
        return [
            campaign
            for campaign in self.campaigns.values()
            if campaign.organization_id == organization_id
        ][offset : offset + limit]


def test_register_campaign_records_event(
    recorder: LivestockEventRecorder,
    event_log: FakeEventLog,
    context: LivestockOperationContext,
) -> None:
    repo = InMemoryCampaignRepo()
    service = SanitaryCampaignService(campaign_repository=repo, recorder=recorder)

    campaign = service.register_campaign(
        context=context,
        code="PNCEBT-BRUCELOSE-2026",
        name="Campanha Brucelose 2026",
        starts_at=datetime(2026, 1, 1, tzinfo=UTC),
        ends_at=datetime(2026, 12, 31, tzinfo=UTC),
        disease="Brucelose",
        authority="MAPA",
    )

    event = event_log.only(SANITARY_CAMPAIGN_REGISTERED)
    assert repo.get_by_id(campaign.campaign_id) == campaign
    assert event.aggregate_reference.target_id == campaign.campaign_id
    assert b"PNCEBT-BRUCELOSE-2026" in event.payload.canonical_bytes


def test_register_campaign_rejects_duplicate_code(
    recorder: LivestockEventRecorder,
    context: LivestockOperationContext,
) -> None:
    repo = InMemoryCampaignRepo()
    service = SanitaryCampaignService(campaign_repository=repo, recorder=recorder)
    service.register_campaign(
        context=context,
        code="PNCEBT-BRUCELOSE-2026",
        name="Campanha Brucelose 2026",
        starts_at=datetime(2026, 1, 1, tzinfo=UTC),
        ends_at=datetime(2026, 12, 31, tzinfo=UTC),
    )
    with pytest.raises(ValueError, match="Ja existe"):
        service.register_campaign(
            context=context,
            code="PNCEBT-BRUCELOSE-2026",
            name="Campanha Brucelose 2026",
            starts_at=datetime(2026, 1, 1, tzinfo=UTC),
            ends_at=datetime(2026, 12, 31, tzinfo=UTC),
        )
