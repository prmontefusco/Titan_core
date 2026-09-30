"""Repositório de leitura do `WorkshopDashboard` — Titan Asset A6.

Este adapter monta a projection a partir das tabelas já existentes de
`WorkOrder`, `StockReservation` e `StockPosition`. Não cria fonte de verdade
paralela: se a projection precisar ser reconstruída, basta reler os agregados
persistidos.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Connection, Select, func, select

from packages.asset_application.workshop_dashboard import WorkshopDashboardSnapshot
from packages.asset_domain.inventory import ReservationState
from packages.asset_domain.work_order import TERMINAL_STATES, WorkOrder
from packages.asset_infrastructure.persistence.inventory_repository import (
    stock_positions_table,
    stock_reservations_table,
)
from packages.asset_infrastructure.persistence.work_order_repository import (
    TransactionalWorkOrderRepository,
    work_orders_table,
)
from packages.shared_kernel import TypedId


def _sum_reserved_qty_by_part(
    rows: Iterable[tuple[UUID, Decimal]],
) -> dict[TypedId, Decimal]:
    totals: dict[TypedId, Decimal] = {}
    for part_id, qty in rows:
        part_ref = TypedId(entity_type="part", value=part_id)
        totals[part_ref] = totals.get(part_ref, Decimal(0)) + qty
    return totals


@dataclass(frozen=True, slots=True)
class TransactionalWorkshopDashboardRepository:
    connection: Connection

    def __post_init__(self) -> None:
        if not isinstance(self.connection, Connection) or not self.connection.in_transaction():
            raise RuntimeError(
                "TransactionalWorkshopDashboardRepository exige Connection com transação ativa."
            )

    def list_open_by_site(
        self, *, site_ref: TypedId, workshop_ref: TypedId | None = None
    ) -> tuple[WorkshopDashboardSnapshot, ...]:
        statement = _open_work_orders_statement(site_ref=site_ref, workshop_ref=workshop_ref)
        rows = self.connection.execute(statement).fetchall()
        work_order_repository = TransactionalWorkOrderRepository(connection=self.connection)
        snapshots: list[WorkshopDashboardSnapshot] = []
        for row in rows:
            work_order = work_order_repository.get_by_id(
                TypedId(entity_type="work_order", value=row.work_order_id)
            )
            if work_order is None:
                continue
            snapshots.append(
                WorkshopDashboardSnapshot(
                    work_order=work_order,
                    reserved_qty_by_part=self._reserved_qty_by_part(work_order),
                )
            )
        return tuple(snapshots)

    def _reserved_qty_by_part(self, work_order: WorkOrder) -> dict[TypedId, Decimal]:
        if not work_order.material_reservations:
            return {}
        rows = self.connection.execute(
            select(
                stock_positions_table.c.part_id,
                func.coalesce(func.sum(stock_reservations_table.c.qty), Decimal(0)).label(
                    "reserved_qty"
                ),
            )
            .select_from(
                stock_reservations_table.join(
                    stock_positions_table,
                    stock_positions_table.c.stock_position_id
                    == stock_reservations_table.c.stock_position_id,
                )
            )
            .where(
                stock_reservations_table.c.reservation_id.in_(
                    [reservation.value for reservation in work_order.material_reservations]
                ),
                stock_reservations_table.c.state != ReservationState.RELEASED.value,
            )
            .group_by(stock_positions_table.c.part_id)
        ).fetchall()
        return _sum_reserved_qty_by_part((row.part_id, row.reserved_qty) for row in rows)


def _open_work_orders_statement(
    *, site_ref: TypedId, workshop_ref: TypedId | None = None
) -> Select[tuple[object]]:
    statement = select(work_orders_table.c.work_order_id).where(
        work_orders_table.c.site_id == site_ref.value,
        work_orders_table.c.state.not_in([state.value for state in TERMINAL_STATES]),
    )
    if workshop_ref is not None:
        statement = statement.where(work_orders_table.c.workshop_id == workshop_ref.value)
    return statement.order_by(work_orders_table.c.priority_score.desc().nullslast())
