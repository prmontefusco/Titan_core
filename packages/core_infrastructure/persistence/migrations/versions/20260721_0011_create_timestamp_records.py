"""Criar tentativas, validações e âncoras temporais separadas.

Revision ID: 20260721_0011
Revises: 20260721_0010
Create Date: 2026-07-21

Classificação: PROTECTED
Módulo owner: core_audit
Decisão: ADR 0007
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260721_0011"
down_revision: str | None = "20260721_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "core_audit"
TABLES = ("timestamp_attempts", "timestamp_validations", "temporal_anchors")


def _protect(table: str) -> None:
    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{table} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{table} FORCE ROW LEVEL SECURITY"))
    context = "record_owner_organization_id = NULLIF(current_setting('titan.organization_id', true), '')::uuid"
    op.execute(
        sa.text(
            f"CREATE POLICY {table}_select_by_owner ON {SCHEMA}.{table} FOR SELECT USING ({context})"
        )
    )
    op.execute(
        sa.text(
            f"CREATE POLICY {table}_insert_by_owner ON {SCHEMA}.{table} FOR INSERT WITH CHECK ({context})"
        )
    )
    op.execute(sa.text(f"REVOKE ALL ON {SCHEMA}.{table} FROM PUBLIC"))


def upgrade() -> None:
    op.create_table(
        "timestamp_attempts",
        sa.Column("attempt_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("checkpoint_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message_imprint", sa.LargeBinary(), nullable=False),
        sa.Column("digest_algorithm", sa.String(30), nullable=False),
        sa.Column("policy", sa.String(200), nullable=False),
        sa.Column("nonce", sa.LargeBinary(), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("provider_id", sa.String(100), nullable=False),
        sa.Column("raw_token", sa.LargeBinary(), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("octet_length(message_imprint) = 32", name="ck_attempts_imprint"),
        sa.CheckConstraint("octet_length(nonce) >= 16", name="ck_attempts_nonce"),
        sa.CheckConstraint(
            "status IN ('PENDENTE', 'RESULTADO_DESCONHECIDO', 'TOKEN_RECEBIDO')",
            name="ck_attempts_status",
        ),
        sa.CheckConstraint(
            "(status = 'TOKEN_RECEBIDO' AND raw_token IS NOT NULL AND received_at IS NOT NULL) OR (status <> 'TOKEN_RECEBIDO' AND raw_token IS NULL AND received_at IS NULL)",
            name="ck_attempts_token_state",
        ),
        sa.ForeignKeyConstraint(
            ["checkpoint_id"],
            ["core_audit.integrity_checkpoints.checkpoint_id"],
            name="fk_timestamp_attempts_checkpoint",
        ),
        sa.PrimaryKeyConstraint("attempt_id", name="pk_timestamp_attempts"),
        schema=SCHEMA,
    )
    op.create_table(
        "timestamp_validations",
        sa.Column("validation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("attempt_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("reason_code", sa.String(100), nullable=False),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("proved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("token_digest", sa.LargeBinary(), nullable=False),
        sa.CheckConstraint(
            "status IN ('VALIDO', 'INVALIDO', 'INDETERMINADO')", name="ck_validations_status"
        ),
        sa.CheckConstraint("octet_length(token_digest) = 32", name="ck_validations_digest"),
        sa.CheckConstraint(
            "(status = 'VALIDO' AND proved_at IS NOT NULL) OR status <> 'VALIDO'",
            name="ck_validations_proved_at",
        ),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["core_audit.timestamp_attempts.attempt_id"],
            name="fk_timestamp_validations_attempt",
        ),
        sa.PrimaryKeyConstraint("validation_id", name="pk_timestamp_validations"),
        schema=SCHEMA,
    )
    op.create_table(
        "temporal_anchors",
        sa.Column("anchor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("checkpoint_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("attempt_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("validation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message_imprint", sa.LargeBinary(), nullable=False),
        sa.Column("proved_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("octet_length(message_imprint) = 32", name="ck_anchors_imprint"),
        sa.ForeignKeyConstraint(
            ["checkpoint_id"],
            ["core_audit.integrity_checkpoints.checkpoint_id"],
            name="fk_temporal_anchors_checkpoint",
        ),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["core_audit.timestamp_attempts.attempt_id"],
            name="fk_temporal_anchors_attempt",
        ),
        sa.ForeignKeyConstraint(
            ["validation_id"],
            ["core_audit.timestamp_validations.validation_id"],
            name="fk_temporal_anchors_validation",
        ),
        sa.PrimaryKeyConstraint("anchor_id", name="pk_temporal_anchors"),
        sa.UniqueConstraint("validation_id", name="uq_temporal_anchors_validation"),
        schema=SCHEMA,
    )
    for table in TABLES:
        op.execute(
            sa.text(
                f"COMMENT ON TABLE {SCHEMA}.{table} IS 'titan.classification=PROTECTED;titan.module_owner=core_audit'"
            )
        )
        _protect(table)


def downgrade() -> None:
    for table in reversed(TABLES):
        op.execute(sa.text(f"DROP POLICY {table}_insert_by_owner ON {SCHEMA}.{table}"))
        op.execute(sa.text(f"DROP POLICY {table}_select_by_owner ON {SCHEMA}.{table}"))
        op.drop_table(table, schema=SCHEMA)
