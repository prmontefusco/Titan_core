from dataclasses import dataclass, field

from packages.core_application import DomainEventLogService
from packages.core_domain import DomainEvent
from packages.shared_kernel import UniversalReference
from tests.core_domain.test_domain_event import valid_event


@dataclass
class InMemoryEventLog:
    events: list[DomainEvent] = field(default_factory=list)

    def append(self, event: DomainEvent) -> None:
        self.events.append(event)

    def list_versions(self, aggregate_reference: UniversalReference) -> tuple[int, ...]:
        return tuple(
            event.aggregate_version
            for event in self.events
            if event.aggregate_reference == aggregate_reference
        )


def test_application_exposes_only_append_and_ordered_query() -> None:
    event_log = InMemoryEventLog()
    service = DomainEventLogService(event_log)
    event = valid_event()

    service.record(event)

    assert service.versions(event.aggregate_reference) == (event.aggregate_version,)
    assert not hasattr(service, "update")
    assert not hasattr(service, "delete")
