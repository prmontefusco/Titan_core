"""Criar Transactional Outbox.

Revision ID: 20260722_0013
Revises: 20260722_0012
Create Date: 2026-07-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260722_0013"
down_revision: str | None = "20260722_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "core_audit"
TABLE = "outbox_messages"


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_domain_events_event_owner",
        "domain_events",
        ["event_id", "record_owner_organization_id"],
        schema=SCHEMA,
    )
    op.create_table(
        TABLE,
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("contract_type", sa.String(100), nullable=False),
        sa.Column("contract_version", sa.Integer(), nullable=False),
        sa.Column("actor_type", sa.String(100), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("producer_type", sa.String(100), nullable=False),
        sa.Column("producer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("causation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=True),
        sa.Column("payload_schema", sa.String(100), nullable=False),
        sa.Column("payload_version", sa.Integer(), nullable=False),
        sa.Column("payload_canonical_bytes", sa.LargeBinary(), nullable=False),
        sa.Column("classification", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.CheckConstraint("contract_version > 0", name="ck_outbox_contract_version"),
        sa.CheckConstraint("payload_version > 0", name="ck_outbox_payload_version"),
        sa.CheckConstraint("status = 'PENDENTE'", name="ck_outbox_initial_status"),
        sa.ForeignKeyConstraint(
            ["causation_id", "record_owner_organization_id"],
            [
                "core_audit.domain_events.event_id",
                "core_audit.domain_events.record_owner_organization_id",
            ],
            name="fk_outbox_causation_event_owner",
        ),
        sa.PrimaryKeyConstraint("message_id", name="pk_outbox_messages"),
        schema=SCHEMA,
        comment="titan.classification=PROTECTED;titan.module_owner=core_audit",
    )
    context = (
        "record_owner_organization_id = "
        "NULLIF(current_setting('titan.organization_id', true), '')::uuid"
    )
    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{TABLE} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{TABLE} FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            f"CREATE POLICY {TABLE}_select_by_owner ON {SCHEMA}.{TABLE} "
            f"FOR SELECT USING ({context})"
        )
    )
    op.execute(
        sa.text(
            f"CREATE POLICY {TABLE}_insert_by_owner ON {SCHEMA}.{TABLE} "
            f"FOR INSERT WITH CHECK ({context})"
        )
    )
    op.execute(sa.text(f"REVOKE ALL ON {SCHEMA}.{TABLE} FROM PUBLIC"))


def downgrade() -> None:
    for operation in ("insert", "select"):
        op.execute(sa.text(f"DROP POLICY {TABLE}_{operation}_by_owner ON {SCHEMA}.{TABLE}"))
    op.drop_table(TABLE, schema=SCHEMA)
    op.drop_constraint(
        "uq_domain_events_event_owner", "domain_events", schema=SCHEMA, type_="unique"
    )
