"""Add operational expiration to idempotency records.

Revision ID: 20260909_0086
Revises: 20260909_0085
Create Date: 2026-09-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260909_0086"
down_revision: str | None = "20260909_0085"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "core_audit"
TABLE = "idempotency_records"
RETENTION_INTERVAL = "30 days"


def upgrade() -> None:
    op.add_column(
        TABLE,
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        schema=SCHEMA,
    )
    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{TABLE} DISABLE TRIGGER idempotency_completion_only"))
    op.execute(
        sa.text(
            f"""
            UPDATE {SCHEMA}.{TABLE}
            SET expires_at = requested_at + INTERVAL '{RETENTION_INTERVAL}'
            WHERE expires_at IS NULL
            """
        )
    )
    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{TABLE} ENABLE TRIGGER idempotency_completion_only"))
    op.alter_column(TABLE, "expires_at", nullable=False, schema=SCHEMA)
    op.create_check_constraint(
        "ck_idempotency_expires_after_request",
        TABLE,
        "expires_at > requested_at",
        schema=SCHEMA,
    )
    op.create_index(
        "ix_idempotency_records_expired_completed",
        TABLE,
        ["expires_at"],
        schema=SCHEMA,
        postgresql_where=sa.text("status = 'CONCLUIDA'"),
    )
    op.execute(
        sa.text(
            f"""
            CREATE OR REPLACE FUNCTION {SCHEMA}.enforce_idempotency_completion_only()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                IF OLD.status <> 'EM_PROCESSAMENTO' OR NEW.status <> 'CONCLUIDA'
                   OR NEW.idempotency_record_id <> OLD.idempotency_record_id
                   OR NEW.record_owner_organization_id <> OLD.record_owner_organization_id
                   OR NEW.idempotency_key <> OLD.idempotency_key
                   OR NEW.principal_type <> OLD.principal_type
                   OR NEW.principal_id <> OLD.principal_id
                   OR NEW.purpose <> OLD.purpose
                   OR NEW.operation <> OLD.operation
                   OR NEW.intent_digest <> OLD.intent_digest
                   OR NEW.requested_at <> OLD.requested_at
                   OR NEW.expires_at <> OLD.expires_at THEN
                    RAISE EXCEPTION 'TRANSICAO_DE_IDEMPOTENCIA_INVALIDA';
                END IF;
                RETURN NEW;
            END;
            $$;
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            f"""
            CREATE OR REPLACE FUNCTION {SCHEMA}.enforce_idempotency_completion_only()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                IF OLD.status <> 'EM_PROCESSAMENTO' OR NEW.status <> 'CONCLUIDA'
                   OR NEW.idempotency_record_id <> OLD.idempotency_record_id
                   OR NEW.record_owner_organization_id <> OLD.record_owner_organization_id
                   OR NEW.idempotency_key <> OLD.idempotency_key
                   OR NEW.principal_type <> OLD.principal_type
                   OR NEW.principal_id <> OLD.principal_id
                   OR NEW.purpose <> OLD.purpose
                   OR NEW.operation <> OLD.operation
                   OR NEW.intent_digest <> OLD.intent_digest
                   OR NEW.requested_at <> OLD.requested_at THEN
                    RAISE EXCEPTION 'TRANSICAO_DE_IDEMPOTENCIA_INVALIDA';
                END IF;
                RETURN NEW;
            END;
            $$;
            """
        )
    )
    op.drop_index("ix_idempotency_records_expired_completed", table_name=TABLE, schema=SCHEMA)
    op.drop_constraint("ck_idempotency_expires_after_request", TABLE, schema=SCHEMA)
    op.drop_column(TABLE, "expires_at", schema=SCHEMA)
