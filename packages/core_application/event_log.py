"""Porta append-only para registrar e consultar a ordem dos eventos."""

from dataclasses import dataclass
from typing import Protocol

from packages.core_domain import DomainEvent
from packages.shared_kernel import UniversalReference


class DomainEventLog(Protocol):
    def append(self, event: DomainEvent) -> None: ...

    def list_versions(self, aggregate_reference: UniversalReference) -> tuple[int, ...]: ...


@dataclass(frozen=True, slots=True)
class DomainEventLogService:
    event_log: DomainEventLog

    def record(self, event: DomainEvent) -> None:
        if not isinstance(event, DomainEvent):
            raise TypeError("event deve ser um DomainEvent.")
        self.event_log.append(event)

    def versions(self, aggregate_reference: UniversalReference) -> tuple[int, ...]:
        if not isinstance(aggregate_reference, UniversalReference):
            raise TypeError("aggregate_reference deve ser UniversalReference.")
        return self.event_log.list_versions(aggregate_reference)
