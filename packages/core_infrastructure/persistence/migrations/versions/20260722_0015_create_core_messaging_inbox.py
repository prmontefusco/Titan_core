"""Criar schema core_messaging e tabelas da Inbox.

Revision ID: 20260722_0015
Revises: 20260722_0014
Create Date: 2026-07-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260722_0015"
down_revision: str | None = "20260722_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "core_messaging"
INBOX_TABLE = "inbox_messages"
ATTEMPTS_TABLE = "inbox_delivery_attempts"
CONFLICTS_TABLE = "inbox_conflicts"
UNTRUSTED_QUARANTINE_TABLE = "untrusted_message_quarantine"


def upgrade() -> None:
    op.execute(sa.text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}"))

    op.create_table(
        INBOX_TABLE,
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message_type", sa.String(100), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("semantic_operation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("producer_identity", sa.String(100), nullable=False),
        sa.Column("semantic_message_digest", sa.LargeBinary(), nullable=False),
        sa.Column("authorization_evaluation_mode", sa.String(50), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completion_result_code", sa.String(30), nullable=True),
        sa.Column("effect_reference", sa.String(200), nullable=True),
        sa.Column("decision_reference", sa.String(200), nullable=True),
        sa.Column("result_digest", sa.LargeBinary(), nullable=True),
        sa.CheckConstraint("schema_version > 0", name="ck_inbox_schema_version"),
        sa.CheckConstraint("attempt_number >= 1", name="ck_inbox_attempt_number"),
        sa.CheckConstraint(
            "status IN ('EM_PROCESSAMENTO', 'AGUARDANDO_RETRY', 'CONCLUIDA', "
            "'EM_QUARENTENA', 'RECONCILIACAO_PENDENTE')",
            name="ck_inbox_status",
        ),
        sa.CheckConstraint(
            "completion_result_code IS NULL OR completion_result_code IN "
            "('SUCCESS', 'BUSINESS_REJECTION', 'NO_OP', 'AUTHORIZATION_REJECTED')",
            name="ck_inbox_completion_result_code",
        ),
        sa.PrimaryKeyConstraint("message_id", name="pk_inbox_messages"),
        sa.UniqueConstraint(
            "message_id",
            "record_owner_organization_id",
            name="uq_inbox_messages_message_owner",
        ),
        schema=SCHEMA,
        comment="titan.classification=PROTECTED;titan.module_owner=core_messaging",
    )

    op.create_table(
        ATTEMPTS_TABLE,
        sa.Column("attempt_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("consumer_id", sa.String(100), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("handling_result", sa.String(30), nullable=False),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(200), nullable=True),
        sa.CheckConstraint("attempt_number >= 1", name="ck_inbox_attempts_number"),
        sa.CheckConstraint(
            "handling_result IN ('PROCESSED', 'DUPLICATE_RECOVERED', "
            "'RETRY_SCHEDULED', 'CONFLICT_DETECTED', 'QUARANTINED')",
            name="ck_inbox_attempts_handling_result",
        ),
        sa.ForeignKeyConstraint(
            ["message_id", "record_owner_organization_id"],
            [
                f"{SCHEMA}.{INBOX_TABLE}.message_id",
                f"{SCHEMA}.{INBOX_TABLE}.record_owner_organization_id",
            ],
            name="fk_inbox_attempts_message_owner",
        ),
        sa.PrimaryKeyConstraint("attempt_id", name="pk_inbox_delivery_attempts"),
        schema=SCHEMA,
        comment="titan.classification=PROTECTED;titan.module_owner=core_messaging",
    )

    op.create_table(
        CONFLICTS_TABLE,
        sa.Column("conflict_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("received_digest", sa.LargeBinary(), nullable=False),
        sa.Column("expected_digest", sa.LargeBinary(), nullable=False),
        sa.Column(
            "handling_result", sa.String(30), nullable=False, server_default="CONFLICT_DETECTED"
        ),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["message_id", "record_owner_organization_id"],
            [
                f"{SCHEMA}.{INBOX_TABLE}.message_id",
                f"{SCHEMA}.{INBOX_TABLE}.record_owner_organization_id",
            ],
            name="fk_inbox_conflicts_message_owner",
        ),
        sa.PrimaryKeyConstraint("conflict_id", name="pk_inbox_conflicts"),
        schema=SCHEMA,
        comment="titan.classification=PROTECTED;titan.module_owner=core_messaging",
    )

    op.create_table(
        UNTRUSTED_QUARANTINE_TABLE,
        sa.Column("quarantine_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("alleged_producer", sa.String(100), nullable=True),
        sa.Column("alleged_organization", sa.String(100), nullable=True),
        sa.Column("received_bytes_digest", sa.LargeBinary(), nullable=False),
        sa.Column("rejection_reason_code", sa.String(50), nullable=False),
        sa.Column("sanitized_routing_metadata", sa.String(200), nullable=True),
        sa.Column("quarantined_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("quarantine_id", name="pk_untrusted_message_quarantine"),
        schema=SCHEMA,
        comment="titan.classification=PROTECTED;titan.module_owner=core_messaging",
    )

    for table in (INBOX_TABLE, ATTEMPTS_TABLE, CONFLICTS_TABLE):
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

    op.execute(sa.text(f"REVOKE ALL ON {SCHEMA}.{UNTRUSTED_QUARANTINE_TABLE} FROM PUBLIC"))


def downgrade() -> None:
    op.drop_table(UNTRUSTED_QUARANTINE_TABLE, schema=SCHEMA)
    for table in (CONFLICTS_TABLE, ATTEMPTS_TABLE, INBOX_TABLE):
        for operation in ("update", "insert", "select"):
            op.execute(sa.text(f"DROP POLICY {table}_{operation}_by_owner ON {SCHEMA}.{table}"))
        op.drop_table(table, schema=SCHEMA)
    op.execute(sa.text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
