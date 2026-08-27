"""Create shared_decisions table for BuyerPolicy Phase 3 increment 1.

Revision ID: 20260827_0076
Revises: 5e402311b352
Create Date: 2026-08-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260827_0076"
down_revision: str | None = "5e402311b352"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "core_audit"
_TABLE = "shared_decisions"
_RLS_CONTEXT = (
    "NULLIF(current_setting('titan.organization_id', true), '')::uuid "
    "IN (proposer_organization_id, reviewer_organization_id)"
)


def upgrade() -> None:
    op.create_table(
        _TABLE,
        sa.Column("decision_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("grant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evaluation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policy_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("proposer_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("proposal_content", sa.Text(), nullable=False),
        sa.Column(
            "proposal_evidence_references",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("proposed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewer_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("review_decision", sa.String(length=50), nullable=True),
        sa.Column("review_content", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=False),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["evaluation_id"],
            ["core_audit.evaluations.evaluation_id"],
            name="fk_shared_decisions_evaluation",
        ),
        sa.ForeignKeyConstraint(
            ["grant_id"],
            ["core_audit.authorization_grants.grant_id"],
            name="fk_shared_decisions_grant",
        ),
        sa.ForeignKeyConstraint(
            ["policy_id"],
            ["core_audit.policies.policy_id"],
            name="fk_shared_decisions_policy",
        ),
        sa.ForeignKeyConstraint(
            ["proposer_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_shared_decisions_proposer_org",
        ),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_shared_decisions_record_owner_org",
        ),
        sa.ForeignKeyConstraint(
            ["reviewer_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_shared_decisions_reviewer_org",
        ),
        sa.PrimaryKeyConstraint("decision_id"),
        schema=_SCHEMA,
        comment="titan.classification=PROTECTED;titan.module_owner=core_audit",
    )
    op.create_index(
        "ix_shared_decisions_policy_proposed_at",
        _TABLE,
        ["policy_id", "proposed_at"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_shared_decisions_grant",
        _TABLE,
        ["grant_id"],
        schema=_SCHEMA,
    )
    op.execute(sa.text(f"ALTER TABLE {_SCHEMA}.{_TABLE} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {_SCHEMA}.{_TABLE} FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            f"""
            CREATE POLICY tenant_isolation_policy ON {_SCHEMA}.{_TABLE}
            USING ({_RLS_CONTEXT})
            WITH CHECK ({_RLS_CONTEXT})
            """
        )
    )


def downgrade() -> None:
    op.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {_SCHEMA}.{_TABLE}"))
    op.drop_index("ix_shared_decisions_grant", table_name=_TABLE, schema=_SCHEMA)
    op.drop_index("ix_shared_decisions_policy_proposed_at", table_name=_TABLE, schema=_SCHEMA)
    op.drop_table(_TABLE, schema=_SCHEMA)
