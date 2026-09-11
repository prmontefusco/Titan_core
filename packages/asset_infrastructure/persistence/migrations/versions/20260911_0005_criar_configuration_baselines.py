"""Criar configuration_baselines/configuration_baseline_positions com RLS (A3).

Revision ID: 20260911_0005
Revises: 20260911_0004
Create Date: 2026-09-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260911_0005"
down_revision: str | None = "20260911_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "core_audit"
MODULE_OWNER_COMMENT = "titan.classification=PROTECTED;titan.module_owner=asset"
TABLES_IN_CREATION_ORDER = ("configuration_baselines", "configuration_baseline_positions")


def upgrade() -> None:
    op.create_table(
        "configuration_baselines",
        sa.Column("baseline_id", sa.UUID(), nullable=False),
        sa.Column("record_owner_organization_id", sa.UUID(), nullable=False),
        sa.Column("model_id", sa.UUID(), nullable=False),
        sa.Column("variant_id", sa.UUID(), nullable=True),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("supersedes_id", sa.UUID(), nullable=True),
        sa.Column("effectivity_valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effectivity_valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("effectivity_serial_from", sa.String(length=100), nullable=True),
        sa.Column("effectivity_serial_to", sa.String(length=100), nullable=True),
        sa.Column("view", sa.String(length=20), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_configuration_baselines_organization",
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_id"],
            ["core_audit.configuration_baselines.baseline_id"],
            name="fk_configuration_baselines_supersedes",
        ),
        sa.PrimaryKeyConstraint("baseline_id"),
        schema=SCHEMA,
        comment=MODULE_OWNER_COMMENT,
    )
    op.create_table(
        "configuration_baseline_positions",
        sa.Column("baseline_id", sa.UUID(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("record_owner_organization_id", sa.UUID(), nullable=False),
        sa.Column("position_code", sa.String(length=100), nullable=False),
        sa.Column("part_id", sa.UUID(), nullable=False),
        sa.Column("part_revision_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["baseline_id"],
            ["core_audit.configuration_baselines.baseline_id"],
            name="fk_configuration_baseline_positions_baseline",
        ),
        sa.ForeignKeyConstraint(
            ["part_id"],
            ["core_audit.parts.part_id"],
            name="fk_configuration_baseline_positions_part",
        ),
        sa.ForeignKeyConstraint(
            ["part_revision_id"],
            ["core_audit.part_revisions.revision_id"],
            name="fk_configuration_baseline_positions_revision",
        ),
        sa.PrimaryKeyConstraint("baseline_id", "ordinal"),
        sa.UniqueConstraint(
            "baseline_id", "position_code", name="uq_configuration_baseline_positions_code"
        ),
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
