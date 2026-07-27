"""create establishment qualifications

Revision ID: 20260727_0055
Revises: 20260727_0054
Create Date: 2026-07-27 00:55:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260727_0055"
down_revision: str | Sequence[str] | None = "20260727_0054"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "establishment_qualifications",
        sa.Column("qualification_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("counterparty_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("market_purpose", sa.String(length=120), nullable=False),
        sa.Column("qualification_status", sa.String(length=40), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=False),
        sa.Column("source_version", sa.String(length=120), nullable=True),
        sa.Column("assessed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "evidence_references",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["counterparty_id"],
            ["core_audit.external_counterparties.counterparty_id"],
            name="fk_establishment_qualifications_counterparty",
        ),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_establishment_qualifications_organization",
        ),
        sa.PrimaryKeyConstraint("qualification_id"),
        schema="core_audit",
        comment="titan.classification=PROTECTED;titan.module_owner=livestock",
    )


def downgrade() -> None:
    op.drop_table("establishment_qualifications", schema="core_audit")
