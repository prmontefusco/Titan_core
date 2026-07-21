"""Criar event store append-only.

Revision ID: 20260721_0008
Revises: 20260721_0007
Create Date: 2026-07-21

Classificação: PROTECTED
Módulo owner: core_audit
Decisões: ADRs 0003 e 0007
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260721_0008"
down_revision: str | None = "20260721_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "core_audit"
TABLE = "domain_events"


def upgrade() -> None:
    op.execute(sa.text(f"CREATE SCHEMA {SCHEMA}"))
    op.execute(sa.text(f"REVOKE ALL ON SCHEMA {SCHEMA} FROM PUBLIC"))
    op.create_table(
        TABLE,
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("aggregate_type", sa.String(length=100), nullable=False),
        sa.Column("aggregate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("aggregate_contract_version", sa.Integer(), nullable=False),
        sa.Column("aggregate_version", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("event_version", sa.Integer(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_type", sa.String(length=100), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_organization_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_contract_version", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(length=100), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_organization_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_contract_version", sa.Integer(), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("causation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("payload_schema", sa.String(length=100), nullable=False),
        sa.Column("payload_version", sa.Integer(), nullable=False),
        sa.Column("payload_canonical_bytes", sa.LargeBinary(), nullable=False),
        sa.CheckConstraint("aggregate_contract_version > 0", name="ck_events_aggregate_contract"),
        sa.CheckConstraint("aggregate_version > 0", name="ck_events_aggregate_version"),
        sa.CheckConstraint("event_version > 0", name="ck_events_event_version"),
        sa.CheckConstraint("actor_contract_version > 0", name="ck_events_actor_contract"),
        sa.CheckConstraint("source_contract_version > 0", name="ck_events_source_contract"),
        sa.CheckConstraint("payload_version > 0", name="ck_events_payload_version"),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_domain_events_owner",
        ),
        sa.PrimaryKeyConstraint("event_id", name="pk_domain_events"),
        sa.UniqueConstraint(
            "record_owner_organization_id",
            "aggregate_type",
            "aggregate_id",
            "aggregate_version",
            name="uq_domain_events_aggregate_version",
        ),
        schema=SCHEMA,
    )
    op.execute(
        sa.text(
            "COMMENT ON TABLE core_audit.domain_events IS "
            "'titan.classification=PROTECTED;titan.module_owner=core_audit'"
        )
    )
    op.execute(sa.text("ALTER TABLE core_audit.domain_events ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text("ALTER TABLE core_audit.domain_events FORCE ROW LEVEL SECURITY"))
    context = (
        "record_owner_organization_id = "
        "NULLIF(current_setting('titan.organization_id', true), '')::uuid"
    )
    op.execute(
        sa.text(
            "CREATE POLICY domain_events_select_by_owner ON core_audit.domain_events "
            f"FOR SELECT USING ({context})"
        )
    )
    op.execute(
        sa.text(
            "CREATE POLICY domain_events_insert_by_owner ON core_audit.domain_events "
            f"FOR INSERT WITH CHECK ({context})"
        )
    )
    op.execute(sa.text("REVOKE ALL ON core_audit.domain_events FROM PUBLIC"))


def downgrade() -> None:
    op.execute(sa.text("DROP POLICY domain_events_insert_by_owner ON core_audit.domain_events"))
    op.execute(sa.text("DROP POLICY domain_events_select_by_owner ON core_audit.domain_events"))
    op.drop_table(TABLE, schema=SCHEMA)
    op.execute(sa.text(f"DROP SCHEMA {SCHEMA}"))
