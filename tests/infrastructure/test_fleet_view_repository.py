"""Testes do repositório de leitura `FleetView` — Titan Asset A6."""

from packages.asset_domain.work_order import WorkOrderState
from packages.asset_infrastructure.persistence.fleet_view_repository import (
    _open_work_orders_for_vehicle_statement,
    _vehicles_statement,
)
from packages.asset_infrastructure.persistence.vehicle_repository import vehicles_table
from packages.asset_infrastructure.persistence.work_order_repository import work_orders_table
from packages.shared_kernel import TypedId


def test_vehicles_statement_filters_by_site_when_requested() -> None:
    site_ref = TypedId.new("customer_site")

    statement = _vehicles_statement(site_ref=site_ref)

    compiled = statement.compile()
    assert site_ref.value in compiled.params.values()
    assert vehicles_table.c.site_id.name in str(statement.whereclause)


def test_vehicles_statement_without_site_lists_whole_fleet() -> None:
    statement = _vehicles_statement()

    assert statement.whereclause is None


def test_open_work_orders_for_vehicle_statement_filters_terminal_states() -> None:
    vehicle_ref = TypedId.new("vehicle")

    statement = _open_work_orders_for_vehicle_statement(vehicle_ref)

    compiled_sql = str(statement.compile(compile_kwargs={"literal_binds": True}))
    assert vehicle_ref.value in statement.compile().params.values()
    assert work_orders_table.c.vehicle_id.name in str(statement.whereclause)
    assert WorkOrderState.COMPLETED.value in compiled_sql
    assert WorkOrderState.CANCELLED.value in compiled_sql
