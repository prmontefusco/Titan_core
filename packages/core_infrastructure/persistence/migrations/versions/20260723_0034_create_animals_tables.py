"""Criar tabelas core_audit.animals e core_audit.animal_identifiers com suporte a RLS (Passo 8.2 - Titan Livestock).

Revision ID: 20260723_0034
Revises: 20260723_0033
Create Date: 2026-07-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260723_0034"
down_revision: str | None = "20260723_0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "core_audit"
ANIMALS_TABLE = "animals"
IDENTIFIERS_TABLE = "animal_identifiers"


def upgrade() -> None:
    # 1. Tabela animals
    op.create_table(
        ANIMALS_TABLE,
        sa.Column("animal_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("birth_property_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sex", sa.String(length=20), nullable=False),
        sa.Column("breed", sa.String(length=100), nullable=True),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_animals_organization",
        ),
        sa.ForeignKeyConstraint(
            ["birth_property_id"],
            ["core_audit.rural_properties.property_id"],
            name="fk_animals_birth_property",
        ),
        comment="titan.classification=PROTECTED;titan.module_owner=titan_livestock",
        schema=SCHEMA,
    )

    op.create_index(
        "ix_animals_org_birth_prop",
        ANIMALS_TABLE,
        ["record_owner_organization_id", "birth_property_id"],
        schema=SCHEMA,
    )

    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{ANIMALS_TABLE} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{ANIMALS_TABLE} FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            f"""
            CREATE POLICY tenant_isolation_policy ON {SCHEMA}.{ANIMALS_TABLE}
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

    # 2. Tabela animal_identifiers
    op.create_table(
        IDENTIFIERS_TABLE,
        sa.Column("identifier_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("animal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("identifier_type", sa.String(length=50), nullable=False),
        sa.Column("identifier_value", sa.String(length=100), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("attached_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_animal_identifiers_organization",
        ),
        sa.ForeignKeyConstraint(
            ["animal_id"],
            ["core_audit.animals.animal_id"],
            name="fk_animal_identifiers_animal",
        ),
        comment="titan.classification=PROTECTED;titan.module_owner=titan_livestock",
        schema=SCHEMA,
    )

    op.create_index(
        "ix_animal_identifiers_search",
        IDENTIFIERS_TABLE,
        ["record_owner_organization_id", "identifier_type", "identifier_value", "state"],
        schema=SCHEMA,
    )

    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{IDENTIFIERS_TABLE} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{IDENTIFIERS_TABLE} FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            f"""
            CREATE POLICY tenant_isolation_policy ON {SCHEMA}.{IDENTIFIERS_TABLE}
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


def downgrade() -> None:
    op.execute(
        sa.text(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {SCHEMA}.{IDENTIFIERS_TABLE}")
    )
    op.drop_index("ix_animal_identifiers_search", table_name=IDENTIFIERS_TABLE, schema=SCHEMA)
    op.drop_table(IDENTIFIERS_TABLE, schema=SCHEMA)

    op.execute(
        sa.text(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {SCHEMA}.{ANIMALS_TABLE}")
    )
    op.drop_index("ix_animals_org_birth_prop", table_name=ANIMALS_TABLE, schema=SCHEMA)
    op.drop_table(ANIMALS_TABLE, schema=SCHEMA)
