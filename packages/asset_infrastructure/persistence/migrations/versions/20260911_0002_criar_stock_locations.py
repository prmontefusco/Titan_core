"""Criar stock_locations com RLS (A3).

Revision ID: 20260911_0002
Revises: 20260911_0001
Create Date: 2026-09-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260911_0002"
down_revision: str | None = "20260911_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "core_audit"
TABLE = "stock_locations"
MODULE_OWNER_COMMENT = "titan.classification=PROTECTED;titan.module_owner=asset"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("location_id", sa.UUID(), nullable=False),
        sa.Column("record_owner_organization_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("site_id", sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_stock_locations_organization",
        ),
        sa.ForeignKeyConstraint(
            ["site_id"],
            ["core_audit.customer_sites.site_id"],
            name="fk_stock_locations_site",
        ),
        sa.PrimaryKeyConstraint("location_id"),
        sa.UniqueConstraint(
            "record_owner_organization_id", "code", name="uq_stock_locations_owner_code"
        ),
        schema=SCHEMA,
        comment=MODULE_OWNER_COMMENT,
    )

    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{TABLE} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{TABLE} FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(f"""
        CREATE POLICY tenant_isolation_policy ON {SCHEMA}.{TABLE}
        FOR ALL
        USING (
            record_owner_organization_id = NULLIF(
                current_setting('titan.organization_id', true),
                ''
            )::uuid
        )
        WITH CHECK (
            record_owner_organization_id = NULLIF(
                current_setting('titan.organization_id', true),
                ''
            )::uuid
        )
        """)
    )


def downgrade() -> None:
    op.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {SCHEMA}.{TABLE}"))
    op.drop_table(TABLE, schema=SCHEMA)
