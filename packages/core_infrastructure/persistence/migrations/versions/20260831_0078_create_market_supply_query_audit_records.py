"""Create Market Supply query audit records table.

Revision ID: 20260831_0078
Revises: 20260827_0077
Create Date: 2026-08-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260831_0078"
down_revision: str | None = "20260827_0077"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "core_audit"
TABLE = "market_supply_query_audit_records"

_RLS_OWNER_CONTEXT = (
    "record_owner_organization_id = "
    "NULLIF(current_setting('titan.organization_id', true), '')::uuid"
)


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("audit_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requester_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("beneficiary_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("access_purpose", sa.Text(), nullable=False),
        sa.Column("authorization_context_digest", sa.Text(), nullable=False),
        sa.Column("policy_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policy_version", sa.Integer(), nullable=False),
        sa.Column("privacy_profile_id", sa.Text(), nullable=False),
        sa.Column("privacy_profile_version", sa.Integer(), nullable=False),
        sa.Column("candidate_population_digest", sa.Text(), nullable=False),
        sa.Column("population_digest", sa.Text(), nullable=True),
        sa.Column("query_fingerprint_digest", sa.Text(), nullable=False),
        sa.Column("policy_context_digest", sa.Text(), nullable=False),
        sa.Column("filter_fingerprint", sa.Text(), nullable=False),
        sa.Column("result_subject_count", sa.Integer(), nullable=False),
        sa.Column("reference_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("knowledge_cutoff", sa.DateTime(timezone=True), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("disclosure_state", sa.String(length=20), nullable=False),
        sa.Column(
            "decision_reason_codes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("outcome", sa.String(length=50), nullable=False),
        sa.Column("external_disposition", sa.String(length=50), nullable=False),
        sa.Column("result_digest", sa.Text(), nullable=True),
        sa.Column("revocation_state", sa.String(length=50), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_reference", sa.Text(), nullable=False),
        sa.Column("semantic_request_digest", sa.Text(), nullable=False),
        sa.Column("grant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("record_digest", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["beneficiary_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_market_supply_query_audit_beneficiary_org",
        ),
        sa.ForeignKeyConstraint(
            ["grant_id"],
            ["core_audit.authorization_grants.grant_id"],
            name="fk_market_supply_query_audit_grant",
        ),
        sa.ForeignKeyConstraint(
            ["policy_id"],
            ["core_audit.policies.policy_id"],
            name="fk_market_supply_query_audit_policy",
        ),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_market_supply_query_audit_record_owner_org",
        ),
        sa.ForeignKeyConstraint(
            ["requester_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_market_supply_query_audit_requester_org",
        ),
        sa.CheckConstraint(
            "policy_version >= 1",
            name="ck_market_supply_query_audit_policy_version",
        ),
        sa.CheckConstraint(
            "privacy_profile_version >= 1",
            name="ck_market_supply_query_audit_privacy_profile_version",
        ),
        sa.CheckConstraint(
            "result_subject_count >= 0",
            name="ck_market_supply_query_audit_result_subject_count",
        ),
        sa.CheckConstraint(
            "access_purpose <> ''",
            name="ck_market_supply_query_audit_purpose",
        ),
        sa.CheckConstraint(
            "authorization_context_digest <> ''",
            name="ck_market_supply_query_audit_authorization_digest",
        ),
        sa.CheckConstraint(
            "privacy_profile_id <> ''",
            name="ck_market_supply_query_audit_privacy_profile",
        ),
        sa.CheckConstraint(
            "candidate_population_digest <> ''",
            name="ck_market_supply_query_audit_candidate_digest",
        ),
        sa.CheckConstraint(
            "query_fingerprint_digest <> ''",
            name="ck_market_supply_query_audit_fingerprint_digest",
        ),
        sa.CheckConstraint(
            "policy_context_digest <> ''",
            name="ck_market_supply_query_audit_policy_context_digest",
        ),
        sa.CheckConstraint(
            "filter_fingerprint <> ''",
            name="ck_market_supply_query_audit_filter",
        ),
        sa.CheckConstraint(
            "idempotency_reference <> ''",
            name="ck_market_supply_query_audit_idempotency_reference",
        ),
        sa.CheckConstraint(
            "semantic_request_digest <> ''",
            name="ck_market_supply_query_audit_semantic_request_digest",
        ),
        sa.CheckConstraint(
            "record_digest <> ''",
            name="ck_market_supply_query_audit_record_digest",
        ),
        sa.CheckConstraint(
            "outcome IN ('RELEASED', 'DENIED_BY_AUTHORIZATION', 'PURPOSE_MISMATCH', "
            "'GRANT_REVOKED', 'SUPPRESSED_BY_PRIVACY')",
            name="ck_market_supply_query_audit_outcome",
        ),
        sa.CheckConstraint(
            "external_disposition IN ('RELEASE_AGGREGATE', 'UNIFORM_NOT_RELEASED')",
            name="ck_market_supply_query_audit_external_disposition",
        ),
        sa.CheckConstraint(
            "disclosure_state IN ('ALLOW', 'GENERALIZE', 'SUPPRESS', 'DENY')",
            name="ck_market_supply_query_audit_disclosure_state",
        ),
        sa.CheckConstraint(
            "revocation_state IN ('NOT_APPLICABLE', 'NOT_REVOKED', 'REVOKED_OBSERVED')",
            name="ck_market_supply_query_audit_revocation_state",
        ),
        sa.CheckConstraint(
            "(outcome = 'RELEASED' AND external_disposition = 'RELEASE_AGGREGATE') "
            "OR (outcome <> 'RELEASED' AND external_disposition = 'UNIFORM_NOT_RELEASED')",
            name="ck_market_supply_query_audit_release_disposition",
        ),
        sa.CheckConstraint(
            "(outcome = 'RELEASED' AND result_digest IS NOT NULL) "
            "OR (outcome <> 'RELEASED' AND result_digest IS NULL)",
            name="ck_market_supply_query_audit_result_digest",
        ),
        sa.CheckConstraint(
            "population_digest IS NOT NULL OR outcome <> 'RELEASED'",
            name="ck_market_supply_query_audit_population_digest",
        ),
        sa.PrimaryKeyConstraint("audit_id", name="pk_market_supply_query_audit_records"),
        schema=SCHEMA,
        comment="titan.classification=PROTECTED;titan.module_owner=livestock",
    )
    op.create_index(
        "uq_market_supply_query_audit_record_digest",
        TABLE,
        ["record_digest"],
        unique=True,
        schema=SCHEMA,
    )
    op.create_index(
        "ix_market_supply_query_audit_requester_purpose_requested",
        TABLE,
        ["requester_organization_id", "access_purpose", sa.text("requested_at DESC")],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_market_supply_query_audit_beneficiary_purpose_requested",
        TABLE,
        ["beneficiary_organization_id", "access_purpose", sa.text("requested_at DESC")],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_market_supply_query_audit_related_fingerprint",
        TABLE,
        [
            "requester_organization_id",
            "beneficiary_organization_id",
            "access_purpose",
            "policy_context_digest",
            sa.text("requested_at DESC"),
        ],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_market_supply_query_audit_policy_window",
        TABLE,
        ["policy_id", "policy_version", "reference_time", "knowledge_cutoff"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_market_supply_query_audit_candidate_population",
        TABLE,
        ["candidate_population_digest"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_market_supply_query_audit_population",
        TABLE,
        ["population_digest"],
        schema=SCHEMA,
        postgresql_where=sa.text("population_digest IS NOT NULL"),
    )
    op.create_index(
        "ix_market_supply_query_audit_semantic_request",
        TABLE,
        ["requester_organization_id", "idempotency_reference", "semantic_request_digest"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_market_supply_query_audit_correlation",
        TABLE,
        ["correlation_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_market_supply_query_audit_grant",
        TABLE,
        ["grant_id"],
        schema=SCHEMA,
        postgresql_where=sa.text("grant_id IS NOT NULL"),
    )
    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{TABLE} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{TABLE} FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            f"""
            CREATE POLICY market_supply_query_audit_select ON {SCHEMA}.{TABLE}
            FOR SELECT USING ({_RLS_OWNER_CONTEXT})
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            CREATE POLICY market_supply_query_audit_insert ON {SCHEMA}.{TABLE}
            FOR INSERT WITH CHECK ({_RLS_OWNER_CONTEXT})
            """
        )
    )
    op.execute(sa.text("REVOKE ALL ON core_audit.market_supply_query_audit_records FROM PUBLIC"))


def downgrade() -> None:
    op.execute(
        sa.text(f"DROP POLICY IF EXISTS market_supply_query_audit_insert ON {SCHEMA}.{TABLE}")
    )
    op.execute(
        sa.text(f"DROP POLICY IF EXISTS market_supply_query_audit_select ON {SCHEMA}.{TABLE}")
    )
    op.drop_index("ix_market_supply_query_audit_grant", table_name=TABLE, schema=SCHEMA)
    op.drop_index("ix_market_supply_query_audit_correlation", table_name=TABLE, schema=SCHEMA)
    op.drop_index(
        "ix_market_supply_query_audit_semantic_request",
        table_name=TABLE,
        schema=SCHEMA,
    )
    op.drop_index("ix_market_supply_query_audit_population", table_name=TABLE, schema=SCHEMA)
    op.drop_index(
        "ix_market_supply_query_audit_candidate_population",
        table_name=TABLE,
        schema=SCHEMA,
    )
    op.drop_index("ix_market_supply_query_audit_policy_window", table_name=TABLE, schema=SCHEMA)
    op.drop_index(
        "ix_market_supply_query_audit_related_fingerprint",
        table_name=TABLE,
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_market_supply_query_audit_beneficiary_purpose_requested",
        table_name=TABLE,
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_market_supply_query_audit_requester_purpose_requested",
        table_name=TABLE,
        schema=SCHEMA,
    )
    op.drop_index(
        "uq_market_supply_query_audit_record_digest",
        table_name=TABLE,
        schema=SCHEMA,
    )
    op.drop_table(TABLE, schema=SCHEMA)
