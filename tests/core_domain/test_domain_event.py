from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from packages.core_domain import CanonicalPayload, DomainEvent
from packages.shared_kernel import OrganizationId, RecordTimestamps, TypedId, UniversalReference


def reference(entity_type: str, organization_id: OrganizationId) -> UniversalReference:
    return UniversalReference(
        target_id=TypedId.new(entity_type),
        organization_id=organization_id,
        contract_version=1,
    )


def valid_event() -> DomainEvent:
    organization_id = OrganizationId.new()
    return DomainEvent(
        event_id=TypedId.new("domain_event"),
        organization_id=organization_id,
        aggregate_reference=reference("aggregate", organization_id),
        aggregate_version=3,
        event_type="record_registered",
        event_version=1,
        timestamps=RecordTimestamps(
            occurred_at=datetime(2026, 7, 20, 14, 0, tzinfo=UTC),
            recorded_at=datetime(2026, 7, 21, 10, 0, tzinfo=UTC),
        ),
        actor_reference=reference("actor", organization_id),
        source_reference=reference("source", organization_id),
        correlation_id=TypedId.new("correlation"),
        causation_id=None,
        payload=CanonicalPayload.from_mapping(
            schema="record_registered_payload",
            version=1,
            value={"record_id": "abc", "status": "registered"},
        ),
    )


def test_builds_complete_immutable_domain_event() -> None:
    event = valid_event()

    assert event.event_id.entity_type == "domain_event"
    assert event.aggregate_reference.organization_id == event.organization_id
    assert event.timestamps.occurred_at != event.timestamps.recorded_at
    assert event.payload.canonical_bytes.startswith(b'["titan-json-v1",')

    with pytest.raises(FrozenInstanceError):
        event.event_version = 2  # type: ignore[misc]


def test_payload_snapshot_is_not_changed_with_original_mapping() -> None:
    original = {"status": "registered"}
    payload = CanonicalPayload.from_mapping(schema="record_payload", version=1, value=original)
    captured = payload.canonical_bytes

    original["status"] = "changed"

    assert payload.canonical_bytes == captured


def test_payload_cannot_be_built_from_arbitrary_bytes() -> None:
    with pytest.raises(TypeError):
        CanonicalPayload(  # type: ignore[call-arg]
            schema="record_payload",
            version=1,
            canonical_bytes=b"unverified",
        )


@pytest.mark.parametrize("schema", ["", "RecordPayload"])
def test_rejects_noncanonical_payload_schema(schema: str) -> None:
    with pytest.raises(ValueError, match="schema"):
        CanonicalPayload.from_mapping(schema=schema, version=1, value={})


def test_rejects_nonpositive_payload_version() -> None:
    with pytest.raises(ValueError, match="maior ou igual a 1"):
        CanonicalPayload.from_mapping(schema="record_payload", version=0, value={})


@pytest.mark.parametrize("reserved_key", ["password", "access_token", "private_key"])
def test_rejects_secret_or_credential_keys_in_payload(reserved_key: str) -> None:
    with pytest.raises(ValueError, match="segredo ou credencial"):
        CanonicalPayload.from_mapping(
            schema="record_payload",
            version=1,
            value={"nested": [{reserved_key: "not-allowed"}]},
        )


def test_rejects_event_id_with_wrong_logical_type() -> None:
    event = valid_event()

    with pytest.raises(ValueError, match="domain_event"):
        DomainEvent(
            event_id=TypedId.new("command"),
            organization_id=event.organization_id,
            aggregate_reference=event.aggregate_reference,
            aggregate_version=event.aggregate_version,
            event_type=event.event_type,
            event_version=event.event_version,
            timestamps=event.timestamps,
            actor_reference=event.actor_reference,
            source_reference=event.source_reference,
            correlation_id=event.correlation_id,
            causation_id=event.causation_id,
            payload=event.payload,
        )


def test_rejects_aggregate_from_another_organization() -> None:
    event = valid_event()

    with pytest.raises(ValueError, match="Organization"):
        DomainEvent(
            event_id=event.event_id,
            organization_id=OrganizationId.new(),
            aggregate_reference=event.aggregate_reference,
            aggregate_version=event.aggregate_version,
            event_type=event.event_type,
            event_version=event.event_version,
            timestamps=event.timestamps,
            actor_reference=event.actor_reference,
            source_reference=event.source_reference,
            correlation_id=event.correlation_id,
            causation_id=event.causation_id,
            payload=event.payload,
        )


@pytest.mark.parametrize("field", ["aggregate_version", "event_version"])
def test_rejects_nonpositive_versions(field: str) -> None:
    event = valid_event()
    values = {
        "event_id": event.event_id,
        "organization_id": event.organization_id,
        "aggregate_reference": event.aggregate_reference,
        "aggregate_version": event.aggregate_version,
        "event_type": event.event_type,
        "event_version": event.event_version,
        "timestamps": event.timestamps,
        "actor_reference": event.actor_reference,
        "source_reference": event.source_reference,
        "correlation_id": event.correlation_id,
        "causation_id": event.causation_id,
        "payload": event.payload,
    }
    values[field] = 0

    with pytest.raises(ValueError, match="maior ou igual a 1"):
        DomainEvent(**values)  # type: ignore[arg-type]


def test_accepts_only_domain_event_as_causation() -> None:
    event = valid_event()

    with pytest.raises(ValueError, match="causation_id"):
        DomainEvent(
            event_id=event.event_id,
            organization_id=event.organization_id,
            aggregate_reference=event.aggregate_reference,
            aggregate_version=event.aggregate_version,
            event_type=event.event_type,
            event_version=event.event_version,
            timestamps=event.timestamps,
            actor_reference=event.actor_reference,
            source_reference=event.source_reference,
            correlation_id=event.correlation_id,
            causation_id=TypedId.new("command"),
            payload=event.payload,
        )
