"""T-05C1: aplicações e correções só existem no snapshot se já registradas."""

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime

from packages.livestock_application.event_recorder import AGGREGATE_CONTRACT_VERSION
from packages.livestock_application.temporal_treatment import (
    TemporalTreatmentApplicationReader,
    TemporalTreatmentLimitation,
)
from packages.livestock_domain.events import TREATMENT_APPLIED, treatment_applied_payload
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


class _EventReader:
    def __init__(self, events: list[_Event]) -> None:
        self.events = events

    def list_canonical_for_aggregate(
        self, aggregate_reference: UniversalReference
    ) -> tuple[_Event, ...]:
        return tuple(
            item for item in self.events if item.aggregate_reference == aggregate_reference
        )


def _application(
    *,
    organization_id: OrganizationId,
    animal_id: TypedId,
    application_id: TypedId | None = None,
    applied_at: datetime,
    created_at: datetime,
    corrects: TypedId | None = None,
) -> TreatmentApplication:
    return TreatmentApplication(
        application_id=application_id or TypedId.new("treatment_application"),
        organization_id=organization_id,
        animal_id=animal_id,
        medication_batch_id=TypedId.new("medication_batch"),
        actor_id=TypedId.new("actor"),
        applied_at=applied_at,
        corrects_application_id=corrects,
        created_at=created_at,
    )


def _event(organization_id: OrganizationId, application: TreatmentApplication) -> _Event:
    payload = treatment_applied_payload(
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
    )
    return _Event(
        event_id=TypedId.new("domain_event"),
        aggregate_reference=UniversalReference(
            target_id=application.application_id,
            organization_id=organization_id,
            contract_version=AGGREGATE_CONTRACT_VERSION,
        ),
        aggregate_version=1,
        event_type=TREATMENT_APPLIED,
        event_version=1,
        occurred_at=application.applied_at,
        recorded_at=application.created_at,
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


def _reader(
    applications: list[TreatmentApplication], events: list[_Event]
) -> TemporalTreatmentApplicationReader:
    return TemporalTreatmentApplicationReader(_ApplicationRepo(applications), _EventReader(events))


def test_retroactive_application_requires_registration_before_cutoff() -> None:
    organization_id = OrganizationId.new()
    animal_id = TypedId.new("animal")
    application = _application(
        organization_id=organization_id,
        animal_id=animal_id,
        applied_at=datetime(2026, 1, 1, tzinfo=UTC),
        created_at=datetime(2026, 1, 3, tzinfo=UTC),
    )
    reader = _reader([application], [_event(organization_id, application)])

    before = reader.select(
        organization_id,
        animal_id,
        reference_time=datetime(2026, 1, 2, tzinfo=UTC),
        knowledge_cutoff=datetime(2026, 1, 2, tzinfo=UTC),
    )
    after = reader.select(
        organization_id,
        animal_id,
        reference_time=datetime(2026, 1, 2, tzinfo=UTC),
        knowledge_cutoff=datetime(2026, 1, 3, tzinfo=UTC),
    )

    assert before.limitation is TemporalTreatmentLimitation.ABSENT_AT_CONTEXT
    assert [item.application.application_id for item in after.effective_applications] == [
        application.application_id
    ]


def test_correction_known_after_cutoff_does_not_suppress_original() -> None:
    organization_id = OrganizationId.new()
    animal_id = TypedId.new("animal")
    original = _application(
        organization_id=organization_id,
        animal_id=animal_id,
        applied_at=datetime(2026, 1, 1, tzinfo=UTC),
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    correction = _application(
        organization_id=organization_id,
        animal_id=animal_id,
        applied_at=datetime(2026, 1, 1, tzinfo=UTC),
        created_at=datetime(2026, 1, 3, tzinfo=UTC),
        corrects=original.application_id,
    )
    reader = _reader(
        [original, correction],
        [_event(organization_id, original), _event(organization_id, correction)],
    )

    before = reader.select(
        organization_id,
        animal_id,
        reference_time=datetime(2026, 1, 2, tzinfo=UTC),
        knowledge_cutoff=datetime(2026, 1, 2, tzinfo=UTC),
    )
    after = reader.select(
        organization_id,
        animal_id,
        reference_time=datetime(2026, 1, 3, tzinfo=UTC),
        knowledge_cutoff=datetime(2026, 1, 3, tzinfo=UTC),
    )

    assert [item.application.application_id for item in before.effective_applications] == [
        original.application_id
    ]
    assert [item.application.application_id for item in after.effective_applications] == [
        correction.application_id
    ]


def test_orphan_correction_fails_closed() -> None:
    organization_id = OrganizationId.new()
    animal_id = TypedId.new("animal")
    correction = _application(
        organization_id=organization_id,
        animal_id=animal_id,
        applied_at=datetime(2026, 1, 1, tzinfo=UTC),
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        corrects=TypedId.new("treatment_application"),
    )

    selection = _reader([correction], [_event(organization_id, correction)]).select(
        organization_id,
        animal_id,
        reference_time=datetime(2026, 1, 2, tzinfo=UTC),
        knowledge_cutoff=datetime(2026, 1, 2, tzinfo=UTC),
    )

    assert selection.limitation is TemporalTreatmentLimitation.CONFLICT


def test_application_after_reference_time_does_not_participate() -> None:
    organization_id = OrganizationId.new()
    animal_id = TypedId.new("animal")
    future = _application(
        organization_id=organization_id,
        animal_id=animal_id,
        applied_at=datetime(2026, 1, 4, tzinfo=UTC),
        created_at=datetime(2026, 1, 4, tzinfo=UTC),
    )

    selection = _reader([future], [_event(organization_id, future)]).select(
        organization_id,
        animal_id,
        reference_time=datetime(2026, 1, 3, tzinfo=UTC),
        knowledge_cutoff=datetime(2026, 1, 5, tzinfo=UTC),
    )

    assert selection.limitation is TemporalTreatmentLimitation.ABSENT_AT_CONTEXT
