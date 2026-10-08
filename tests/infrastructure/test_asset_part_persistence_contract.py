"""Contrato de persistência de Part — Titan Asset."""

from sqlalchemy import UniqueConstraint

from packages.asset_infrastructure.persistence.part_repository import parts_table


def test_part_number_is_unique_inside_record_owner_organization() -> None:
    constraints = {
        constraint.name: tuple(column.name for column in constraint.columns)
        for constraint in parts_table.constraints
        if isinstance(constraint, UniqueConstraint)
    }

    assert constraints["uq_parts_owner_part_number"] == (
        "record_owner_organization_id",
        "part_number",
    )
