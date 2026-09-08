"""Create AI Explanation audit records table.

Revision ID: 20260907_0080
Revises: 20260831_0079
Create Date: 2026-09-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260907_0080"
down_revision: str | None = "20260831_0079"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "core_audit"
TABLE = "ai_explanation_audit_records"

_RLS_OWNER_CONTEXT = (
    "record_owner_organization_id = "
    "NULLIF(current_setting('titan.organization_id', true), '')::uuid"
)


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("audit_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policy_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policy_version", sa.Integer(), nullable=False),
        sa.Column("reference_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("knowledge_cutoff", sa.DateTime(timezone=True), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processing_activity", sa.Text(), nullable=False),
        sa.Column("processing_authorization_reference", sa.Text(), nullable=False),
        sa.Column("processing_authorization_version", sa.Integer(), nullable=False),
        sa.Column("processing_authorization_digest", sa.Text(), nullable=False),
        sa.Column("data_contract_id", sa.Text(), nullable=False),
        sa.Column("data_contract_version", sa.Integer(), nullable=False),
        sa.Column("provider_profile", sa.Text(), nullable=False),
        sa.Column("provider_profile_version", sa.Integer(), nullable=False),
        sa.Column("provider_profile_digest", sa.Text(), nullable=False),
        sa.Column("model_name", sa.Text(), nullable=False),
        sa.Column("explanation_schema", sa.Text(), nullable=False),
        sa.Column("prompt_template_id", sa.Text(), nullable=False),
        sa.Column("prompt_template_version", sa.Integer(), nullable=False),
        sa.Column("prompt_template_digest", sa.Text(), nullable=False),
        sa.Column("guard_version", sa.Integer(), nullable=False),
        sa.Column("guard_digest", sa.Text(), nullable=False),
        sa.Column("prompt_payload_digest", sa.Text(), nullable=False),
        sa.Column("source_reference_digest", sa.Text(), nullable=False),
        sa.Column(
            "source_reference_audit_references",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("canonical_fallback_digest", sa.Text(), nullable=False),
        sa.Column("idempotency_reference", sa.Text(), nullable=True),
        sa.Column("released_output_digest", sa.Text(), nullable=True),
        sa.Column("release_disposition", sa.String(length=30), nullable=False),
        sa.Column("accepted", sa.Boolean(), nullable=False),
        sa.Column("violation_codes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("limitations", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("record_digest", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_ai_explanation_audit_record_owner_org",
        ),
        sa.ForeignKeyConstraint(
            ["policy_id"],
            ["core_audit.policies.policy_id"],
            name="fk_ai_explanation_audit_policy",
        ),
        sa.CheckConstraint("policy_version >= 1", name="ck_ai_explanation_audit_policy_version"),
        sa.CheckConstraint(
            "processing_authorization_version >= 1",
            name="ck_ai_explanation_audit_processing_authorization_version",
        ),
        sa.CheckConstraint(
            "data_contract_version >= 1",
            name="ck_ai_explanation_audit_data_contract_version",
        ),
        sa.CheckConstraint(
            "provider_profile_version >= 1",
            name="ck_ai_explanation_audit_provider_profile_version",
        ),
        sa.CheckConstraint(
            "prompt_template_version >= 1",
            name="ck_ai_explanation_audit_prompt_template_version",
        ),
        sa.CheckConstraint("guard_version >= 1", name="ck_ai_explanation_audit_guard_version"),
        sa.CheckConstraint(
            "knowledge_cutoff >= reference_time",
            name="ck_ai_explanation_audit_temporal_order",
        ),
        sa.CheckConstraint(
            "evaluated_at >= requested_at",
            name="ck_ai_explanation_audit_evaluation_order",
        ),
        sa.CheckConstraint(
            "release_disposition IN ('RELEASE_APPROVED', 'NOT_RELEASED')",
            name="ck_ai_explanation_audit_release_disposition_values",
        ),
        sa.CheckConstraint(
            "(accepted = true AND release_disposition = 'RELEASE_APPROVED') "
            "OR (accepted = false AND release_disposition = 'NOT_RELEASED')",
            name="ck_ai_explanation_audit_accepted_disposition",
        ),
        sa.CheckConstraint(
            "(release_disposition = 'RELEASE_APPROVED' AND released_output_digest IS NOT NULL) "
            "OR (release_disposition = 'NOT_RELEASED' AND released_output_digest IS NULL)",
            name="ck_ai_explanation_audit_released_output_digest",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(source_reference_audit_references) = 'array'",
            name="ck_ai_explanation_audit_source_references_json_array",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(violation_codes) = 'array'",
            name="ck_ai_explanation_audit_violation_codes_json_array",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(limitations) = 'array'",
            name="ck_ai_explanation_audit_limitations_json_array",
        ),
        sa.CheckConstraint(
            "length(processing_authorization_digest) = 64",
            name="ck_ai_explanation_audit_processing_authorization_digest_len",
        ),
        sa.CheckConstraint(
            "length(provider_profile_digest) = 64",
            name="ck_ai_explanation_audit_provider_profile_digest_len",
        ),
        sa.CheckConstraint(
            "length(prompt_template_digest) = 64",
            name="ck_ai_explanation_audit_prompt_template_digest_len",
        ),
        sa.CheckConstraint(
            "length(guard_digest) = 64",
            name="ck_ai_explanation_audit_guard_digest_len",
        ),
        sa.CheckConstraint(
            "length(prompt_payload_digest) = 64",
            name="ck_ai_explanation_audit_prompt_payload_digest_len",
        ),
        sa.CheckConstraint(
            "length(source_reference_digest) = 64",
            name="ck_ai_explanation_audit_source_reference_digest_len",
        ),
        sa.CheckConstraint(
            "length(canonical_fallback_digest) = 64",
            name="ck_ai_explanation_audit_canonical_fallback_digest_len",
        ),
        sa.CheckConstraint(
            "idempotency_reference IS NULL OR length(idempotency_reference) = 64",
            name="ck_ai_explanation_audit_idempotency_reference_len",
        ),
        sa.CheckConstraint(
            "released_output_digest IS NULL OR length(released_output_digest) = 64",
            name="ck_ai_explanation_audit_released_output_digest_len",
        ),
        sa.CheckConstraint(
            "length(record_digest) = 64",
            name="ck_ai_explanation_audit_record_digest_len",
        ),
        sa.PrimaryKeyConstraint("audit_id", name="pk_ai_explanation_audit_records"),
        schema=SCHEMA,
        comment="titan.classification=PROTECTED;titan.module_owner=livestock",
    )
    op.create_index(
        "uq_ai_explanation_audit_owner_record_digest",
        TABLE,
        ["record_owner_organization_id", "record_digest"],
        unique=True,
        schema=SCHEMA,
    )
    op.create_index(
        "ix_ai_explanation_audit_owner_created",
        TABLE,
        ["record_owner_organization_id", sa.text("created_at DESC")],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_ai_explanation_audit_owner_policy_temporal",
        TABLE,
        [
            "record_owner_organization_id",
            "policy_id",
            "policy_version",
            "reference_time",
            "knowledge_cutoff",
        ],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_ai_explanation_audit_owner_correlation",
        TABLE,
        ["record_owner_organization_id", "correlation_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_ai_explanation_audit_owner_idempotency",
        TABLE,
        ["record_owner_organization_id", "idempotency_reference"],
        schema=SCHEMA,
        postgresql_where=sa.text("idempotency_reference IS NOT NULL"),
    )
    op.create_index(
        "ix_ai_explanation_audit_owner_processing_created",
        TABLE,
        ["record_owner_organization_id", "processing_activity", sa.text("created_at DESC")],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_ai_explanation_audit_owner_disposition_created",
        TABLE,
        ["record_owner_organization_id", "release_disposition", sa.text("created_at DESC")],
        schema=SCHEMA,
    )
    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{TABLE} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{TABLE} FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            f"""
            CREATE POLICY ai_explanation_audit_select ON {SCHEMA}.{TABLE}
            FOR SELECT USING ({_RLS_OWNER_CONTEXT})
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            CREATE POLICY ai_explanation_audit_insert ON {SCHEMA}.{TABLE}
            FOR INSERT WITH CHECK ({_RLS_OWNER_CONTEXT})
            """
        )
    )
    op.execute(sa.text(f"REVOKE ALL ON {SCHEMA}.{TABLE} FROM PUBLIC"))


def downgrade() -> None:
    op.execute(sa.text(f"DROP POLICY IF EXISTS ai_explanation_audit_insert ON {SCHEMA}.{TABLE}"))
    op.execute(sa.text(f"DROP POLICY IF EXISTS ai_explanation_audit_select ON {SCHEMA}.{TABLE}"))
    op.drop_index(
        "ix_ai_explanation_audit_owner_disposition_created", table_name=TABLE, schema=SCHEMA
    )
    op.drop_index(
        "ix_ai_explanation_audit_owner_processing_created", table_name=TABLE, schema=SCHEMA
    )
    op.drop_index("ix_ai_explanation_audit_owner_idempotency", table_name=TABLE, schema=SCHEMA)
    op.drop_index("ix_ai_explanation_audit_owner_correlation", table_name=TABLE, schema=SCHEMA)
    op.drop_index("ix_ai_explanation_audit_owner_policy_temporal", table_name=TABLE, schema=SCHEMA)
    op.drop_index("ix_ai_explanation_audit_owner_created", table_name=TABLE, schema=SCHEMA)
    op.drop_index("uq_ai_explanation_audit_owner_record_digest", table_name=TABLE, schema=SCHEMA)
    op.drop_table(TABLE, schema=SCHEMA)
