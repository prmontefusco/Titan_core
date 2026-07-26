"""Criar campanhas sanitarias e vinculo em tratamentos (Passo 14.2).

Revision ID: 20260726_0048
Revises: 20260726_0047
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260726_0048"
down_revision: str | None = "20260726_0047"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "core_audit"
CAMPAIGNS_TABLE = "sanitary_campaigns"
APPLICATIONS_TABLE = "treatment_applications"


def upgrade() -> None:
    op.create_table(
        CAMPAIGNS_TABLE,
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("disease", sa.String(length=255), nullable=True),
        sa.Column("authority", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "record_owner_organization_id",
            "code",
            name="uq_sanitary_campaigns_org_code",
        ),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_sanitary_campaigns_organization",
        ),
        comment="titan.classification=PROTECTED;titan.module_owner=titan_livestock",
        schema=SCHEMA,
    )
    op.create_check_constraint(
        "ck_sanitary_campaigns_window",
        CAMPAIGNS_TABLE,
        "ends_at > starts_at",
        schema=SCHEMA,
    )
    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{CAMPAIGNS_TABLE} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{CAMPAIGNS_TABLE} FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            f"""
            CREATE POLICY tenant_isolation_policy ON {SCHEMA}.{CAMPAIGNS_TABLE}
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
            """
        )
    )

    op.add_column(
        APPLICATIONS_TABLE,
        sa.Column("sanitary_campaign_id", postgresql.UUID(as_uuid=True), nullable=True),
        schema=SCHEMA,
    )
    op.create_foreign_key(
        "fk_treatment_applications_sanitary_campaign",
        APPLICATIONS_TABLE,
        CAMPAIGNS_TABLE,
        ["sanitary_campaign_id"],
        ["campaign_id"],
        source_schema=SCHEMA,
        referent_schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_treatment_applications_sanitary_campaign",
        APPLICATIONS_TABLE,
        schema=SCHEMA,
    )
    op.drop_column(APPLICATIONS_TABLE, "sanitary_campaign_id", schema=SCHEMA)
    op.execute(
        sa.text(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {SCHEMA}.{CAMPAIGNS_TABLE}")
    )
    op.drop_constraint("ck_sanitary_campaigns_window", CAMPAIGNS_TABLE, schema=SCHEMA)
    op.drop_table(CAMPAIGNS_TABLE, schema=SCHEMA)
