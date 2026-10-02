"""Query de detalhe de `WorkOrder` — Titan Asset A5.

`GetWorkOrder(work_order_id)` é uma leitura de aplicação: abre o agregado para
exibição operacional sem acionar comandos, eventos ou serviços coordenadores.
"""

from dataclasses import dataclass
from typing import Protocol

from packages.asset_domain.work_order import WorkOrder
from packages.shared_kernel import TypedId


class WorkOrderQueryRepositoryPort(Protocol):
    def get_by_id(self, work_order_id: TypedId) -> WorkOrder | None: ...


class WorkOrderDetailNaoEncontrado(KeyError):
    """`work_order_id` não corresponde a nenhuma `WorkOrder` visível nesta Organization."""


@dataclass(frozen=True, slots=True)
class WorkOrderQueryService:
    repository: WorkOrderQueryRepositoryPort

    def get_work_order(self, work_order_id: TypedId) -> WorkOrder:
        work_order = self.repository.get_by_id(work_order_id)
        if work_order is None:
            raise WorkOrderDetailNaoEncontrado(f"WorkOrder '{work_order_id.value}' não encontrada.")
        return work_order
