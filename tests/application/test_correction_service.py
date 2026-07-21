from dataclasses import dataclass, field
from datetime import UTC, datetime

from packages.core_application import CorrectionService
from packages.core_domain import ChangeKind, DomainEvent
from packages.shared_kernel import TypedId
from tests.core_domain.test_domain_event import reference, valid_event


@dataclass
class InMemoryEventWriter:
    events: list[DomainEvent] = field(default_factory=list)

    def append(self, event: DomainEvent) -> None:
        self.events.append(event)


def test_service_appends_correction_after_original_without_mutating_it() -> None:
    original = valid_event()
    original_snapshot = original.payload.canonical_bytes
    writer = InMemoryEventWriter([original])

    correction = CorrectionService(writer).correct(
        correction_event_id=TypedId.new("domain_event"),
        original=original,
        aggregate_version=4,
        change_kind=ChangeKind.CORRECAO_DE_ERRO,
        justification="Estado original estava incorreto.",
        new_content={"status": "corrigido"},
        corrected_at=datetime(2026, 7, 21, 21, 0, tzinfo=UTC),
        actor_reference=reference("actor", original.organization_id),
        source_reference=reference("source", original.organization_id),
        correlation_id=TypedId.new("correlation"),
    )

    assert writer.events == [original, correction.event]
    assert writer.events[1].causation_id == writer.events[0].event_id
    assert writer.events[0].payload.canonical_bytes == original_snapshot
