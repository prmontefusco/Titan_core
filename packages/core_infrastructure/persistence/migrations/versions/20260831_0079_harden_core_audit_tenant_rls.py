"""Harden tenant RLS on protected core_audit tables.

Revision ID: 20260831_0079
Revises: 20260831_0078
Create Date: 2026-08-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260831_0079"
down_revision: str | None = "20260831_0078"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "core_audit"

OWNER_CONTEXT = "record_owner_organization_id = NULLIF(current_setting('titan.organization_id', true), '')::uuid"
AUTHORIZATION_GRANTS_SELECT_CONTEXT = (
    "NULLIF(current_setting('titan.organization_id', true), '')::uuid "
    "IN (record_owner_organization_id, beneficiary_organization_id)"
)

OWNER_SCOPED_TABLES = (
    "decision_proposals",
    "decision_reviews",
    "decision_overrides",
    "decision_contestations",
    "establishment_qualifications",
)


def upgrade() -> None:
    _harden_authorization_grants()
    for table in OWNER_SCOPED_TABLES:
        _harden_owner_scoped_table(table)


def downgrade() -> None:
    _drop_authorization_grants_policies()
    for table in OWNER_SCOPED_TABLES:
        _drop_owner_scoped_policies(table)


def _harden_authorization_grants() -> None:
    table = "authorization_grants"
    qualified = f"{SCHEMA}.{table}"
    _drop_authorization_grants_policies()
    op.execute(sa.text(f"ALTER TABLE {qualified} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {qualified} FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            f"""
            CREATE POLICY authorization_grants_select ON {qualified}
            FOR SELECT
            USING ({AUTHORIZATION_GRANTS_SELECT_CONTEXT})
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            CREATE POLICY authorization_grants_insert ON {qualified}
            FOR INSERT
            WITH CHECK ({OWNER_CONTEXT})
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            CREATE POLICY authorization_grants_update ON {qualified}
            FOR UPDATE
            USING ({OWNER_CONTEXT})
            WITH CHECK ({OWNER_CONTEXT})
            """
        )
    )


def _drop_authorization_grants_policies() -> None:
    qualified = f"{SCHEMA}.authorization_grants"
    for policy in (
        "authorization_grants_update",
        "authorization_grants_insert",
        "authorization_grants_select",
        "tenant_isolation_policy",
    ):
        op.execute(sa.text(f"DROP POLICY IF EXISTS {policy} ON {qualified}"))


def _harden_owner_scoped_table(table: str) -> None:
    qualified = f"{SCHEMA}.{table}"
    _drop_owner_scoped_policies(table)
    op.execute(sa.text(f"ALTER TABLE {qualified} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {qualified} FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            f"""
            CREATE POLICY {table}_select_by_owner ON {qualified}
            FOR SELECT
            USING ({OWNER_CONTEXT})
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            CREATE POLICY {table}_insert_by_owner ON {qualified}
            FOR INSERT
            WITH CHECK ({OWNER_CONTEXT})
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            CREATE POLICY {table}_update_by_owner ON {qualified}
            FOR UPDATE
            USING ({OWNER_CONTEXT})
            WITH CHECK ({OWNER_CONTEXT})
            """
        )
    )


def _drop_owner_scoped_policies(table: str) -> None:
    qualified = f"{SCHEMA}.{table}"
    for policy in (
        f"{table}_update_by_owner",
        f"{table}_insert_by_owner",
        f"{table}_select_by_owner",
        "tenant_isolation_policy",
    ):
        op.execute(sa.text(f"DROP POLICY IF EXISTS {policy} ON {qualified}"))
