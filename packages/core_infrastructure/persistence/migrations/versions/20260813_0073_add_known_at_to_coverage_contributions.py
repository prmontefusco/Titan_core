"""Acrescenta conhecimento explícito a contribuições dimensionais.

Revision ID: 20260813_0073
Revises: 20260813_0072
"""

import sqlalchemy as sa
from alembic import op

revision = "20260813_0073"
down_revision = "20260813_0072"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "coverage_contributions",
        sa.Column("known_at", sa.DateTime(timezone=True), nullable=True),
        schema="core_audit",
    )
    op.create_index(
        "ix_coverage_contributions_temporal_selection",
        "coverage_contributions",
        ["record_owner_organization_id", "subject_id", "dimension", "known_at"],
        schema="core_audit",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_coverage_contributions_temporal_selection",
        table_name="coverage_contributions",
        schema="core_audit",
    )
    op.drop_column("coverage_contributions", "known_at", schema="core_audit")
