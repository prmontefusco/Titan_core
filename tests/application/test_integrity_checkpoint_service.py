from dataclasses import dataclass, replace
from datetime import UTC, datetime

from packages.core_application import IntegrityCheckpointService
from packages.core_integrity import (
    IntegrityCheckpoint,
    build_event_chain_entry,
    build_integrity_checkpoint,
)
from packages.shared_kernel import TypedId
from tests.core_domain.test_domain_event import reference, valid_event


@dataclass
class InMemoryCheckpointWriter:
    stored: IntegrityCheckpoint | None = None

    def add(self, checkpoint: IntegrityCheckpoint) -> None:
        self.stored = checkpoint


def test_application_builds_and_persists_checkpoint_once() -> None:
    first_event = replace(valid_event(), aggregate_version=1)
    second_event = replace(
        valid_event(),
        organization_id=first_event.organization_id,
        aggregate_reference=first_event.aggregate_reference,
        aggregate_version=2,
    )
    first_entry = build_event_chain_entry(first_event, None)
    entries = (first_entry, build_event_chain_entry(second_event, first_entry.current_hash))
    expected = build_integrity_checkpoint(
        checkpoint_id=TypedId.new("integrity_checkpoint"),
        entries=entries,
        observed_at=datetime(2026, 7, 21, 18, 0, tzinfo=UTC),
        producer_reference=reference("service_identity", first_event.organization_id),
        correlation_id=TypedId.new("correlation"),
        causation_id=second_event.event_id,
    )
    writer = InMemoryCheckpointWriter()

    created = IntegrityCheckpointService(writer).create(
        checkpoint_id=expected.checkpoint_id,
        entries=entries,
        observed_at=expected.observed_at,
        producer_reference=expected.producer_reference,
        correlation_id=expected.correlation_id,
        causation_id=expected.causation_id,
    )

    assert created == expected
    assert writer.stored == expected
