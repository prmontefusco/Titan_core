"""Leitura temporal limitada de campanhas sanitárias imutáveis."""

from dataclasses import dataclass
from datetime import datetime

from packages.core_application.event_log import CanonicalDomainEventReader, RecordedCanonicalEvent
from packages.livestock_application.event_recorder import AGGREGATE_CONTRACT_VERSION
from packages.livestock_application.sanitary_campaign_service import (
    SanitaryCampaignRepositoryPort,
)
from packages.livestock_domain.events import (
    SANITARY_CAMPAIGN_REGISTERED,
    sanitary_campaign_registered_payload,
)
from packages.livestock_domain.sanitary_campaign import SanitaryCampaign
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference


@dataclass(frozen=True, slots=True)
class TemporalSanitaryCampaign:
    campaign: SanitaryCampaign
    event_id: TypedId
    payload_digest: str
    recorded_at: datetime


@dataclass(frozen=True, slots=True)
class TemporalSanitaryCampaignReader:
    campaign_repository: SanitaryCampaignRepositoryPort
    event_reader: CanonicalDomainEventReader

    def list_applicable(
        self,
        organization_id: OrganizationId,
        *,
        reference_time: datetime,
        knowledge_cutoff: datetime,
    ) -> tuple[TemporalSanitaryCampaign, ...]:
        """Retorna somente campanhas já iniciadas e comprovadas no corte.

        Sem eventos de correção/revogação, esta leitura não tenta reconstruir
        mudanças posteriores: um registro que não coincide com seu evento é
        simplesmente inelegível como fonte histórica.
        """
        selected: list[TemporalSanitaryCampaign] = []
        for campaign in self.campaign_repository.list_by_organization(organization_id, limit=1000):
            if (
                campaign.organization_id != organization_id
                or campaign.starts_at > reference_time
                or campaign.created_at > knowledge_cutoff
            ):
                continue
            event = self._matching_event(
                organization_id, campaign, knowledge_cutoff=knowledge_cutoff
            )
            if event is None:
                continue
            selected.append(
                TemporalSanitaryCampaign(
                    campaign=campaign,
                    event_id=event.event_id,
                    payload_digest=event.payload_digest,
                    recorded_at=max(campaign.created_at, event.recorded_at),
                )
            )
        return tuple(
            sorted(
                selected,
                key=lambda item: (item.campaign.code, item.campaign.campaign_id.value.hex),
            )
        )

    def _matching_event(
        self,
        organization_id: OrganizationId,
        campaign: SanitaryCampaign,
        *,
        knowledge_cutoff: datetime,
    ) -> RecordedCanonicalEvent | None:
        expected = sanitary_campaign_registered_payload(
            campaign_id=campaign.campaign_id,
            code=campaign.code,
            name=campaign.name,
            starts_at=campaign.starts_at,
            ends_at=campaign.ends_at,
            disease=campaign.disease,
            authority=campaign.authority,
        )
        reference = UniversalReference(
            target_id=campaign.campaign_id,
            organization_id=organization_id,
            contract_version=AGGREGATE_CONTRACT_VERSION,
        )
        matches = [
            event
            for event in self.event_reader.list_canonical_for_aggregate(reference)
            if event.event_type == SANITARY_CAMPAIGN_REGISTERED
            and event.occurred_at == campaign.created_at
            and event.recorded_at <= knowledge_cutoff
            and event.payload_schema == expected.schema
            and event.payload_version == expected.version
            and event.payload_canonical_bytes == expected.canonical_bytes
        ]
        return matches[0] if len(matches) == 1 else None
