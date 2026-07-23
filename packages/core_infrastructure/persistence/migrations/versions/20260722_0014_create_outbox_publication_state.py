"""Criar estado operacional de publicacao da Outbox.

Revision ID: 20260722_0014
Revises: 20260722_0013
Create Date: 2026-07-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260722_0014"
down_revision: str | None = "20260722_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "core_audit"
OUTBOX_TABLE = "outbox_messages"
STATE_TABLE = "outbox_publication_state"
ATTEMPTS_TABLE = "outbox_publication_attempts"


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_outbox_messages_message_owner",
        OUTBOX_TABLE,
        ["message_id", "record_owner_organization_id"],
        schema=SCHEMA,
    )
    op.create_table(
        STATE_TABLE,
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("claim_token", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("publisher_id", sa.String(100), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("broker_accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_result_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_reason", sa.String(200), nullable=True),
        sa.CheckConstraint(
            "attempt_count >= 0",
            name="ck_outbox_publication_attempt_count",
        ),
        sa.CheckConstraint(
            "status IN ('CLAIMED', 'ACEITA_PELO_BROKER', "
            "'RESULTADO_DESCONHECIDO', 'REJEITADA_PELO_BROKER')",
            name="ck_outbox_publication_status",
        ),
        sa.ForeignKeyConstraint(
            ["message_id", "record_owner_organization_id"],
            [
                "core_audit.outbox_messages.message_id",
                "core_audit.outbox_messages.record_owner_organization_id",
            ],
            name="fk_outbox_publication_state_message_owner",
        ),
        sa.PrimaryKeyConstraint("message_id", name="pk_outbox_publication_state"),
        schema=SCHEMA,
        comment="titan.classification=PROTECTED;titan.module_owner=core_audit",
    )
    op.create_table(
        ATTEMPTS_TABLE,
        sa.Column("attempt_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("claim_token", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("publisher_id", sa.String(100), nullable=False),
        sa.Column("result", sa.String(30), nullable=False),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(200), nullable=True),
        sa.CheckConstraint(
            "result IN ('ACEITA_PELO_BROKER', 'RESULTADO_DESCONHECIDO', 'REJEITADA_PELO_BROKER')",
            name="ck_outbox_publication_attempt_result",
        ),
        sa.ForeignKeyConstraint(
            ["message_id", "record_owner_organization_id"],
            [
                "core_audit.outbox_messages.message_id",
                "core_audit.outbox_messages.record_owner_organization_id",
            ],
            name="fk_outbox_publication_attempt_message_owner",
        ),
        sa.PrimaryKeyConstraint("attempt_id", name="pk_outbox_publication_attempts"),
        sa.UniqueConstraint(
            "message_id",
            "claim_token",
            "result",
            name="uq_outbox_publication_attempt_claim_result",
        ),
        schema=SCHEMA,
        comment="titan.classification=PROTECTED;titan.module_owner=core_audit",
    )
    for table in (STATE_TABLE, ATTEMPTS_TABLE):
        context = (
            "record_owner_organization_id = "
            "NULLIF(current_setting('titan.organization_id', true), '')::uuid"
        )
        op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{table} ENABLE ROW LEVEL SECURITY"))
        op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{table} FORCE ROW LEVEL SECURITY"))
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
        op.execute(
            sa.text(
                f"CREATE POLICY {table}_update_by_owner ON {SCHEMA}.{table} "
                f"FOR UPDATE USING ({context}) WITH CHECK ({context})"
            )
        )
        op.execute(sa.text(f"REVOKE ALL ON {SCHEMA}.{table} FROM PUBLIC"))


def downgrade() -> None:
    for table in (ATTEMPTS_TABLE, STATE_TABLE):
        for operation in ("update", "insert", "select"):
            op.execute(sa.text(f"DROP POLICY {table}_{operation}_by_owner ON {SCHEMA}.{table}"))
        op.drop_table(table, schema=SCHEMA)
    op.drop_constraint(
        "uq_outbox_messages_message_owner",
        OUTBOX_TABLE,
        schema=SCHEMA,
        type_="unique",
    )
