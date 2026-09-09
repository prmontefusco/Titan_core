"""Scope Livestock property foreign keys by owner Organization.

Revision ID: 20260909_0083
Revises: 20260908_0082
Create Date: 2026-09-09
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260909_0083"
down_revision: str | None = "20260908_0082"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "core_audit"
PROPERTY_TARGET = ["record_owner_organization_id", "property_id"]
PROPERTY_SOURCE = [
    "core_audit.rural_properties.record_owner_organization_id",
    "core_audit.rural_properties.property_id",
]

FOREIGN_KEYS = (
    ("animals", "fk_animals_birth_property", ["record_owner_organization_id", "birth_property_id"]),
    (
        "animal_movements",
        "fk_animal_movements_origin_property",
        ["record_owner_organization_id", "origin_property_id"],
    ),
    (
        "animal_movements",
        "fk_animal_movements_destination_property",
        ["record_owner_organization_id", "destination_property_id"],
    ),
    (
        "property_stays",
        "fk_property_stays_property",
        ["record_owner_organization_id", "property_id"],
    ),
    (
        "livestock_lots",
        "fk_livestock_lots_property",
        ["record_owner_organization_id", "property_id"],
    ),
)


def upgrade() -> None:
    for table, constraint, columns in FOREIGN_KEYS:
        op.drop_constraint(constraint, table, schema=SCHEMA, type_="foreignkey")
        op.create_foreign_key(
            constraint,
            table,
            "rural_properties",
            columns,
            PROPERTY_TARGET,
            source_schema=SCHEMA,
            referent_schema=SCHEMA,
        )


def downgrade() -> None:
    raise RuntimeError("TENANT_SCOPED_PROPERTY_FK_DOWNGRADE_NAO_PERMITIDO")
