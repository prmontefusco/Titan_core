"""Testes do repositório de leitura `WorkshopDashboard` — Titan Asset A6."""

from decimal import Decimal

from packages.asset_domain.work_order import WorkOrderState
from packages.asset_infrastructure.persistence.work_order_repository import work_orders_table
from packages.asset_infrastructure.persistence.workshop_dashboard_repository import (
    _open_work_orders_statement,
    _sum_reserved_qty_by_part,
)
from packages.shared_kernel import TypedId


def test_reserved_qty_by_part_sums_rows_with_same_part() -> None:
    part_ref = TypedId.new("part")
    other_part_ref = TypedId.new("part")

    totals = _sum_reserved_qty_by_part(
        (
            (part_ref.value, Decimal("1.5")),
            (part_ref.value, Decimal("2.5")),
            (other_part_ref.value, Decimal("3")),
        )
    )

    assert totals == {
        part_ref: Decimal("4.0"),
        other_part_ref: Decimal("3"),
    }


def test_open_work_orders_statement_filters_site_workshop_and_terminal_states() -> None:
    site_ref = TypedId.new("customer_site")
    workshop_ref = TypedId.new("workshop")

    statement = _open_work_orders_statement(site_ref=site_ref, workshop_ref=workshop_ref)

    compiled = statement.compile()
    where_text = str(statement.whereclause)
    assert site_ref.value in compiled.params.values()
    assert workshop_ref.value in compiled.params.values()
    assert work_orders_table.c.site_id.name in where_text
    assert work_orders_table.c.workshop_id.name in where_text
    assert WorkOrderState.COMPLETED.value in str(
        statement.compile(compile_kwargs={"literal_binds": True})
    )
    assert WorkOrderState.CANCELLED.value in str(
        statement.compile(compile_kwargs={"literal_binds": True})
    )
