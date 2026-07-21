"""Criar elos versionados da cadeia de hashes dos eventos.

Revision ID: 20260721_0009
Revises: 20260721_0008
Create Date: 2026-07-21

Classificação: PROTECTED
Módulo owner: core_audit
Decisão: ADR 0007
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260721_0009"
down_revision: str | None = "20260721_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "core_audit"
TABLE = "domain_event_integrity"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("aggregate_type", sa.String(length=100), nullable=False),
        sa.Column("aggregate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("aggregate_version", sa.Integer(), nullable=False),
        sa.Column("previous_hash", sa.LargeBinary(), nullable=True),
        sa.Column("current_hash", sa.LargeBinary(), nullable=False),
        sa.Column("event_canonical_bytes", sa.LargeBinary(), nullable=False),
        sa.Column("hash_algorithm", sa.String(length=30), nullable=False),
        sa.Column("hash_profile", sa.String(length=100), nullable=False),
        sa.Column("hash_profile_version", sa.Integer(), nullable=False),
        sa.Column("canonical_serialization_version", sa.String(length=50), nullable=False),
        sa.CheckConstraint(
            "octet_length(current_hash) = 32", name="ck_integrity_current_hash_size"
        ),
        sa.CheckConstraint(
            "previous_hash IS NULL OR octet_length(previous_hash) = 32",
            name="ck_integrity_previous_hash_size",
        ),
        sa.CheckConstraint(
            "(aggregate_version = 1 AND previous_hash IS NULL) OR "
            "(aggregate_version > 1 AND previous_hash IS NOT NULL)",
            name="ck_integrity_previous_hash_position",
        ),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["core_audit.domain_events.event_id"],
            name="fk_event_integrity_event",
        ),
        sa.PrimaryKeyConstraint("event_id", name="pk_event_integrity"),
        sa.UniqueConstraint(
            "record_owner_organization_id",
            "aggregate_type",
            "aggregate_id",
            "aggregate_version",
            name="uq_event_integrity_aggregate_version",
        ),
        schema=SCHEMA,
    )
    op.execute(
        sa.text(
            "COMMENT ON TABLE core_audit.domain_event_integrity IS "
            "'titan.classification=PROTECTED;titan.module_owner=core_audit'"
        )
    )
    op.execute(sa.text("ALTER TABLE core_audit.domain_event_integrity ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text("ALTER TABLE core_audit.domain_event_integrity FORCE ROW LEVEL SECURITY"))
    context = (
        "record_owner_organization_id = "
        "NULLIF(current_setting('titan.organization_id', true), '')::uuid"
    )
    op.execute(
        sa.text(
            "CREATE POLICY event_integrity_select_by_owner ON "
            f"core_audit.domain_event_integrity FOR SELECT USING ({context})"
        )
    )
    op.execute(
        sa.text(
            "CREATE POLICY event_integrity_insert_by_owner ON "
            f"core_audit.domain_event_integrity FOR INSERT WITH CHECK ({context})"
        )
    )
    op.execute(sa.text("REVOKE ALL ON core_audit.domain_event_integrity FROM PUBLIC"))


def downgrade() -> None:
    op.execute(
        sa.text("DROP POLICY event_integrity_insert_by_owner ON core_audit.domain_event_integrity")
    )
    op.execute(
        sa.text("DROP POLICY event_integrity_select_by_owner ON core_audit.domain_event_integrity")
    )
    op.drop_table(TABLE, schema=SCHEMA)
