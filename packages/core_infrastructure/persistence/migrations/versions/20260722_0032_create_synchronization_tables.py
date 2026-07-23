"""Criar tabelas de sincronização offline com suporte a RLS.

Revision ID: 20260722_0032
Revises: 20260722_0031
Create Date: 2026-07-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260722_0032"
down_revision: str | None = "20260722_0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "core_audit"
OPERATIONS_TABLE = "offline_operations"
RESULTS_TABLE = "synchronization_results"
BATCHES_TABLE = "synchronization_batches"

_TABLES = (OPERATIONS_TABLE, RESULTS_TABLE, BATCHES_TABLE)


def upgrade() -> None:
    op.create_table(
        OPERATIONS_TABLE,
        sa.Column("operation_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("device_contract_version", sa.Integer(), nullable=False),
        sa.Column("actor_entity_type", sa.String(length=100), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_contract_version", sa.Integer(), nullable=False),
        sa.Column("semantic_identity", sa.String(length=255), nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("operation_type", sa.String(length=100), nullable=False),
        sa.Column("contract_version", sa.Integer(), nullable=False),
        sa.Column("local_sequence", sa.Integer(), nullable=False),
        sa.Column("intent_digest", sa.String(length=64), nullable=False),
        sa.Column("client_observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claimed_occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timezone_name", sa.String(length=100), nullable=False),
        sa.Column("time_confidence", sa.String(length=40), nullable=False),
        sa.Column(
            "monotonic_continuity_id",
            sa.String(length=100),
            nullable=False,
            server_default="",
        ),
        sa.Column("monotonic_elapsed_ms", sa.BigInteger(), nullable=True),
        sa.Column("last_server_contact_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payload_schema", sa.String(length=100), nullable=False),
        sa.Column("payload_version", sa.Integer(), nullable=False),
        sa.Column("payload_canonical_bytes", sa.LargeBinary(), nullable=False),
        sa.Column(
            "depends_on",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "evidence_references",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("server_received_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("local_sequence >= 1", name="ck_offline_operations_local_sequence"),
        sa.CheckConstraint("contract_version >= 1", name="ck_offline_operations_contract_version"),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_offline_operations_organization",
        ),
        comment="titan.classification=PROTECTED;titan.module_owner=core_audit",
        schema=SCHEMA,
    )
    op.create_index(
        "ix_offline_operations_idempotency",
        OPERATIONS_TABLE,
        ["record_owner_organization_id", "idempotency_key", "server_received_at"],
        schema=SCHEMA,
    )

    op.create_table(
        RESULTS_TABLE,
        sa.Column("operation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "reason_codes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "produced_references",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("conflict", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "pending_dependencies",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("reconciliation_deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "limitations",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.PrimaryKeyConstraint("operation_id", "attempt", name="pk_synchronization_results"),
        sa.CheckConstraint("attempt >= 1", name="ck_synchronization_results_attempt"),
        # As três invariantes que o domínio já impõe são repetidas no banco: nem
        # escrita direta em SQL produz aceitação sem efeito, conflito mudo ou
        # resultado desconhecido sem prazo de reconciliação.
        sa.CheckConstraint(
            "status <> 'RESULTADO_DESCONHECIDO' OR reconciliation_deadline IS NOT NULL",
            name="ck_synchronization_results_reconciliation",
        ),
        sa.CheckConstraint(
            "(status = 'CONFLITANTE') = (conflict IS NOT NULL)",
            name="ck_synchronization_results_conflict",
        ),
        sa.CheckConstraint(
            "status <> 'ACEITA' OR jsonb_array_length(produced_references) > 0",
            name="ck_synchronization_results_efeito",
        ),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_synchronization_results_organization",
        ),
        comment="titan.classification=PROTECTED;titan.module_owner=core_audit",
        schema=SCHEMA,
    )
    op.create_index(
        "ix_synchronization_results_batch",
        RESULTS_TABLE,
        ["record_owner_organization_id", "batch_id"],
        schema=SCHEMA,
    )

    op.create_table(
        BATCHES_TABLE,
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("batch_version", sa.Integer(), nullable=False),
        sa.Column("manifest", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("manifest_digest", sa.String(length=64), nullable=False),
        sa.Column("operation_count", sa.Integer(), nullable=False),
        sa.Column("sequence_first", sa.Integer(), nullable=False),
        sa.Column("sequence_last", sa.Integer(), nullable=False),
        sa.Column("created_at_device", sa.DateTime(timezone=True), nullable=False),
        sa.Column("first_received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("state", sa.String(length=40), nullable=False),
        sa.Column("examined_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "counts",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "gaps",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "limitations",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("attempts >= 1", name="ck_synchronization_batches_attempts"),
        sa.CheckConstraint("operation_count >= 1", name="ck_synchronization_batches_count"),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_synchronization_batches_organization",
        ),
        comment="titan.classification=PROTECTED;titan.module_owner=core_audit",
        schema=SCHEMA,
    )

    for table in _TABLES:
        op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{table} ENABLE ROW LEVEL SECURITY"))
        op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{table} FORCE ROW LEVEL SECURITY"))
        op.execute(
            sa.text(
                f"""
                CREATE POLICY tenant_isolation_policy ON {SCHEMA}.{table}
                FOR ALL
                USING (
                    record_owner_organization_id = NULLIF(
                        current_setting('titan.organization_id', true),
                        ''
                    )::uuid
                )
                WITH CHECK (
                    record_owner_organization_id = NULLIF(
                        current_setting('titan.organization_id', true),
                        ''
                    )::uuid
                )
                """
            )
        )


def downgrade() -> None:
    for table in _TABLES:
        op.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {SCHEMA}.{table}"))
    op.drop_table(BATCHES_TABLE, schema=SCHEMA)
    op.drop_index("ix_synchronization_results_batch", table_name=RESULTS_TABLE, schema=SCHEMA)
    op.drop_table(RESULTS_TABLE, schema=SCHEMA)
    op.drop_index("ix_offline_operations_idempotency", table_name=OPERATIONS_TABLE, schema=SCHEMA)
    op.drop_table(OPERATIONS_TABLE, schema=SCHEMA)
