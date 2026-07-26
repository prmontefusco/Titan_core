"""Servico de aplicacao para campanhas sanitarias oficiais (Passo 14.2)."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from packages.livestock_application.event_recorder import (
    LivestockEventRecorder,
    LivestockOperationContext,
)
from packages.livestock_domain.events import (
    SANITARY_CAMPAIGN_REGISTERED,
    sanitary_campaign_registered_payload,
)
from packages.livestock_domain.sanitary_campaign import SanitaryCampaign
from packages.shared_kernel import OrganizationId, TypedId


class SanitaryCampaignRepositoryPort(Protocol):
    def save(self, campaign: SanitaryCampaign) -> None: ...

    def get_by_id(self, campaign_id: TypedId) -> SanitaryCampaign | None: ...

    def get_by_code(
        self, organization_id: OrganizationId, code: str
    ) -> SanitaryCampaign | None: ...

    def list_by_organization(
        self, organization_id: OrganizationId, limit: int = 50, offset: int = 0
    ) -> list[SanitaryCampaign]: ...


@dataclass(frozen=True, slots=True)
class SanitaryCampaignService:
    campaign_repository: SanitaryCampaignRepositoryPort
    recorder: LivestockEventRecorder

    def register_campaign(
        self,
        context: LivestockOperationContext,
        code: str,
        name: str,
        starts_at: datetime,
        ends_at: datetime,
        disease: str | None = None,
        authority: str | None = None,
    ) -> SanitaryCampaign:
        organization_id = context.organization_id
        normalized_code = code.strip()
        if self.campaign_repository.get_by_code(organization_id, normalized_code) is not None:
            raise ValueError(
                f"Ja existe campanha sanitaria com codigo '{normalized_code}' para a "
                f"organizacao {organization_id.value}."
            )

        created_at = datetime.now(UTC)
        campaign = SanitaryCampaign(
            campaign_id=TypedId.new("sanitary_campaign"),
            organization_id=organization_id,
            code=normalized_code,
            name=name.strip(),
            starts_at=starts_at,
            ends_at=ends_at,
            disease=disease.strip() if disease is not None else None,
            authority=authority.strip() if authority is not None else None,
            created_at=created_at,
        )
        self.campaign_repository.save(campaign)
        self.recorder.record(
            context=context,
            aggregate_id=campaign.campaign_id,
            event_type=SANITARY_CAMPAIGN_REGISTERED,
            payload=sanitary_campaign_registered_payload(
                campaign_id=campaign.campaign_id,
                code=campaign.code,
                name=campaign.name,
                starts_at=campaign.starts_at,
                ends_at=campaign.ends_at,
                disease=campaign.disease,
                authority=campaign.authority,
            ),
            occurred_at=created_at,
        )
        return campaign
