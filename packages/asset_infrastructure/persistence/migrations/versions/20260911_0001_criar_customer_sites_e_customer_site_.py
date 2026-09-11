"""Criar customer_sites/customer_site_contacts com RLS (A3, primeiro agregado de Asset).

Revision ID: 20260911_0001
Revises:
Create Date: 2026-09-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260911_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = ("asset",)
depends_on: str | Sequence[str] | None = None

SCHEMA = "core_audit"
SITES_TABLE = "customer_sites"
CONTACTS_TABLE = "customer_site_contacts"
MODULE_OWNER_COMMENT = "titan.classification=PROTECTED;titan.module_owner=asset"


def upgrade() -> None:
    op.create_table(
        SITES_TABLE,
        sa.Column("site_id", sa.UUID(), nullable=False),
        sa.Column("record_owner_organization_id", sa.UUID(), nullable=False),
        sa.Column("customer_id", sa.UUID(), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_customer_sites_organization",
        ),
        sa.PrimaryKeyConstraint("site_id"),
        sa.UniqueConstraint(
            "record_owner_organization_id", "code", name="uq_customer_sites_owner_code"
        ),
        schema=SCHEMA,
        comment=MODULE_OWNER_COMMENT,
    )
    op.create_table(
        CONTACTS_TABLE,
        sa.Column("site_id", sa.UUID(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("record_owner_organization_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("role", sa.String(length=100), nullable=True),
        sa.Column("email", sa.String(length=200), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.ForeignKeyConstraint(
            ["site_id"],
            ["core_audit.customer_sites.site_id"],
            name="fk_customer_site_contacts_site",
        ),
        sa.PrimaryKeyConstraint("site_id", "position"),
        schema=SCHEMA,
        comment=MODULE_OWNER_COMMENT,
    )

    for table in (SITES_TABLE, CONTACTS_TABLE):
        op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{table} ENABLE ROW LEVEL SECURITY"))
        op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{table} FORCE ROW LEVEL SECURITY"))
        op.execute(
            sa.text(f"""
            CREATE POLICY tenant_isolation_policy ON {SCHEMA}.{table}
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
    for table in (CONTACTS_TABLE, SITES_TABLE):
        op.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {SCHEMA}.{table}"))

    op.drop_table(CONTACTS_TABLE, schema=SCHEMA)
    op.drop_table(SITES_TABLE, schema=SCHEMA)
