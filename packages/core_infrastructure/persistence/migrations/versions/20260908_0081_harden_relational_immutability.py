"""Harden relational immutability for historical records.

Revision ID: 20260908_0081
Revises: 20260907_0080
Create Date: 2026-09-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260908_0081"
down_revision: str | None = "20260907_0080"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "core_audit"
OWNER_CONTEXT = (
    "record_owner_organization_id = "
    "NULLIF(current_setting('titan.organization_id', true), '')::uuid"
)

# ADR-0076. Evidence remains outside this list until its mutable lifecycle is
# split into append-only records by FINDING-002 Part B.
IMMUTABLE_TABLES = (
    "ai_explanation_audit_records",
    "animal_exits",
    "animal_movement_items",
    "animal_movements",
    "attachments",
    "coverage_contributions",
    "decision_authority_profiles",
    "decision_contestations",
    "decision_overrides",
    "decision_proposals",
    "decision_reviews",
    "decisions",
    "domain_event_integrity",
    "domain_events",
    "dossiers",
    "establishment_qualification_assertions",
    "establishment_qualifications",
    "evaluations",
    "evidence_verifications",
    "external_counterparties",
    "external_source_capture_artifacts",
    "external_source_capture_association_reviews",
    "imported_livestock_facts",
    "integrity_checkpoint_events",
    "integrity_checkpoints",
    "internal_test_normative_bases",
    "market_supply_query_audit_records",
    "medication_batches",
    "medication_classification_assertions",
    "medications",
    "offline_operations",
    "outbox_messages",
    "outbox_publication_attempts",
    "prescription_targets",
    "prescriptions",
    "property_environmental_embargo_assertions",
    "property_geometries",
    "qualification_source_artifacts",
    "recalls",
    "received_transfer_artifacts",
    "reproductive_event_offspring",
    "reproductive_events",
    "rural_properties",
    "rule_identities",
    "rule_timeline_events",
    "sanitary_campaigns",
    "shared_policy_access_log",
    "synchronization_results",
    "temporal_anchors",
    "territorial_source_captures",
    "timestamp_attempts",
    "timestamp_validations",
    "traceable_items",
    "transformation_events",
    "treatment_applications",
)


def _drop_mutating_policies(table: str) -> None:
    op.execute(
        sa.text(
            f"""
            DO $$
            DECLARE policy_name text;
            BEGIN
                FOR policy_name IN
                    SELECT policyname FROM pg_policies
                    WHERE schemaname = '{SCHEMA}'
                      AND tablename = '{table}'
                      AND cmd IN ('ALL', 'UPDATE', 'DELETE')
                LOOP
                    EXECUTE format(
                        'DROP POLICY %I ON {SCHEMA}.{table}', policy_name
                    );
                END LOOP;
            END
            $$
            """
        )
    )


def _ensure_owner_policy(table: str, operation: str) -> None:
    policy = f"{table}_{operation.lower()}_by_owner"
    clause = (
        f"FOR SELECT USING ({OWNER_CONTEXT})"
        if operation == "SELECT"
        else f"FOR INSERT WITH CHECK ({OWNER_CONTEXT})"
    )
    op.execute(
        sa.text(
            f"""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_policies
                    WHERE schemaname = '{SCHEMA}'
                      AND tablename = '{table}'
                      AND policyname = '{policy}'
                ) THEN
                    CREATE POLICY {policy} ON {SCHEMA}.{table} {clause};
                END IF;
            END
            $$
            """
        )
    )


def upgrade() -> None:
    op.execute(
        sa.text(
            f"""
            CREATE FUNCTION {SCHEMA}.reject_historical_mutation()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                RAISE EXCEPTION 'REGISTRO_HISTORICO_IMUTAVEL: %.%',
                    TG_TABLE_SCHEMA, TG_TABLE_NAME USING ERRCODE = '55000';
            END;
            $$
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            CREATE FUNCTION {SCHEMA}.enforce_animal_version_transition()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                IF TG_OP <> 'UPDATE'
                   OR NEW.version <> OLD.version + 1
                   OR (to_jsonb(NEW) - 'version') IS DISTINCT FROM
                      (to_jsonb(OLD) - 'version') THEN
                    RAISE EXCEPTION 'TRANSICAO_DE_ANIMAL_INVALIDA'
                        USING ERRCODE = '55000';
                END IF;
                RETURN NEW;
            END;
            $$
            """
        )
    )

    for table in IMMUTABLE_TABLES:
        _drop_mutating_policies(table)
        _ensure_owner_policy(table, "SELECT")
        _ensure_owner_policy(table, "INSERT")
        op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{table} ENABLE ROW LEVEL SECURITY"))
        op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{table} FORCE ROW LEVEL SECURITY"))
        op.execute(
            sa.text(
                f"CREATE TRIGGER {table}_reject_update_delete "
                f"BEFORE UPDATE OR DELETE ON {SCHEMA}.{table} FOR EACH ROW "
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

    _drop_mutating_policies("animals")
    _ensure_owner_policy("animals", "SELECT")
    _ensure_owner_policy("animals", "INSERT")
    op.execute(
        sa.text(
            f"CREATE POLICY animals_update_version_by_owner ON {SCHEMA}.animals "
            f"FOR UPDATE USING ({OWNER_CONTEXT}) WITH CHECK ({OWNER_CONTEXT})"
        )
    )
    op.execute(
        sa.text(
            f"CREATE TRIGGER animals_enforce_version_update BEFORE UPDATE "
            f"ON {SCHEMA}.animals FOR EACH ROW "
            f"EXECUTE FUNCTION {SCHEMA}.enforce_animal_version_transition()"
        )
    )
    op.execute(
        sa.text(
            f"CREATE TRIGGER animals_reject_delete BEFORE DELETE ON {SCHEMA}.animals "
            f"FOR EACH ROW EXECUTE FUNCTION {SCHEMA}.reject_historical_mutation()"
        )
    )
    op.execute(
        sa.text(
            f"CREATE TRIGGER animals_reject_truncate BEFORE TRUNCATE ON {SCHEMA}.animals "
            f"FOR EACH STATEMENT EXECUTE FUNCTION {SCHEMA}.reject_historical_mutation()"
        )
    )


def downgrade() -> None:
    for trigger in (
        "animals_reject_truncate",
        "animals_reject_delete",
        "animals_enforce_version_update",
    ):
        op.execute(sa.text(f"DROP TRIGGER {trigger} ON {SCHEMA}.animals"))
    op.execute(
        sa.text(f"DROP POLICY IF EXISTS animals_update_version_by_owner ON {SCHEMA}.animals")
    )

    for table in reversed(IMMUTABLE_TABLES):
        op.execute(sa.text(f"DROP TRIGGER {table}_reject_truncate ON {SCHEMA}.{table}"))
        op.execute(sa.text(f"DROP TRIGGER {table}_reject_update_delete ON {SCHEMA}.{table}"))

    op.execute(sa.text(f"DROP FUNCTION {SCHEMA}.enforce_animal_version_transition()"))
    op.execute(sa.text(f"DROP FUNCTION {SCHEMA}.reject_historical_mutation()"))
