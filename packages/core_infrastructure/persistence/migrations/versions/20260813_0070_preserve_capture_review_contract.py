"""Preserva o contrato integral de captura e review.

Revision ID: 20260813_0070
Revises: 20260813_0069
"""

from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "20260813_0070"
down_revision = "20260813_0069"
branch_labels = None
depends_on = None

SCHEMA = "core_audit"
ARTIFACTS = "external_source_capture_artifacts"
REVIEWS = "external_source_capture_association_reviews"


def _add_required_column(table: str, column: sa.Column[Any], fill: str) -> None:
    op.add_column(table, column, schema=SCHEMA)
    op.execute(
        sa.text(f"UPDATE {SCHEMA}.{table} SET {column.name} = {fill} WHERE {column.name} IS NULL")
    )
    op.alter_column(table, column.name, nullable=False, schema=SCHEMA)


def upgrade() -> None:
    op.add_column(
        ARTIFACTS,
        sa.Column("projection_digest", sa.String(length=64), nullable=True),
        schema=SCHEMA,
    )
    _add_required_column(ARTIFACTS, sa.Column("limitations", JSONB(), nullable=True), "'[]'::jsonb")
    _add_required_column(
        ARTIFACTS,
        sa.Column("recorded_by_entity_type", sa.String(length=40), nullable=True),
        "'actor'",
    )
    _add_required_column(
        REVIEWS,
        sa.Column("reviewed_by_entity_type", sa.String(length=40), nullable=True),
        "'actor'",
    )
    _add_required_column(REVIEWS, sa.Column("limitations", JSONB(), nullable=True), "'[]'::jsonb")


def downgrade() -> None:
    op.drop_column(REVIEWS, "limitations", schema=SCHEMA)
    op.drop_column(REVIEWS, "reviewed_by_entity_type", schema=SCHEMA)
    op.drop_column(ARTIFACTS, "recorded_by_entity_type", schema=SCHEMA)
    op.drop_column(ARTIFACTS, "limitations", schema=SCHEMA)
    op.drop_column(ARTIFACTS, "projection_digest", schema=SCHEMA)
