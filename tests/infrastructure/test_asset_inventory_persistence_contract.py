"""Contrato de persistência de Inventory — Titan Asset."""

from sqlalchemy import UniqueConstraint

from packages.asset_infrastructure.persistence.inventory_repository import stock_positions_table


def test_stock_position_scope_is_unique_inside_record_owner_organization() -> None:
    constraints = {
        constraint.name: tuple(column.name for column in constraint.columns)
        for constraint in stock_positions_table.constraints
        if isinstance(constraint, UniqueConstraint)
    }

    assert constraints["uq_stock_positions_owner_part_location_purpose"] == (
        "record_owner_organization_id",
        "part_id",
        "location_id",
        "purpose",
    )
