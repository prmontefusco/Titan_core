"""Bloqueio transacional para correção de TransformationEvent (ADR-0047, item 5).

Isolado da leitura/escrita normal (`transformation_repository.py`,
`animal_repository.py`) porque o único consumidor é o protocolo de
lock→revalida→escreve descrito na ADR — nenhum leitor comum precisa de
`SELECT ... FOR UPDATE`. Uma linha ausente devolve `False` em vez de lançar:
quem chama já tem sua própria guarda de domínio para "não existe" (ex.:
`AnimalNaoAbatido`), e duplicar essa checagem aqui só divergiria da mensagem.
"""

from dataclasses import dataclass

from sqlalchemy import Connection, select

from packages.livestock_application.transformation_service import TransformationLockPort
from packages.livestock_infrastructure.persistence.animal_repository import animals_table
from packages.livestock_infrastructure.persistence.transformation_repository import (
    traceable_items_table,
    transformation_events_table,
)
from packages.shared_kernel import TypedId


@dataclass(frozen=True, slots=True)
class TransactionalTransformationLock(TransformationLockPort):
    connection: Connection

    def lock_transformation_event(self, event_id: TypedId) -> bool:
        row = self.connection.execute(
            select(transformation_events_table.c.event_id)
            .where(transformation_events_table.c.event_id == event_id.value)
            .with_for_update()
        ).one_or_none()
        return row is not None

    def lock_traceable_item(self, item_id: TypedId) -> bool:
        row = self.connection.execute(
            select(traceable_items_table.c.item_id)
            .where(traceable_items_table.c.item_id == item_id.value)
            .with_for_update()
        ).one_or_none()
        return row is not None

    def lock_animal(self, animal_id: TypedId) -> bool:
        row = self.connection.execute(
            select(animals_table.c.animal_id)
            .where(animals_table.c.animal_id == animal_id.value)
            .with_for_update()
        ).one_or_none()
        return row is not None
