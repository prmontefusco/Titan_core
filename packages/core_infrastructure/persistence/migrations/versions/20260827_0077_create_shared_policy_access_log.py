"""Create shared_policy_access_log table for BuyerPolicy Phase 3 increment 2.

Revision ID: 20260827_0077
Revises: 20260827_0076
Create Date: 2026-08-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260827_0077"
down_revision: str | None = "20260827_0076"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "core_audit"
_TABLE = "shared_policy_access_log"

# As duas partes do grant enxergam a trilha do proprio contrato: a dona da
# Policy porque a trilha existe para ela, e a beneficiaria porque e sob o
# contexto dela que parte dos acessos e registrada. Terceira Organization nao
# alcanca nenhuma linha.
_RLS_CONTEXT = (
    "NULLIF(current_setting('titan.organization_id', true), '')::uuid "
    "IN (organization_id, record_owner_organization_id)"
)


def upgrade() -> None:
    op.create_table(
        _TABLE,
        sa.Column("access_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("grant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policy_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("subject_type", sa.String(length=100), nullable=True),
        sa.Column("subject_id", sa.String(length=100), nullable=True),
        sa.Column("http_status_code", sa.Integer(), nullable=False),
        sa.Column("accessed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["grant_id"],
            ["core_audit.authorization_grants.grant_id"],
            name="fk_shared_policy_access_log_grant",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_shared_policy_access_log_org",
        ),
        sa.ForeignKeyConstraint(
            ["policy_id"],
            ["core_audit.policies.policy_id"],
            name="fk_shared_policy_access_log_policy",
        ),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_shared_policy_access_log_record_owner_org",
        ),
        sa.PrimaryKeyConstraint("access_id"),
        schema=_SCHEMA,
        comment="titan.classification=PROTECTED;titan.module_owner=core_audit",
    )
    op.create_index(
        "ix_shared_policy_access_log_policy_accessed_at",
        _TABLE,
        ["policy_id", "accessed_at"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_shared_policy_access_log_grant",
        _TABLE,
        ["grant_id"],
        schema=_SCHEMA,
    )
    op.execute(sa.text(f"ALTER TABLE {_SCHEMA}.{_TABLE} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {_SCHEMA}.{_TABLE} FORCE ROW LEVEL SECURITY"))
    # Somente SELECT e INSERT ganham policy: sem policy de UPDATE ou DELETE, o
    # PostgreSQL recusa reescrita e apagamento ao runtime. E assim que a trilha
    # e append-only de fato, e nao por convencao de codigo.
    op.execute(
        sa.text(
            f"""
            CREATE POLICY shared_policy_access_log_select ON {_SCHEMA}.{_TABLE}
            FOR SELECT USING ({_RLS_CONTEXT})
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            CREATE POLICY shared_policy_access_log_insert ON {_SCHEMA}.{_TABLE}
            FOR INSERT WITH CHECK ({_RLS_CONTEXT})
            """
        )
    )
    op.execute(sa.text(f"REVOKE ALL ON {_SCHEMA}.{_TABLE} FROM PUBLIC"))


def downgrade() -> None:
    op.execute(
        sa.text(f"DROP POLICY IF EXISTS shared_policy_access_log_insert ON {_SCHEMA}.{_TABLE}")
    )
    op.execute(
        sa.text(f"DROP POLICY IF EXISTS shared_policy_access_log_select ON {_SCHEMA}.{_TABLE}")
    )
    op.drop_index("ix_shared_policy_access_log_grant", table_name=_TABLE, schema=_SCHEMA)
    op.drop_index(
        "ix_shared_policy_access_log_policy_accessed_at", table_name=_TABLE, schema=_SCHEMA
    )
    op.drop_table(_TABLE, schema=_SCHEMA)
