"""Garantir StockPosition única por Organization, Part, Location e purpose.

Revision ID: 20261008_0011
Revises: 20261008_0010
Create Date: 2026-10-08
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261008_0011"
down_revision: str | None = "20261008_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "core_audit"
CONSTRAINT = "uq_stock_positions_owner_part_location_purpose"


def upgrade() -> None:
    op.create_unique_constraint(
        CONSTRAINT,
        "stock_positions",
        ["record_owner_organization_id", "part_id", "location_id", "purpose"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_constraint(CONSTRAINT, "stock_positions", schema=SCHEMA, type_="unique")
