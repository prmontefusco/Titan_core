"""Impõe append-only físico a Evaluation, Decision e Dossier.

Revision ID: 20260813_0072
Revises: 20260813_0071
"""

import sqlalchemy as sa
from alembic import op

revision = "20260813_0072"
down_revision = "20260813_0071"
branch_labels = None
depends_on = None

SCHEMA = "core_audit"
TABLES = ("evaluations", "decisions", "dossiers")


def _context() -> str:
    return (
        "record_owner_organization_id = "
        "NULLIF(current_setting('titan.organization_id', true), '')::uuid"
    )


def upgrade() -> None:
    for table in TABLES:
        op.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {SCHEMA}.{table}"))
        op.execute(
            sa.text(
                f"CREATE POLICY {table}_select_by_owner ON {SCHEMA}.{table} "
                f"FOR SELECT USING ({_context()})"
            )
        )
        op.execute(
            sa.text(
                f"CREATE POLICY {table}_insert_by_owner ON {SCHEMA}.{table} "
                f"FOR INSERT WITH CHECK ({_context()})"
            )
        )


def downgrade() -> None:
    for table in TABLES:
        op.execute(sa.text(f"DROP POLICY IF EXISTS {table}_insert_by_owner ON {SCHEMA}.{table}"))
        op.execute(sa.text(f"DROP POLICY IF EXISTS {table}_select_by_owner ON {SCHEMA}.{table}"))
        op.execute(
            sa.text(
                f"CREATE POLICY tenant_isolation_policy ON {SCHEMA}.{table} "
                f"USING ({_context()}) WITH CHECK ({_context()})"
            )
        )
