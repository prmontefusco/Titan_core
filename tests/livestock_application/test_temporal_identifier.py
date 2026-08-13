"""Contrato temporal T-05B: lifecycle de identificador por eventos preservados."""

from dataclasses import dataclass
from datetime import UTC, datetime

from packages.core_domain.events import CanonicalPayload
from packages.livestock_application.event_recorder import AGGREGATE_CONTRACT_VERSION
from packages.livestock_application.temporal_identifier import (
    TemporalAnimalIdentifierReader,
    TemporalIdentifierLimitation,
)
from packages.livestock_domain.animal import IdentifierType
from packages.livestock_domain.events import (
    IDENTIFIER_ATTACHED,
    IDENTIFIER_DEACTIVATED,
    identifier_attached_payload,
    identifier_deactivated_payload,
)
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference


@dataclass(frozen=True, slots=True)
class _CanonicalEvent:
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


class _Reader:
    def __init__(self, events: list[_CanonicalEvent]) -> None:
        self.events = events

    def list_canonical_for_aggregate(
        self, aggregate_reference: UniversalReference
    ) -> tuple[_CanonicalEvent, ...]:
        return tuple(
            item for item in self.events if item.aggregate_reference == aggregate_reference
        )


def _reference(organization_id: OrganizationId, animal_id: TypedId) -> UniversalReference:
    return UniversalReference(
        target_id=animal_id,
        organization_id=organization_id,
        contract_version=AGGREGATE_CONTRACT_VERSION,
    )


def _event(
    *,
    organization_id: OrganizationId,
    animal_id: TypedId,
    version: int,
    event_type: str,
    occurred_at: datetime,
    recorded_at: datetime,
    payload: CanonicalPayload,
) -> _CanonicalEvent:
    import hashlib

    return _CanonicalEvent(
        event_id=TypedId.new("domain_event"),
        aggregate_reference=_reference(organization_id, animal_id),
        aggregate_version=version,
        event_type=event_type,
        event_version=1,
        occurred_at=occurred_at,
        recorded_at=recorded_at,
        actor_reference=UniversalReference(
            target_id=TypedId.new("actor"),
            organization_id=organization_id,
            contract_version=1,
        ),
        correlation_id=TypedId.new("correlation"),
        causation_id=None,
        payload_schema=payload.schema,
        payload_version=payload.version,
        payload_canonical_bytes=payload.canonical_bytes,
        payload_digest=hashlib.sha256(payload.canonical_bytes).hexdigest(),
    )


def _attachment(
    *,
    organization_id: OrganizationId,
    animal_id: TypedId,
    identifier_id: TypedId,
    version: int,
    occurred_at: datetime,
    recorded_at: datetime,
) -> _CanonicalEvent:
    return _event(
        organization_id=organization_id,
        animal_id=animal_id,
        version=version,
        event_type=IDENTIFIER_ATTACHED,
        occurred_at=occurred_at,
        recorded_at=recorded_at,
        payload=identifier_attached_payload(
            animal_id=animal_id,
            identifier_id=identifier_id,
            identifier_type=IdentifierType.OFFICIAL_SISBOV.value,
            identifier_value="BR-001",
            attached_at=occurred_at,
        ),
    )


def _deactivation(
    *,
    organization_id: OrganizationId,
    animal_id: TypedId,
    identifier_id: TypedId,
    version: int,
    occurred_at: datetime,
    recorded_at: datetime,
) -> _CanonicalEvent:
    return _event(
        organization_id=organization_id,
        animal_id=animal_id,
        version=version,
        event_type=IDENTIFIER_DEACTIVATED,
        occurred_at=occurred_at,
        recorded_at=recorded_at,
        payload=identifier_deactivated_payload(
            animal_id=animal_id,
            identifier_id=identifier_id,
            deactivated_at=occurred_at,
        ),
    )


def test_selects_identifier_only_when_event_was_known_by_cutoff() -> None:
    organization_id = OrganizationId.new()
    animal_id = TypedId.new("animal")
    identifier_id = TypedId.new("animal_identifier")
    event = _attachment(
        organization_id=organization_id,
        animal_id=animal_id,
        identifier_id=identifier_id,
        version=1,
        occurred_at=datetime(2026, 1, 1, tzinfo=UTC),
        recorded_at=datetime(2026, 1, 3, tzinfo=UTC),
    )
    reader = TemporalAnimalIdentifierReader(_Reader([event]))

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

    assert before.limitation is TemporalIdentifierLimitation.ABSENT_AT_CONTEXT
    assert after.limitation is None
    assert after.identifiers[0].identifier_id == identifier_id
    assert after.supporting_event_ids == (event.event_id,)
    assert after.recorded_at == event.recorded_at


def test_deactivation_after_cutoff_does_not_rewrite_prior_snapshot() -> None:
    organization_id = OrganizationId.new()
    animal_id = TypedId.new("animal")
    identifier_id = TypedId.new("animal_identifier")
    attached = _attachment(
        organization_id=organization_id,
        animal_id=animal_id,
        identifier_id=identifier_id,
        version=1,
        occurred_at=datetime(2026, 1, 1, tzinfo=UTC),
        recorded_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    deactivated = _deactivation(
        organization_id=organization_id,
        animal_id=animal_id,
        identifier_id=identifier_id,
        version=2,
        occurred_at=datetime(2026, 1, 4, tzinfo=UTC),
        recorded_at=datetime(2026, 1, 4, tzinfo=UTC),
    )
    reader = TemporalAnimalIdentifierReader(_Reader([attached, deactivated]))

    before = reader.select(
        organization_id,
        animal_id,
        reference_time=datetime(2026, 1, 3, tzinfo=UTC),
        knowledge_cutoff=datetime(2026, 1, 3, tzinfo=UTC),
    )
    after = reader.select(
        organization_id,
        animal_id,
        reference_time=datetime(2026, 1, 5, tzinfo=UTC),
        knowledge_cutoff=datetime(2026, 1, 5, tzinfo=UTC),
    )

    assert [item.identifier_id for item in before.identifiers] == [identifier_id]
    assert after.identifiers == ()
    assert after.limitation is None


def test_refuses_deactivation_without_eligible_attachment() -> None:
    organization_id = OrganizationId.new()
    animal_id = TypedId.new("animal")
    event = _deactivation(
        organization_id=organization_id,
        animal_id=animal_id,
        identifier_id=TypedId.new("animal_identifier"),
        version=1,
        occurred_at=datetime(2026, 1, 2, tzinfo=UTC),
        recorded_at=datetime(2026, 1, 2, tzinfo=UTC),
    )

    selection = TemporalAnimalIdentifierReader(_Reader([event])).select(
        organization_id,
        animal_id,
        reference_time=datetime(2026, 1, 3, tzinfo=UTC),
        knowledge_cutoff=datetime(2026, 1, 3, tzinfo=UTC),
    )

    assert selection.limitation is TemporalIdentifierLimitation.CONFLICT


def test_refuses_two_active_identifiers_of_the_same_type() -> None:
    organization_id = OrganizationId.new()
    animal_id = TypedId.new("animal")
    first = _attachment(
        organization_id=organization_id,
        animal_id=animal_id,
        identifier_id=TypedId.new("animal_identifier"),
        version=1,
        occurred_at=datetime(2026, 1, 1, tzinfo=UTC),
        recorded_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    second = _attachment(
        organization_id=organization_id,
        animal_id=animal_id,
        identifier_id=TypedId.new("animal_identifier"),
        version=2,
        occurred_at=datetime(2026, 1, 2, tzinfo=UTC),
        recorded_at=datetime(2026, 1, 2, tzinfo=UTC),
    )

    selection = TemporalAnimalIdentifierReader(_Reader([first, second])).select(
        organization_id,
        animal_id,
        reference_time=datetime(2026, 1, 3, tzinfo=UTC),
        knowledge_cutoff=datetime(2026, 1, 3, tzinfo=UTC),
    )

    assert selection.limitation is TemporalIdentifierLimitation.CONFLICT


def test_refuses_unknown_payload_version_without_using_current_projection() -> None:
    organization_id = OrganizationId.new()
    animal_id = TypedId.new("animal")
    event = _attachment(
        organization_id=organization_id,
        animal_id=animal_id,
        identifier_id=TypedId.new("animal_identifier"),
        version=1,
        occurred_at=datetime(2026, 1, 1, tzinfo=UTC),
        recorded_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    unknown_version = _CanonicalEvent(
        event_id=event.event_id,
        aggregate_reference=event.aggregate_reference,
        aggregate_version=event.aggregate_version,
        event_type=event.event_type,
        event_version=event.event_version,
        occurred_at=event.occurred_at,
        recorded_at=event.recorded_at,
        actor_reference=event.actor_reference,
        correlation_id=event.correlation_id,
        causation_id=event.causation_id,
        payload_schema=event.payload_schema,
        payload_version=2,
        payload_canonical_bytes=event.payload_canonical_bytes,
        payload_digest=event.payload_digest,
    )

    selection = TemporalAnimalIdentifierReader(_Reader([unknown_version])).select(
        organization_id,
        animal_id,
        reference_time=datetime(2026, 1, 2, tzinfo=UTC),
        knowledge_cutoff=datetime(2026, 1, 2, tzinfo=UTC),
    )

    assert selection.identifiers == ()
    assert selection.limitation is TemporalIdentifierLimitation.INVALID_EVENT
