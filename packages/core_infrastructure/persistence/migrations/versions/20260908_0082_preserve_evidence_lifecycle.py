"""Preserve Evidence baseline and append-only lifecycle (ADR-0076).

Revision ID: 20260908_0082
Revises: 20260908_0081
Create Date: 2026-09-08
"""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260908_0082"
down_revision: str | None = "20260908_0081"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "core_audit"
NEW_LIFECYCLE_TABLES = ("evidence_signatures", "evidence_revocations")
LIFECYCLE_TABLES = (*NEW_LIFECYCLE_TABLES, "evidence_verifications")
OWNER_CONTEXT = (
    "record_owner_organization_id = "
    "NULLIF(current_setting('titan.organization_id', true), '')::uuid"
)


def _protect(table: str) -> None:
    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{table} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{table} FORCE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"REVOKE ALL ON {SCHEMA}.{table} FROM PUBLIC"))
    for operation, clause in (
        ("select", f"USING ({OWNER_CONTEXT})"),
        ("insert", f"WITH CHECK ({OWNER_CONTEXT})"),
    ):
        op.execute(
            sa.text(
                f"CREATE POLICY {table}_{operation}_by_owner ON {SCHEMA}.{table} "
                f"FOR {operation.upper()} {clause}"
            )
        )
    op.execute(
        sa.text(
            f"CREATE TRIGGER {table}_reject_update_delete BEFORE UPDATE OR DELETE "
            f"ON {SCHEMA}.{table} FOR EACH ROW "
            f"EXECUTE FUNCTION {SCHEMA}.reject_historical_mutation()"
        )
    )
    op.execute(
        sa.text(
            f"CREATE TRIGGER {table}_reject_truncate BEFORE TRUNCATE "
            f"ON {SCHEMA}.{table} FOR EACH STATEMENT "
            f"EXECUTE FUNCTION {SCHEMA}.reject_historical_mutation()"
        )
    )


def _create_lifecycle_table(table: str, identity: str, *columns: sa.Column[Any]) -> None:
    op.create_table(
        table,
        sa.Column(identity, postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evidence_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evidence_version", sa.Integer(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        *columns,
        sa.PrimaryKeyConstraint(identity, name=f"pk_{table}"),
        sa.CheckConstraint("evidence_version > 1", name=f"ck_{table}_version"),
        sa.UniqueConstraint("evidence_id", "evidence_version", name=f"uq_{table}_version"),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id", "evidence_id"],
            [f"{SCHEMA}.evidences.record_owner_organization_id", f"{SCHEMA}.evidences.evidence_id"],
            name=f"fk_{table}_owner_evidence",
        ),
        schema=SCHEMA,
        comment="titan.classification=PROTECTED;titan.module_owner=core_audit",
    )
    _protect(table)


def upgrade() -> None:
    # Preserve legacy columns as the known baseline, without inventing events.
    op.create_unique_constraint(
        "uq_evidences_owner_id",
        "evidences",
        ["record_owner_organization_id", "evidence_id"],
        schema=SCHEMA,
    )
    _create_lifecycle_table(
        "evidence_signatures",
        "signature_id",
        sa.Column("profile", sa.String(50), nullable=False),
        sa.Column("algorithm", sa.String(50), nullable=False),
        sa.Column("raw_bytes", sa.LargeBinary(), nullable=False),
        sa.Column("key_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("key_purpose", sa.String(100), nullable=False),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=False),
    )
    _create_lifecycle_table(
        "evidence_revocations",
        "revocation_id",
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoking_actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revoking_actor_org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revoking_actor_contract_version", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
    )
    op.create_unique_constraint(
        "uq_evidence_revocations_evidence", "evidence_revocations", ["evidence_id"], schema=SCHEMA
    )
    for name, datatype in (
        ("evidence_version", sa.Integer()),
        ("recorded_at", sa.DateTime(timezone=True)),
    ):
        op.add_column(
            "evidence_verifications",
            sa.Column(name, datatype, nullable=True),
            schema=SCHEMA,
        )
    op.create_unique_constraint(
        "uq_evidence_verifications_version",
        "evidence_verifications",
        ["evidence_id", "evidence_version"],
        schema=SCHEMA,
    )
    op.create_check_constraint(
        "ck_evidence_verifications_version",
        "evidence_verifications",
        "evidence_version IS NULL OR evidence_version > 1",
        schema=SCHEMA,
    )
    # Validate new writes immediately; do not relabel or rewrite legacy references.
    op.execute(
        sa.text(
            f"ALTER TABLE {SCHEMA}.evidence_verifications ADD CONSTRAINT "
            "fk_evidence_verifications_owner_evidence FOREIGN KEY "
            "(record_owner_organization_id, evidence_id) REFERENCES "
            f"{SCHEMA}.evidences (record_owner_organization_id, evidence_id) NOT VALID"
        )
    )
    op.execute(
        sa.text(f"""
        CREATE FUNCTION {SCHEMA}.enforce_evidence_lifecycle()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
            baseline record;
            last_version integer;
            last_recorded_at timestamptz;
        BEGIN
            PERFORM pg_advisory_xact_lock(hashtextextended(NEW.evidence_id::text, 0));
            SELECT version, registered_at, is_revoked INTO baseline
            FROM {SCHEMA}.evidences
            WHERE evidence_id = NEW.evidence_id
              AND record_owner_organization_id = NEW.record_owner_organization_id;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'EVIDENCE_LIFECYCLE_BASE_AUSENTE' USING ERRCODE = '23503';
            END IF;
            IF baseline.is_revoked OR EXISTS (
                SELECT 1 FROM {SCHEMA}.evidence_revocations
                WHERE evidence_id = NEW.evidence_id
            ) THEN
                RAISE EXCEPTION 'EVIDENCE_LIFECYCLE_REVOGADA' USING ERRCODE = '55000';
            END IF;
            SELECT greatest(baseline.version, coalesce(max(evidence_version), 0)),
                   greatest(baseline.registered_at, coalesce(max(recorded_at), baseline.registered_at))
              INTO last_version, last_recorded_at
            FROM (
                SELECT evidence_version, recorded_at FROM {SCHEMA}.evidence_signatures
                WHERE evidence_id = NEW.evidence_id
                UNION ALL
                SELECT evidence_version, recorded_at FROM {SCHEMA}.evidence_revocations
                WHERE evidence_id = NEW.evidence_id
                UNION ALL
                SELECT evidence_version, recorded_at FROM {SCHEMA}.evidence_verifications
                WHERE evidence_id = NEW.evidence_id
            ) lifecycle;
            IF NEW.evidence_version IS NULL OR NEW.evidence_version <> last_version + 1
               OR NEW.recorded_at IS NULL OR NEW.recorded_at < last_recorded_at THEN
                RAISE EXCEPTION 'EVIDENCE_LIFECYCLE_SEQUENCIA_INVALIDA' USING ERRCODE = '55000';
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    )
    for table in LIFECYCLE_TABLES:
        op.execute(
            sa.text(
                f"CREATE TRIGGER {table}_enforce_lifecycle BEFORE INSERT ON {SCHEMA}.{table} "
                f"FOR EACH ROW EXECUTE FUNCTION {SCHEMA}.enforce_evidence_lifecycle()"
            )
        )
    op.execute(
        sa.text(f"""
        DO $$ DECLARE policy_name text;
        BEGIN
            FOR policy_name IN SELECT policyname FROM pg_policies
                WHERE schemaname = '{SCHEMA}' AND tablename = 'evidences'
            LOOP
                EXECUTE format('DROP POLICY %I ON {SCHEMA}.evidences', policy_name);
            END LOOP;
        END $$
    """)
    )
    _protect("evidences")


def downgrade() -> None:
    # Reverting application code never authorizes dropping accumulated history.
    raise RuntimeError("EVIDENCE_LIFECYCLE_DOWNGRADE_DESTRUTIVO_NAO_PERMITIDO")
