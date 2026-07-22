"""Criar registro autoritativo de idempotência.

Revision ID: 20260722_0012
Revises: 20260721_0011
Create Date: 2026-07-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260722_0012"
down_revision: str | None = "20260721_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "core_audit"
TABLE = "idempotency_records"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("idempotency_record_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("principal_type", sa.String(100), nullable=False),
        sa.Column("principal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("purpose", sa.String(100), nullable=False),
        sa.Column("operation", sa.String(100), nullable=False),
        sa.Column("intent_digest", sa.LargeBinary(), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("result_schema", sa.String(100), nullable=True),
        sa.Column("result_version", sa.Integer(), nullable=True),
        sa.Column("result_canonical_bytes", sa.LargeBinary(), nullable=True),
        sa.CheckConstraint("octet_length(intent_digest) = 32", name="ck_idempotency_intent_digest"),
        sa.CheckConstraint(
            "status IN ('EM_PROCESSAMENTO', 'CONCLUIDA')", name="ck_idempotency_status"
        ),
        sa.CheckConstraint(
            "(status = 'EM_PROCESSAMENTO' AND result_schema IS NULL AND result_version IS NULL "
            "AND result_canonical_bytes IS NULL) OR (status = 'CONCLUIDA' AND result_schema IS NOT NULL "
            "AND result_version > 0 AND result_canonical_bytes IS NOT NULL)",
            name="ck_idempotency_result_state",
        ),
        sa.PrimaryKeyConstraint("idempotency_record_id", name="pk_idempotency_records"),
        sa.UniqueConstraint(
            "record_owner_organization_id",
            "principal_type",
            "principal_id",
            "purpose",
            "operation",
            "idempotency_key",
            name="uq_idempotency_semantic_scope",
        ),
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
    op.execute(
        sa.text(
            f"CREATE POLICY {TABLE}_update_by_owner ON {SCHEMA}.{TABLE} "
            f"FOR UPDATE USING ({context}) WITH CHECK ({context})"
        )
    )
    op.execute(
        sa.text(
            f"""
            CREATE FUNCTION {SCHEMA}.enforce_idempotency_completion_only()
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
            $$
            """
        )
    )
    op.execute(
        sa.text(
            f"CREATE TRIGGER idempotency_completion_only BEFORE UPDATE ON {SCHEMA}.{TABLE} "
            f"FOR EACH ROW EXECUTE FUNCTION {SCHEMA}.enforce_idempotency_completion_only()"
        )
    )
    op.execute(sa.text(f"REVOKE ALL ON {SCHEMA}.{TABLE} FROM PUBLIC"))


def downgrade() -> None:
    for operation in ("update", "insert", "select"):
        op.execute(sa.text(f"DROP POLICY {TABLE}_{operation}_by_owner ON {SCHEMA}.{TABLE}"))
    op.drop_table(TABLE, schema=SCHEMA)
    op.execute(sa.text(f"DROP FUNCTION {SCHEMA}.enforce_idempotency_completion_only()"))
