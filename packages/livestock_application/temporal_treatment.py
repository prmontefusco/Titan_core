"""Seleção temporal estrita de aplicações locais e suas correções."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from packages.core_application.event_log import CanonicalDomainEventReader, RecordedCanonicalEvent
from packages.livestock_application.event_recorder import AGGREGATE_CONTRACT_VERSION
from packages.livestock_application.treatment_service import TreatmentApplicationRepositoryPort
from packages.livestock_domain.events import TREATMENT_APPLIED
from packages.livestock_domain.treatment import TreatmentApplication
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference

TEMPORAL_TREATMENT_HISTORY_FACT_TYPE = "livestock.treatment_history.local"


class TemporalTreatmentLimitation(StrEnum):
    SOURCE_UNAVAILABLE = "LIVESTOCK_TREATMENT_HISTORY_SOURCE_UNAVAILABLE"
    ABSENT_AT_CONTEXT = "LIVESTOCK_TREATMENT_HISTORY_ABSENT_AT_CONTEXT"
    INVALID_EVENT = "LIVESTOCK_TREATMENT_HISTORY_INVALID_EVENT"
    CONFLICT = "LIVESTOCK_TREATMENT_HISTORY_CONFLICT"


@dataclass(frozen=True, slots=True)
class TemporalTreatmentApplication:
    application: TreatmentApplication
    event_id: TypedId
    payload_digest: str
    recorded_at: datetime


@dataclass(frozen=True, slots=True)
class TemporalTreatmentSelection:
    effective_applications: tuple[TemporalTreatmentApplication, ...]
    supporting_applications: tuple[TemporalTreatmentApplication, ...]
    limitation: TemporalTreatmentLimitation | None


@dataclass(frozen=True, slots=True)
class TemporalTreatmentApplicationReader:
    application_repository: TreatmentApplicationRepositoryPort
    event_reader: CanonicalDomainEventReader

    def select(
        self,
        organization_id: OrganizationId,
        animal_id: TypedId,
        *,
        reference_time: datetime,
        knowledge_cutoff: datetime,
    ) -> TemporalTreatmentSelection:
        candidates = [
            item
            for item in self.application_repository.list_by_animal(organization_id, animal_id)
            if item.organization_id == organization_id
            and item.animal_id == animal_id
            and item.applied_at <= reference_time
            and item.created_at <= knowledge_cutoff
        ]
        selected: list[TemporalTreatmentApplication] = []
        for application in candidates:
            event = self._event_for(
                organization_id,
                application,
                knowledge_cutoff=knowledge_cutoff,
            )
            if event is None:
                return _empty(TemporalTreatmentLimitation.INVALID_EVENT)
            selected.append(
                TemporalTreatmentApplication(
                    application=application,
                    event_id=event.event_id,
                    payload_digest=event.payload_digest,
                    recorded_at=event.recorded_at,
                )
            )
        if not selected:
            return _empty(TemporalTreatmentLimitation.ABSENT_AT_CONTEXT)

        by_id = {item.application.application_id: item for item in selected}
        corrected: set[TypedId] = set()
        for item in selected:
            original_id = item.application.corrects_application_id
            if original_id is None:
                continue
            if original_id not in by_id or original_id in corrected:
                return _empty(TemporalTreatmentLimitation.CONFLICT)
            corrected.add(original_id)

        effective = tuple(
            item for item in selected if item.application.application_id not in corrected
        )
        return TemporalTreatmentSelection(
            effective_applications=effective,
            supporting_applications=tuple(selected),
            limitation=None,
        )

    def _event_for(
        self,
        organization_id: OrganizationId,
        application: TreatmentApplication,
        *,
        knowledge_cutoff: datetime,
    ) -> RecordedCanonicalEvent | None:
        reference = UniversalReference(
            target_id=application.application_id,
            organization_id=organization_id,
            contract_version=AGGREGATE_CONTRACT_VERSION,
        )
        events = self.event_reader.list_canonical_for_aggregate(reference)
        matches = [
            event
            for event in events
            if event.event_type == TREATMENT_APPLIED
            and event.occurred_at == application.applied_at
            and event.recorded_at <= knowledge_cutoff
        ]
        return matches[0] if len(matches) == 1 else None


def _empty(limitation: TemporalTreatmentLimitation) -> TemporalTreatmentSelection:
    return TemporalTreatmentSelection((), (), limitation)
