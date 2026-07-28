"""Adicionar correção de TransformationEvent publicado (ADR-0047, Passo 11.7).

Revision ID: 20260728_0058
Revises: 20260728_0057
Create Date: 2026-07-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260728_0058"
down_revision: str | Sequence[str] | None = "20260728_0057"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

SCHEMA = "core_audit"
EVENTS_TABLE = "transformation_events"


def upgrade() -> None:
    op.add_column(
        EVENTS_TABLE,
        sa.Column("corrects_transformation_id", postgresql.UUID(as_uuid=True), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        EVENTS_TABLE,
        sa.Column("correction_reason", sa.Text(), nullable=True),
        schema=SCHEMA,
    )
    op.create_foreign_key(
        "fk_transformation_events_corrects",
        EVENTS_TABLE,
        EVENTS_TABLE,
        ["corrects_transformation_id"],
        ["event_id"],
        source_schema=SCHEMA,
        referent_schema=SCHEMA,
    )
    # ADR-0047, invariante 7: no máximo uma correção direta por evento. Postgres
    # permite múltiplos NULL num índice UNIQUE — eventos comuns nunca colidem.
    op.create_unique_constraint(
        "uq_transformation_events_corrects_transformation_id",
        EVENTS_TABLE,
        ["corrects_transformation_id"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_transformation_events_corrects_transformation_id",
        EVENTS_TABLE,
        schema=SCHEMA,
        type_="unique",
    )
    op.drop_constraint(
        "fk_transformation_events_corrects",
        EVENTS_TABLE,
        schema=SCHEMA,
        type_="foreignkey",
    )
    op.drop_column(EVENTS_TABLE, "correction_reason", schema=SCHEMA)
    op.drop_column(EVENTS_TABLE, "corrects_transformation_id", schema=SCHEMA)
