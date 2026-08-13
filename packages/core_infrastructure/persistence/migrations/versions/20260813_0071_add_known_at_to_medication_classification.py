"""Acrescenta disponibilidade de conhecimento à assertion sanitária.

Revision ID: 20260813_0071
Revises: 20260813_0070
"""

import sqlalchemy as sa
from alembic import op

revision = "20260813_0071"
down_revision = "20260813_0070"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "medication_classification_assertions",
        sa.Column("known_at", sa.DateTime(timezone=True), nullable=True),
        schema="core_audit",
    )
    op.create_index(
        "ix_medication_classification_assertions_temporal_selection",
        "medication_classification_assertions",
        ["record_owner_organization_id", "medication_id", "category", "known_at"],
        schema="core_audit",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_medication_classification_assertions_temporal_selection",
        table_name="medication_classification_assertions",
        schema="core_audit",
    )
    op.drop_column("medication_classification_assertions", "known_at", schema="core_audit")
