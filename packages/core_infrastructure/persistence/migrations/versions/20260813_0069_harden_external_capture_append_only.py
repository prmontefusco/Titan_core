"""Impõe append-only e coerência de tenant às capturas externas.

Revision ID: 20260813_0069
Revises: 20260812_0068
"""

import sqlalchemy as sa
from alembic import op

revision = "20260813_0069"
down_revision = "20260812_0068"
branch_labels = None
depends_on = None

SCHEMA = "core_audit"
ARTIFACTS = "external_source_capture_artifacts"
REVIEWS = "external_source_capture_association_reviews"
ANIMALS = "animals"


def _replace_with_append_only_policies(table: str) -> None:
    context = (
        "record_owner_organization_id = "
        "NULLIF(current_setting('titan.organization_id', true), '')::uuid"
    )
    op.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {SCHEMA}.{table}"))
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


def _restore_tenant_policy(table: str) -> None:
    context = (
        "record_owner_organization_id = "
        "NULLIF(current_setting('titan.organization_id', true), '')::uuid"
    )
    op.execute(sa.text(f"DROP POLICY IF EXISTS {table}_insert_by_owner ON {SCHEMA}.{table}"))
    op.execute(sa.text(f"DROP POLICY IF EXISTS {table}_select_by_owner ON {SCHEMA}.{table}"))
    op.execute(
        sa.text(
            f"CREATE POLICY tenant_isolation_policy ON {SCHEMA}.{table} "
            f"USING ({context}) WITH CHECK ({context})"
        )
    )


def _drop_legacy_reference(reference_table: str) -> None:
    """Remove a FK simples criada sem nome explícito pela migration 0068."""
    op.execute(
        sa.text(
            f"""
            DO $$
            DECLARE constraint_name text;
            BEGIN
                SELECT conname INTO constraint_name
                FROM pg_constraint
                WHERE conrelid = '{SCHEMA}.{REVIEWS}'::regclass
                  AND contype = 'f'
                  AND confrelid = '{SCHEMA}.{reference_table}'::regclass;
                IF constraint_name IS NOT NULL THEN
                    EXECUTE format(
                        'ALTER TABLE {SCHEMA}.{REVIEWS} DROP CONSTRAINT %I', constraint_name
                    );
                END IF;
            END $$;
            """
        )
    )


def upgrade() -> None:
    _replace_with_append_only_policies(ARTIFACTS)
    _replace_with_append_only_policies(REVIEWS)

    op.create_unique_constraint(
        "uq_external_source_capture_artifacts_owner_artifact",
        ARTIFACTS,
        ["record_owner_organization_id", "artifact_id"],
        schema=SCHEMA,
    )
    op.create_unique_constraint(
        "uq_animals_owner_animal",
        ANIMALS,
        ["record_owner_organization_id", "animal_id"],
        schema=SCHEMA,
    )
    _drop_legacy_reference(ARTIFACTS)
    _drop_legacy_reference(ANIMALS)
    op.create_foreign_key(
        "fk_capture_reviews_capture_same_owner",
        REVIEWS,
        ARTIFACTS,
        ["record_owner_organization_id", "capture_artifact_id"],
        ["record_owner_organization_id", "artifact_id"],
        source_schema=SCHEMA,
        referent_schema=SCHEMA,
    )
    op.create_foreign_key(
        "fk_capture_reviews_animal_same_owner",
        REVIEWS,
        ANIMALS,
        ["record_owner_organization_id", "candidate_animal_id"],
        ["record_owner_organization_id", "animal_id"],
        source_schema=SCHEMA,
        referent_schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_constraint("fk_capture_reviews_animal_same_owner", REVIEWS, schema=SCHEMA)
    op.drop_constraint("fk_capture_reviews_capture_same_owner", REVIEWS, schema=SCHEMA)
    op.create_foreign_key(
        "fk_capture_reviews_animal",
        REVIEWS,
        ANIMALS,
        ["candidate_animal_id"],
        ["animal_id"],
        source_schema=SCHEMA,
        referent_schema=SCHEMA,
    )
    op.create_foreign_key(
        "fk_capture_reviews_capture",
        REVIEWS,
        ARTIFACTS,
        ["capture_artifact_id"],
        ["artifact_id"],
        source_schema=SCHEMA,
        referent_schema=SCHEMA,
    )
    op.drop_constraint("uq_animals_owner_animal", ANIMALS, schema=SCHEMA)
    op.drop_constraint(
        "uq_external_source_capture_artifacts_owner_artifact", ARTIFACTS, schema=SCHEMA
    )
    _restore_tenant_policy(REVIEWS)
    _restore_tenant_policy(ARTIFACTS)
