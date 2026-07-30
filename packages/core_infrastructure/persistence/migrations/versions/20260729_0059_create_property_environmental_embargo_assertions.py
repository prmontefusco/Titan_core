"""Criar assercoes auditaveis de embargo ambiental por propriedade.

Congela o resultado da avaliacao espacial sobre a geometria vigente da
propriedade: fonte, camada, digests, versoes declaradas e payload minimo das
restricoes encontradas.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260729_0059"
down_revision = "20260728_0058"
branch_labels = None
depends_on = None

SCHEMA = "core_audit"
TABLE = "property_environmental_embargo_assertions"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("assertion_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("property_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("geometry_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("geometry_version", sa.Integer(), nullable=True),
        sa.Column("source_name", sa.String(length=120), nullable=False),
        sa.Column("source_layer", sa.String(length=120), nullable=False),
        sa.Column("operation", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("source_digest", sa.String(length=64), nullable=True),
        sa.Column("response_digest", sa.String(length=64), nullable=True),
        sa.Column("version_ids", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("restrictions_payload", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_property_environmental_embargo_assertions_organization",
        ),
        sa.ForeignKeyConstraint(
            ["property_id"],
            [f"{SCHEMA}.rural_properties.property_id"],
            name="fk_property_environmental_embargo_assertions_property",
        ),
        sa.ForeignKeyConstraint(
            ["geometry_id"],
            [f"{SCHEMA}.property_geometries.geometry_id"],
            name="fk_property_environmental_embargo_assertions_geometry",
        ),
        sa.PrimaryKeyConstraint("assertion_id"),
        schema=SCHEMA,
        comment="titan.classification=PROTECTED;titan.module_owner=livestock",
    )
    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{TABLE} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{TABLE} FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            f"""
            CREATE POLICY tenant_isolation_policy ON {SCHEMA}.{TABLE}
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
    op.create_index(
        "ix_property_environmental_embargo_assertions_lookup",
        TABLE,
        ["record_owner_organization_id", "property_id", "observed_at"],
        unique=False,
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_property_environmental_embargo_assertions_lookup",
        table_name=TABLE,
        schema=SCHEMA,
    )
    op.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {SCHEMA}.{TABLE}"))
    op.drop_table(TABLE, schema=SCHEMA)
