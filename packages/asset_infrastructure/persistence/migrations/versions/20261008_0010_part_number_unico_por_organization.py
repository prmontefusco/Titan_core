"""Garantir part_number único por Organization (I-INV-0).

Revision ID: 20261008_0010
Revises: 20260911_0009
Create Date: 2026-10-08
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261008_0010"
down_revision: str | None = "20260911_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "core_audit"
CONSTRAINT = "uq_parts_owner_part_number"


def upgrade() -> None:
    op.create_unique_constraint(
        CONSTRAINT,
        "parts",
        ["record_owner_organization_id", "part_number"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_constraint(CONSTRAINT, "parts", schema=SCHEMA, type_="unique")
