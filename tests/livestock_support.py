"""Apoio a testes da vertical Livestock (Passo 10.1a).

Vive fora de um `conftest.py` porque também é usado pelos testes de integração,
e importar de conftest alheio confunde a coleta do pytest.
"""

from dataclasses import dataclass, field

from packages.core_domain.decision import Decision
from packages.core_domain.evaluation import Evaluation
from packages.core_domain.events import DomainEvent
from packages.livestock_application.event_recorder import (
    LivestockEventRecorder,
    LivestockOperationContext,
)
from packages.shared_kernel import OrganizationId, SystemClock, TypedId, UniversalReference


@dataclass
class FakeEvaluationRepository:
    """As tabelas do Core, em memória: a vertical não guarda avaliação por conta própria."""

    saved: list[Evaluation] = field(default_factory=list)

    def save(self, evaluation: Evaluation) -> None:
        self.saved.append(evaluation)


@dataclass
class FakeDecisionRepository:
    saved: list[Decision] = field(default_factory=list)

    def save(self, decision: Decision) -> None:
        self.saved.append(decision)


@dataclass
class FakeEventLog:
    """Log em memória que imita a numeração por agregado do repositório do Core.

    A checagem de sequência não é enfeite: é ela que faz um serviço que esqueça de
    consultar a versão corrente falhar no teste unitário, em vez de só no
    PostgreSQL.
    """

    events: list[DomainEvent] = field(default_factory=list)

    def append(self, event: DomainEvent) -> None:
        expected = len(self.versions_of(event.aggregate_reference)) + 1
        if event.aggregate_version != expected:
            raise AssertionError(
                f"Versão {event.aggregate_version} fora de sequência; esperada {expected}."
            )
        self.events.append(event)

    def list_versions(self, aggregate_reference: UniversalReference) -> tuple[int, ...]:
        return self.versions_of(aggregate_reference)

    def versions_of(self, aggregate_reference: UniversalReference) -> tuple[int, ...]:
        return tuple(
            event.aggregate_version
            for event in self.events
            if event.aggregate_reference == aggregate_reference
        )

    def types(self) -> list[str]:
        return [event.event_type for event in self.events]

    def of_type(self, event_type: str) -> list[DomainEvent]:
        return [event for event in self.events if event.event_type == event_type]

    def only(self, event_type: str) -> DomainEvent:
        matches = self.of_type(event_type)
        assert len(matches) == 1, f"Esperado exatamente um '{event_type}', houve {len(matches)}."
        return matches[0]


def in_memory_recorder() -> tuple[LivestockEventRecorder, FakeEventLog]:
    """Gravador sobre log em memória, para o teste que não é sobre o log."""
    event_log = FakeEventLog()
    return LivestockEventRecorder(event_log=event_log, clock=SystemClock()), event_log


def operation_context(organization_id: OrganizationId) -> LivestockOperationContext:
    return LivestockOperationContext.create(
        organization_id=organization_id,
        actor_id=TypedId.new("actor"),
        source_id=TypedId.new("system"),
    )
