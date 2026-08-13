"""Cria catálogo temporal append-only para material normativo sintético.

Revision ID: 20260813_0074
Revises: 20260813_0073
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260813_0074"
down_revision = "20260813_0073"
branch_labels = None
depends_on = None

_SCHEMA = "core_audit"
_TABLE = "internal_test_normative_bases"
_CONTEXT = (
    "record_owner_organization_id = "
    "NULLIF(current_setting('titan.organization_id', true), '')::uuid"
)


def upgrade() -> None:
    op.create_table(
        _TABLE,
        sa.Column("normative_basis_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(120), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("policy_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policy_code", sa.String(160), nullable=False),
        sa.Column("policy_version", sa.Integer(), nullable=False),
        sa.Column("purpose", sa.String(160), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True)),
        sa.Column("known_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_by", sa.String(240), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("instrument_code", sa.String(240), nullable=False),
        sa.Column("instrument_version", sa.String(120), nullable=False),
        sa.Column("provision", sa.String(240)),
        sa.Column("content_digest", sa.String(128), nullable=False),
        sa.Column("limitations", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"], ["core_identity.organizations.organization_id"]
        ),
        sa.UniqueConstraint(
            "record_owner_organization_id", "code", "version", name="uq_internal_test_normative_basis_version"
        ),
        schema=_SCHEMA,
        comment="titan.classification=PROTECTED;titan.module_owner=livestock",
    )
    op.create_index(
        "ix_internal_test_normative_bases_policy_temporal",
        _TABLE,
        ["record_owner_organization_id", "policy_id", "known_at", "valid_from"],
        schema=_SCHEMA,
    )
    op.execute(sa.text(f"ALTER TABLE {_SCHEMA}.{_TABLE} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {_SCHEMA}.{_TABLE} FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            f"CREATE POLICY {_TABLE}_select_by_owner ON {_SCHEMA}.{_TABLE} "
            f"FOR SELECT USING ({_CONTEXT})"
        )
    )
    op.execute(
        sa.text(
            f"CREATE POLICY {_TABLE}_insert_by_owner ON {_SCHEMA}.{_TABLE} "
            f"FOR INSERT WITH CHECK ({_CONTEXT})"
        )
    )


def downgrade() -> None:
    op.drop_table(_TABLE, schema=_SCHEMA)
