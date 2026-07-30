"""Adicionar tabelas de governanca de decisao.

Revision ID: 20260730_0062
Revises: 20260730_0061
Create Date: 2026-07-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from packages.core_infrastructure.persistence.events import CORE_AUDIT_SCHEMA

# revision identifiers, used by Alembic.
revision = "20260730_0062"
down_revision = "20260730_0061"
branch_labels = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "decision_proposals",
        sa.Column("proposal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evaluation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evaluation_hash", sa.String(length=64), nullable=False),
        sa.Column("proposed_result", sa.String(length=50), nullable=False),
        sa.Column("proposed_reasons", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("purpose", sa.String(length=255), nullable=False),
        sa.Column("justification_required", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "jsonb_array_length(proposed_reasons) > 0",
            name="ck_decision_proposals_reasons_not_empty",
        ),
        sa.ForeignKeyConstraint(
            ["evaluation_id"],
            [f"{CORE_AUDIT_SCHEMA}.evaluations.evaluation_id"],
            name="fk_decision_proposals_evaluation",
        ),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_decision_proposals_organization",
        ),
        sa.PrimaryKeyConstraint("proposal_id"),
        schema=CORE_AUDIT_SCHEMA,
        comment="titan.classification=PROTECTED;titan.module_owner=core_audit",
    )

    op.create_table(
        "decision_reviews",
        sa.Column("review_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("proposal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reviewer_reference", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("reviewer_authority_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conclusion", sa.String(length=50), nullable=False),
        sa.Column("reasoning", sa.String(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["proposal_id"],
            [f"{CORE_AUDIT_SCHEMA}.decision_proposals.proposal_id"],
            name="fk_decision_reviews_proposal",
        ),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_decision_reviews_organization",
        ),
        sa.ForeignKeyConstraint(
            ["reviewer_authority_id", "record_owner_organization_id"],
            [
                f"{CORE_AUDIT_SCHEMA}.decision_authority_profiles.authority_profile_id",
                f"{CORE_AUDIT_SCHEMA}.decision_authority_profiles.record_owner_organization_id",
            ],
            name="fk_decision_reviews_authority_profile",
        ),
        sa.PrimaryKeyConstraint("review_id"),
        schema=CORE_AUDIT_SCHEMA,
        comment="titan.classification=PROTECTED;titan.module_owner=core_audit",
    )

    op.create_table(
        "decision_overrides",
        sa.Column("override_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("original_decision_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("authority_profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("new_result", sa.String(length=50), nullable=False),
        sa.Column("mandatory_reason", sa.String(), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["authority_profile_id", "record_owner_organization_id"],
            [
                f"{CORE_AUDIT_SCHEMA}.decision_authority_profiles.authority_profile_id",
                f"{CORE_AUDIT_SCHEMA}.decision_authority_profiles.record_owner_organization_id",
            ],
            name="fk_decision_overrides_authority_profile",
        ),
        sa.ForeignKeyConstraint(
            ["original_decision_id"],
            [f"{CORE_AUDIT_SCHEMA}.decisions.decision_id"],
            name="fk_decision_overrides_decision",
        ),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_decision_overrides_organization",
        ),
        sa.PrimaryKeyConstraint("override_id"),
        schema=CORE_AUDIT_SCHEMA,
        comment="titan.classification=PROTECTED;titan.module_owner=core_audit",
    )

    op.create_table(
        "decision_contestations",
        sa.Column("contestation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("decision_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contested_by", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("grounds_description", sa.String(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("filed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_notes", sa.String(), server_default="", nullable=False),
        sa.ForeignKeyConstraint(
            ["decision_id"],
            [f"{CORE_AUDIT_SCHEMA}.decisions.decision_id"],
            name="fk_decision_contestations_decision",
        ),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_decision_contestations_organization",
        ),
        sa.PrimaryKeyConstraint("contestation_id"),
        schema=CORE_AUDIT_SCHEMA,
        comment="titan.classification=PROTECTED;titan.module_owner=core_audit",
    )


def downgrade() -> None:
    op.drop_table("decision_contestations", schema=CORE_AUDIT_SCHEMA)
    op.drop_table("decision_overrides", schema=CORE_AUDIT_SCHEMA)
    op.drop_table("decision_reviews", schema=CORE_AUDIT_SCHEMA)
    op.drop_table("decision_proposals", schema=CORE_AUDIT_SCHEMA)
