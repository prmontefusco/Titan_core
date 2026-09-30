"""Repositório de leitura da `FleetView` — Titan Asset A6.

Monta a projection a partir das tabelas atuais de `Vehicle` e `WorkOrder`.
Não materializa estado operacional em tabela própria; a classificação continua
na camada de aplicação (`FleetViewService`).
"""

from dataclasses import dataclass

from sqlalchemy import Connection, Select, select

from packages.asset_application.fleet_view import FleetViewSnapshot
from packages.asset_domain.work_order import TERMINAL_STATES, WorkOrder
from packages.asset_infrastructure.persistence.vehicle_repository import (
    TransactionalVehicleRepository,
    vehicles_table,
)
from packages.asset_infrastructure.persistence.work_order_repository import (
    TransactionalWorkOrderRepository,
    work_orders_table,
)
from packages.shared_kernel import TypedId


@dataclass(frozen=True, slots=True)
class TransactionalFleetViewRepository:
    connection: Connection

    def __post_init__(self) -> None:
        if not isinstance(self.connection, Connection) or not self.connection.in_transaction():
            raise RuntimeError(
                "TransactionalFleetViewRepository exige Connection com transação ativa."
            )

    def list_fleet(self, *, site_ref: TypedId | None = None) -> tuple[FleetViewSnapshot, ...]:
        vehicle_rows = self.connection.execute(_vehicles_statement(site_ref=site_ref)).fetchall()
        vehicle_repository = TransactionalVehicleRepository(connection=self.connection)
        snapshots: list[FleetViewSnapshot] = []
        for row in vehicle_rows:
            vehicle = vehicle_repository.get_by_id(
                TypedId(entity_type="vehicle", value=row.vehicle_id)
            )
            if vehicle is None:
                continue
            snapshots.append(
                FleetViewSnapshot(
                    vehicle=vehicle,
                    open_work_orders=self._open_work_orders_for_vehicle(vehicle.vehicle_id),
                )
            )
        return tuple(snapshots)

    def _open_work_orders_for_vehicle(self, vehicle_ref: TypedId) -> tuple[WorkOrder, ...]:
        work_order_rows = self.connection.execute(
            _open_work_orders_for_vehicle_statement(vehicle_ref)
        ).fetchall()
        work_order_repository = TransactionalWorkOrderRepository(connection=self.connection)
        work_orders: list[WorkOrder] = []
        for row in work_order_rows:
            work_order = work_order_repository.get_by_id(
                TypedId(entity_type="work_order", value=row.work_order_id)
            )
            if work_order is not None:
                work_orders.append(work_order)
        return tuple(work_orders)


def _vehicles_statement(*, site_ref: TypedId | None = None) -> Select[tuple[object]]:
    statement = select(vehicles_table.c.vehicle_id)
    if site_ref is not None:
        statement = statement.where(vehicles_table.c.site_id == site_ref.value)
    return statement.order_by(vehicles_table.c.vehicle_id)


def _open_work_orders_for_vehicle_statement(vehicle_ref: TypedId) -> Select[tuple[object]]:
    return (
        select(work_orders_table.c.work_order_id)
        .where(
            work_orders_table.c.vehicle_id == vehicle_ref.value,
            work_orders_table.c.state.not_in([state.value for state in TERMINAL_STATES]),
        )
        .order_by(work_orders_table.c.priority_score.desc().nullslast())
    )
