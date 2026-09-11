"""Criar parts/interchangeability_groups e tabelas filhas com RLS (A3).

Revision ID: 20260911_0003
Revises: 20260911_0002
Create Date: 2026-09-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260911_0003"
down_revision: str | None = "20260911_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "core_audit"
MODULE_OWNER_COMMENT = "titan.classification=PROTECTED;titan.module_owner=asset"

# Ordem de criação (topológica por FK) e ordem reversa para downgrade/RLS.
TABLES_IN_CREATION_ORDER = (
    "interchangeability_groups",
    "parts",
    "part_revisions",
    "interchangeability_group_members",
    "part_supersessions",
)


def upgrade() -> None:
    op.create_table(
        "interchangeability_groups",
        sa.Column("group_id", sa.UUID(), nullable=False),
        sa.Column("record_owner_organization_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_interchangeability_groups_organization",
        ),
        sa.PrimaryKeyConstraint("group_id"),
        schema=SCHEMA,
        comment=MODULE_OWNER_COMMENT,
    )
    op.create_table(
        "parts",
        sa.Column("part_id", sa.UUID(), nullable=False),
        sa.Column("record_owner_organization_id", sa.UUID(), nullable=False),
        sa.Column("part_number", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("manufacturer", sa.String(length=200), nullable=False),
        sa.Column("manufacturer_pn", sa.String(length=100), nullable=True),
        sa.Column("nsn", sa.String(length=50), nullable=True),
        sa.Column("external_classifications", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("interchangeability_group_id", sa.UUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["interchangeability_group_id"],
            ["core_audit.interchangeability_groups.group_id"],
            name="fk_parts_interchangeability_group",
        ),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_parts_organization",
        ),
        sa.PrimaryKeyConstraint("part_id"),
        schema=SCHEMA,
        comment=MODULE_OWNER_COMMENT,
    )
    op.create_table(
        "part_revisions",
        sa.Column("revision_id", sa.UUID(), nullable=False),
        sa.Column("part_id", sa.UUID(), nullable=False),
        sa.Column("record_owner_organization_id", sa.UUID(), nullable=False),
        sa.Column("revision_code", sa.String(length=50), nullable=False),
        sa.Column("lifecycle_state", sa.String(length=20), nullable=False),
        sa.Column("spec_ref", sa.UUID(), nullable=True),
        sa.Column("drawing_ref", sa.UUID(), nullable=True),
        sa.Column("materials", postgresql.ARRAY(sa.String()), nullable=False),
        sa.ForeignKeyConstraint(
            ["part_id"], ["core_audit.parts.part_id"], name="fk_part_revisions_part"
        ),
        sa.PrimaryKeyConstraint("revision_id"),
        schema=SCHEMA,
        comment=MODULE_OWNER_COMMENT,
    )
    op.create_table(
        "interchangeability_group_members",
        sa.Column("group_id", sa.UUID(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("record_owner_organization_id", sa.UUID(), nullable=False),
        sa.Column("part_revision_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["core_audit.interchangeability_groups.group_id"],
            name="fk_interchangeability_group_members_group",
        ),
        sa.ForeignKeyConstraint(
            ["part_revision_id"],
            ["core_audit.part_revisions.revision_id"],
            name="fk_interchangeability_group_members_revision",
        ),
        sa.PrimaryKeyConstraint("group_id", "position"),
        schema=SCHEMA,
        comment=MODULE_OWNER_COMMENT,
    )
    op.create_table(
        "part_supersessions",
        sa.Column("part_id", sa.UUID(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("record_owner_organization_id", sa.UUID(), nullable=False),
        sa.Column("predecessor_revision_id", sa.UUID(), nullable=False),
        sa.Column("successor_revision_id", sa.UUID(), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.ForeignKeyConstraint(
            ["part_id"], ["core_audit.parts.part_id"], name="fk_part_supersessions_part"
        ),
        sa.ForeignKeyConstraint(
            ["predecessor_revision_id"],
            ["core_audit.part_revisions.revision_id"],
            name="fk_part_supersessions_predecessor",
        ),
        sa.ForeignKeyConstraint(
            ["successor_revision_id"],
            ["core_audit.part_revisions.revision_id"],
            name="fk_part_supersessions_successor",
        ),
        sa.PrimaryKeyConstraint("part_id", "position"),
        schema=SCHEMA,
        comment=MODULE_OWNER_COMMENT,
    )

    for table in TABLES_IN_CREATION_ORDER:
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
    for table in reversed(TABLES_IN_CREATION_ORDER):
        op.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {SCHEMA}.{table}"))

    for table in reversed(TABLES_IN_CREATION_ORDER):
        op.drop_table(table, schema=SCHEMA)
