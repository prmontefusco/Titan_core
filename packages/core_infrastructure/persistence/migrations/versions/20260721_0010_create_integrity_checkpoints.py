"""Criar checkpoints verificáveis e seu conjunto coberto.

Revision ID: 20260721_0010
Revises: 20260721_0009
Create Date: 2026-07-21

Classificação: PROTECTED
Módulo owner: core_audit
Decisão: ADR 0007
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260721_0010"
down_revision: str | None = "20260721_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "core_audit"
TABLES = ("integrity_checkpoints", "integrity_checkpoint_events")


def _protect(table: str) -> None:
    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{table} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{table} FORCE ROW LEVEL SECURITY"))
    context = (
        "record_owner_organization_id = "
        "NULLIF(current_setting('titan.organization_id', true), '')::uuid"
    )
    op.execute(
        sa.text(
            f"CREATE POLICY {table}_select_by_owner ON {SCHEMA}.{table} "
            f"FOR SELECT USING ({context})"
        )
    )
    op.execute(
        sa.text(
            f"CREATE POLICY {table}_insert_by_owner ON {SCHEMA}.{table} "
            f"FOR INSERT WITH CHECK ({context})"
        )
    )
    op.execute(sa.text(f"REVOKE ALL ON {SCHEMA}.{table} FROM PUBLIC"))


def upgrade() -> None:
    op.create_table(
        "integrity_checkpoints",
        sa.Column("checkpoint_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("aggregate_type", sa.String(100), nullable=False),
        sa.Column("aggregate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("aggregate_contract_version", sa.Integer(), nullable=False),
        sa.Column("first_sequence", sa.Integer(), nullable=False),
        sa.Column("last_sequence", sa.Integer(), nullable=False),
        sa.Column("record_count", sa.Integer(), nullable=False),
        sa.Column("initial_hash", sa.LargeBinary(), nullable=False),
        sa.Column("final_hash", sa.LargeBinary(), nullable=False),
        sa.Column("hash_algorithm", sa.String(30), nullable=False),
        sa.Column("event_chain_profile", sa.String(100), nullable=False),
        sa.Column("event_chain_profile_version", sa.Integer(), nullable=False),
        sa.Column("checkpoint_profile", sa.String(100), nullable=False),
        sa.Column("checkpoint_profile_version", sa.Integer(), nullable=False),
        sa.Column("canonical_serialization_version", sa.String(50), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("producer_type", sa.String(100), nullable=False),
        sa.Column("producer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("producer_organization_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("producer_contract_version", sa.Integer(), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("causation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("checkpoint_canonical_bytes", sa.LargeBinary(), nullable=False),
        sa.Column("checkpoint_digest", sa.LargeBinary(), nullable=False),
        sa.CheckConstraint("first_sequence = 1", name="ck_checkpoints_first_sequence"),
        sa.CheckConstraint("record_count = last_sequence", name="ck_checkpoints_count"),
        sa.CheckConstraint("octet_length(initial_hash) = 32", name="ck_checkpoints_initial_hash"),
        sa.CheckConstraint("octet_length(final_hash) = 32", name="ck_checkpoints_final_hash"),
        sa.CheckConstraint("octet_length(checkpoint_digest) = 32", name="ck_checkpoints_digest"),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_integrity_checkpoints_owner",
        ),
        sa.PrimaryKeyConstraint("checkpoint_id", name="pk_integrity_checkpoints"),
        schema=SCHEMA,
    )
    op.create_table(
        "integrity_checkpoint_events",
        sa.Column("checkpoint_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_hash", sa.LargeBinary(), nullable=False),
        sa.CheckConstraint("sequence > 0", name="ck_checkpoint_events_sequence"),
        sa.CheckConstraint("octet_length(event_hash) = 32", name="ck_checkpoint_events_hash"),
        sa.ForeignKeyConstraint(
            ["checkpoint_id"],
            ["core_audit.integrity_checkpoints.checkpoint_id"],
            name="fk_checkpoint_events_checkpoint",
        ),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["core_audit.domain_event_integrity.event_id"],
            name="fk_checkpoint_events_event",
        ),
        sa.UniqueConstraint("checkpoint_id", "sequence", name="uq_checkpoint_events_sequence"),
        sa.UniqueConstraint("checkpoint_id", "event_id", name="uq_checkpoint_events_event"),
        schema=SCHEMA,
    )
    for table in TABLES:
        op.execute(
            sa.text(
                f"COMMENT ON TABLE {SCHEMA}.{table} IS "
                "'titan.classification=PROTECTED;titan.module_owner=core_audit'"
            )
        )
        _protect(table)


def downgrade() -> None:
    for table in reversed(TABLES):
        op.execute(sa.text(f"DROP POLICY {table}_insert_by_owner ON {SCHEMA}.{table}"))
        op.execute(sa.text(f"DROP POLICY {table}_select_by_owner ON {SCHEMA}.{table}"))
        op.drop_table(table, schema=SCHEMA)
