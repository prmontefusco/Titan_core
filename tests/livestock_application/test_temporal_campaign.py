"""T-05C3: campanhas sanitarias so contribuem com base temporal comprovada."""

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime

from packages.core_domain.events import CanonicalPayload
from packages.livestock_application.event_recorder import AGGREGATE_CONTRACT_VERSION
from packages.livestock_application.fact_provider import (
    LivestockFactProvider,
    sanitary_requirement_fact_type,
)
from packages.livestock_application.temporal_campaign import TemporalSanitaryCampaignReader
from packages.livestock_application.temporal_treatment import TemporalTreatmentApplicationReader
from packages.livestock_domain.events import (
    SANITARY_CAMPAIGN_REGISTERED,
    TREATMENT_APPLIED,
    sanitary_campaign_registered_payload,
    treatment_applied_payload,
)
from packages.livestock_domain.sanitary_campaign import SanitaryCampaign
from packages.livestock_domain.treatment import TreatmentApplication
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference


@dataclass(frozen=True, slots=True)
class _Event:
    event_id: TypedId
    aggregate_reference: UniversalReference
    aggregate_version: int
    event_type: str
    event_version: int
    occurred_at: datetime
    recorded_at: datetime
    actor_reference: UniversalReference
    correlation_id: TypedId
    causation_id: TypedId | None
    payload_schema: str
    payload_version: int
    payload_canonical_bytes: bytes
    payload_digest: str
    integrity_hash: bytes | None = None


class _EventReader:
    def __init__(self, events: list[_Event]) -> None:
        self.events = events

    def list_canonical_for_aggregate(
        self, aggregate_reference: UniversalReference
    ) -> tuple[_Event, ...]:
        return tuple(
            item for item in self.events if item.aggregate_reference == aggregate_reference
        )


class _CampaignRepo:
    def __init__(self, campaigns: list[SanitaryCampaign]) -> None:
        self.campaigns = campaigns

    def save(self, campaign: SanitaryCampaign) -> None: ...

    def get_by_id(self, campaign_id: TypedId) -> SanitaryCampaign | None:
        return next((item for item in self.campaigns if item.campaign_id == campaign_id), None)

    def get_by_code(self, organization_id: OrganizationId, code: str) -> SanitaryCampaign | None:
        return next(
            (
                item
                for item in self.campaigns
                if item.organization_id == organization_id and item.code == code
            ),
            None,
        )

    def list_by_organization(
        self, organization_id: OrganizationId, limit: int = 50, offset: int = 0
    ) -> list[SanitaryCampaign]:
        return [item for item in self.campaigns if item.organization_id == organization_id][
            offset : offset + limit
        ]


class _ApplicationRepo:
    def __init__(self, applications: list[TreatmentApplication]) -> None:
        self.applications = applications

    def save(self, application: TreatmentApplication) -> None: ...

    def get_by_id(self, application_id: TypedId) -> TreatmentApplication | None:
        return next(
            (item for item in self.applications if item.application_id == application_id), None
        )

    def list_by_animal(
        self, organization_id: OrganizationId, animal_id: TypedId
    ) -> list[TreatmentApplication]:
        return [
            item
            for item in self.applications
            if item.organization_id == organization_id and item.animal_id == animal_id
        ]

    def list_by_batch(
        self, organization_id: OrganizationId, medication_batch_id: TypedId
    ) -> list[TreatmentApplication]:
        return []


def _event(
    organization_id: OrganizationId,
    aggregate_id: TypedId,
    event_type: str,
    occurred_at: datetime,
    recorded_at: datetime,
    payload: CanonicalPayload,
) -> _Event:
    return _Event(
        event_id=TypedId.new("domain_event"),
        aggregate_reference=UniversalReference(
            target_id=aggregate_id,
            organization_id=organization_id,
            contract_version=AGGREGATE_CONTRACT_VERSION,
        ),
        aggregate_version=1,
        event_type=event_type,
        event_version=1,
        occurred_at=occurred_at,
        recorded_at=recorded_at,
        actor_reference=UniversalReference(
            target_id=TypedId.new("actor"), organization_id=organization_id, contract_version=1
        ),
        correlation_id=TypedId.new("correlation"),
        causation_id=None,
        payload_schema=payload.schema,
        payload_version=payload.version,
        payload_canonical_bytes=payload.canonical_bytes,
        payload_digest=hashlib.sha256(payload.canonical_bytes).hexdigest(),
    )


def _campaign(
    organization_id: OrganizationId,
    *,
    starts_at: datetime = datetime(2026, 1, 1, tzinfo=UTC),
    ends_at: datetime = datetime(2026, 2, 1, tzinfo=UTC),
    created_at: datetime = datetime(2025, 12, 20, tzinfo=UTC),
) -> SanitaryCampaign:
    return SanitaryCampaign(
        campaign_id=TypedId.new("sanitary_campaign"),
        organization_id=organization_id,
        code="BRUCELOSE-2026",
        name="Campanha Brucelose 2026",
        starts_at=starts_at,
        ends_at=ends_at,
        disease="brucelose",
        authority="TITAN_TEST",
        created_at=created_at,
    )


def _campaign_event(
    organization_id: OrganizationId,
    campaign: SanitaryCampaign,
    *,
    recorded_at: datetime | None = None,
) -> _Event:
    return _event(
        organization_id,
        campaign.campaign_id,
        SANITARY_CAMPAIGN_REGISTERED,
        campaign.created_at,
        recorded_at or campaign.created_at,
        sanitary_campaign_registered_payload(
            campaign_id=campaign.campaign_id,
            code=campaign.code,
            name=campaign.name,
            starts_at=campaign.starts_at,
            ends_at=campaign.ends_at,
            disease=campaign.disease,
            authority=campaign.authority,
        ),
    )


def _application(
    organization_id: OrganizationId,
    animal_id: TypedId,
    campaign_id: TypedId,
    *,
    applied_at: datetime,
    created_at: datetime | None = None,
) -> TreatmentApplication:
    return TreatmentApplication(
        application_id=TypedId.new("treatment_application"),
        organization_id=organization_id,
        animal_id=animal_id,
        medication_batch_id=TypedId.new("medication_batch"),
        actor_id=TypedId.new("actor"),
        applied_at=applied_at,
        sanitary_campaign_id=campaign_id,
        created_at=created_at or applied_at,
    )


def _application_event(
    organization_id: OrganizationId, application: TreatmentApplication
) -> _Event:
    return _event(
        organization_id,
        application.application_id,
        TREATMENT_APPLIED,
        application.applied_at,
        application.created_at,
        treatment_applied_payload(
            application_id=application.application_id,
            animal_id=application.animal_id,
            medication_batch_id=application.medication_batch_id,
            applied_at=application.applied_at,
            dose=application.dose,
            prescription_id=application.prescription_id,
            sanitary_campaign_id=application.sanitary_campaign_id,
            evidence_references=application.evidence_references,
            evidence_notes=application.evidence_notes,
            corrects_application_id=application.corrects_application_id,
        ),
    )


def test_campaign_registered_after_cutoff_is_not_historical_source() -> None:
    organization_id = OrganizationId.new()
    campaign = _campaign(
        organization_id,
        created_at=datetime(2026, 1, 3, tzinfo=UTC),
    )
    reader = TemporalSanitaryCampaignReader(
        campaign_repository=_CampaignRepo([campaign]),
        event_reader=_EventReader([_campaign_event(organization_id, campaign)]),
    )

    selected = reader.list_applicable(
        organization_id,
        reference_time=datetime(2026, 1, 10, tzinfo=UTC),
        knowledge_cutoff=datetime(2026, 1, 2, tzinfo=UTC),
    )

    assert selected == ()


def test_campaign_payload_divergence_fails_closed() -> None:
    organization_id = OrganizationId.new()
    campaign = _campaign(organization_id)
    changed_campaign = SanitaryCampaign(
        campaign_id=campaign.campaign_id,
        organization_id=campaign.organization_id,
        code=campaign.code,
        name="Nome alterado sem evento",
        starts_at=campaign.starts_at,
        ends_at=campaign.ends_at,
        disease=campaign.disease,
        authority=campaign.authority,
        created_at=campaign.created_at,
    )
    reader = TemporalSanitaryCampaignReader(
        campaign_repository=_CampaignRepo([changed_campaign]),
        event_reader=_EventReader([_campaign_event(organization_id, campaign)]),
    )

    selected = reader.list_applicable(
        organization_id,
        reference_time=datetime(2026, 1, 10, tzinfo=UTC),
        knowledge_cutoff=datetime(2026, 1, 10, tzinfo=UTC),
    )

    assert selected == ()


def test_temporal_snapshot_marks_campaign_satisfied_with_source_ids() -> None:
    organization_id = OrganizationId.new()
    animal_id = TypedId.new("animal")
    campaign = _campaign(organization_id)
    application = _application(
        organization_id,
        animal_id,
        campaign.campaign_id,
        applied_at=datetime(2026, 1, 15, tzinfo=UTC),
    )
    events = [
        _campaign_event(organization_id, campaign),
        _application_event(organization_id, application),
    ]
    provider = LivestockFactProvider(
        property_repository=None,  # type: ignore[arg-type]
        animal_repository=None,  # type: ignore[arg-type]
        temporal_treatment_reader=TemporalTreatmentApplicationReader(
            _ApplicationRepo([application]), _EventReader(events)
        ),
        temporal_campaign_reader=TemporalSanitaryCampaignReader(
            campaign_repository=_CampaignRepo([campaign]),
            event_reader=_EventReader(events),
        ),
    )

    snapshot = provider.get_snapshot_with_temporal_context(
        organization_id,
        animal_id,
        reference_time=datetime(2026, 1, 20, tzinfo=UTC),
        knowledge_cutoff=datetime(2026, 1, 20, tzinfo=UTC),
    )

    fact = next(
        item
        for item in snapshot.facts
        if item.fact_type == sanitary_requirement_fact_type(campaign.code)
    )
    assert fact.payload["status"] == "ATENDIDA"
    assert fact.payload["campaign_event_id"]
    assert fact.payload["campaign_payload_digest"]
    assert fact.payload["application_id"] == application.application_id.value.hex
    assert fact.payload["application_event_id"]
    assert fact.payload["application_payload_digest"]


def test_campaign_application_uses_semi_open_interval() -> None:
    organization_id = OrganizationId.new()
    animal_id = TypedId.new("animal")
    campaign = _campaign(organization_id)
    application = _application(
        organization_id,
        animal_id,
        campaign.campaign_id,
        applied_at=campaign.ends_at,
    )
    events = [
        _campaign_event(organization_id, campaign),
        _application_event(organization_id, application),
    ]
    provider = LivestockFactProvider(
        property_repository=None,  # type: ignore[arg-type]
        animal_repository=None,  # type: ignore[arg-type]
        temporal_treatment_reader=TemporalTreatmentApplicationReader(
            _ApplicationRepo([application]), _EventReader(events)
        ),
        temporal_campaign_reader=TemporalSanitaryCampaignReader(
            campaign_repository=_CampaignRepo([campaign]),
            event_reader=_EventReader(events),
        ),
    )

    snapshot = provider.get_snapshot_with_temporal_context(
        organization_id,
        animal_id,
        reference_time=campaign.ends_at,
        knowledge_cutoff=campaign.ends_at,
    )

    fact = next(
        item
        for item in snapshot.facts
        if item.fact_type == sanitary_requirement_fact_type(campaign.code)
    )
    assert fact.payload["status"] == "INDETERMINADA"
    assert fact.payload["application_id"] is None
