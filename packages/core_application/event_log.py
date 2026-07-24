"""Porta append-only para registrar e consultar a ordem dos eventos."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from packages.core_domain import DomainEvent
from packages.shared_kernel import TypedId, UniversalReference


class DomainEventLog(Protocol):
    def append(self, event: DomainEvent) -> None: ...

    def list_versions(self, aggregate_reference: UniversalReference) -> tuple[int, ...]: ...


class RecordedEvent(Protocol):
    """O que a leitura de um evento já persistido oferece.

    Descrito por estrutura, e não pelo tipo concreto da persistência, porque a
    Application não pode conhecer a Infrastructure — a mesma solução que
    `ProvenanceService` já usava, aqui com tipo em vez de `Any`.

    O payload aparece só pelo nome do schema: quem lê ordem e autoria não precisa
    desserializar conteúdo, e não desserializar é o que mantém a leitura barata e
    imune a payload de versão desconhecida.

    Os membros são propriedades, e não atributos: atributo de Protocol exige ser
    gravável, o que nenhum registro imutável do Titan é. Declarados assim, os
    dataclasses congelados da persistência satisfazem o contrato — e continua
    valendo que ninguém escreve por esta porta.
    """

    @property
    def event_id(self) -> TypedId: ...

    @property
    def aggregate_reference(self) -> UniversalReference: ...

    @property
    def aggregate_version(self) -> int: ...

    @property
    def event_type(self) -> str: ...

    @property
    def occurred_at(self) -> datetime: ...

    @property
    def recorded_at(self) -> datetime: ...

    @property
    def actor_reference(self) -> UniversalReference: ...

    @property
    def correlation_id(self) -> TypedId: ...

    @property
    def causation_id(self) -> TypedId | None: ...

    @property
    def payload_schema(self) -> str: ...


class DomainEventReader(Protocol):
    """Leitura ordenada de um fluxo, sem qualquer forma de escrita."""

    def list_for_aggregate(
        self, aggregate_reference: UniversalReference
    ) -> Sequence[RecordedEvent]: ...


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
