"""Adicionar perfis de autoridade decisoria e emissao em decisions (T3 ADR-0048).

Revision ID: 20260730_0060
Revises: 20260729_0059
Create Date: 2026-07-30
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260730_0060"
down_revision = "20260729_0059"
branch_labels = None
depends_on = None

SCHEMA = "core_audit"
DECISIONS_TABLE = "decisions"
AUTHORITY_TABLE = "decision_authority_profiles"
LEGACY_PROFILE_ROLE = "LEGACY_AUTOMATED_DECISION_ENGINE"
LEGACY_PURPOSE = "LEGACY_DECISION_EMISSION"
LEGACY_EMISSION_METHOD = "AUTOMATED"

_PROFILE_UUID_SQL = """
(
    substr(md5(record_owner_organization_id::text || '|authority-profile'), 1, 8) || '-' ||
    substr(md5(record_owner_organization_id::text || '|authority-profile'), 9, 4) || '-' ||
    substr(md5(record_owner_organization_id::text || '|authority-profile'), 13, 4) || '-' ||
    substr(md5(record_owner_organization_id::text || '|authority-profile'), 17, 4) || '-' ||
    substr(md5(record_owner_organization_id::text || '|authority-profile'), 21, 12)
)::uuid
"""

_SERVICE_IDENTITY_UUID_SQL = """
(
    substr(md5(record_owner_organization_id::text || '|service-identity'), 1, 8) || '-' ||
    substr(md5(record_owner_organization_id::text || '|service-identity'), 9, 4) || '-' ||
    substr(md5(record_owner_organization_id::text || '|service-identity'), 13, 4) || '-' ||
    substr(md5(record_owner_organization_id::text || '|service-identity'), 17, 4) || '-' ||
    substr(md5(record_owner_organization_id::text || '|service-identity'), 21, 12)
)::uuid
"""


def upgrade() -> None:
    op.create_table(
        AUTHORITY_TABLE,
        sa.Column("authority_profile_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("principal_reference", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("role_name", sa.String(length=255), nullable=False),
        sa.Column("purpose", sa.String(length=255), nullable=False),
        sa.Column("emission_method", sa.String(length=50), nullable=False),
        sa.Column("approvals_required", sa.Integer(), nullable=False),
        sa.Column("max_delegated_severity", sa.String(length=50), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_decision_authority_profiles_organization",
        ),
        sa.UniqueConstraint(
            "authority_profile_id",
            "record_owner_organization_id",
            name="uq_decision_authority_profiles_id_org",
        ),
        schema=SCHEMA,
        comment="titan.classification=PROTECTED;titan.module_owner=core_audit",
    )
    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{AUTHORITY_TABLE} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{AUTHORITY_TABLE} FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            f"""
            CREATE POLICY tenant_isolation_policy ON {SCHEMA}.{AUTHORITY_TABLE}
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
        DECISIONS_TABLE,
        sa.Column("authority_profile_id", postgresql.UUID(as_uuid=True), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        DECISIONS_TABLE,
        sa.Column("authority_reference", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        DECISIONS_TABLE,
        sa.Column("emission_method", sa.String(length=50), nullable=True),
        schema=SCHEMA,
    )

    op.execute(
        sa.text(
            f"""
            INSERT INTO {SCHEMA}.{AUTHORITY_TABLE} (
                authority_profile_id,
                record_owner_organization_id,
                principal_reference,
                role_name,
                purpose,
                emission_method,
                approvals_required,
                max_delegated_severity,
                is_active,
                valid_from,
                valid_to
            )
            SELECT DISTINCT
                {_PROFILE_UUID_SQL},
                record_owner_organization_id,
                jsonb_build_object(
                    'entity_type', 'service_identity',
                    'value', {_SERVICE_IDENTITY_UUID_SQL}::text,
                    'organization_id', record_owner_organization_id::text,
                    'contract_version', 1
                ),
                :role_name,
                :purpose,
                :emission_method,
                0,
                'CRITICAL',
                TRUE,
                NULL::timestamptz,
                NULL::timestamptz
            FROM {SCHEMA}.{DECISIONS_TABLE}
            ON CONFLICT (authority_profile_id) DO NOTHING
            """
        ).bindparams(
            role_name=LEGACY_PROFILE_ROLE,
            purpose=LEGACY_PURPOSE,
            emission_method=LEGACY_EMISSION_METHOD,
        )
    )

    op.execute(
        sa.text(
            f"""
            UPDATE {SCHEMA}.{DECISIONS_TABLE}
               SET authority_profile_id = {_PROFILE_UUID_SQL},
                   authority_reference = jsonb_build_object(
                       'entity_type', 'service_identity',
                       'value', {_SERVICE_IDENTITY_UUID_SQL}::text,
                       'organization_id', record_owner_organization_id::text,
                       'contract_version', 1
                   ),
                   emission_method = :emission_method
             WHERE authority_profile_id IS NULL
                OR authority_reference IS NULL
                OR emission_method IS NULL
            """
        ).bindparams(emission_method=LEGACY_EMISSION_METHOD)
    )

    op.alter_column(
        DECISIONS_TABLE,
        "authority_profile_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
        schema=SCHEMA,
    )
    op.alter_column(
        DECISIONS_TABLE,
        "authority_reference",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        nullable=False,
        schema=SCHEMA,
    )
    op.alter_column(
        DECISIONS_TABLE,
        "emission_method",
        existing_type=sa.String(length=50),
        nullable=False,
        schema=SCHEMA,
    )
    op.create_foreign_key(
        "fk_decisions_authority_profile",
        DECISIONS_TABLE,
        AUTHORITY_TABLE,
        ["authority_profile_id", "record_owner_organization_id"],
        ["authority_profile_id", "record_owner_organization_id"],
        source_schema=SCHEMA,
        referent_schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_decisions_authority_profile",
        DECISIONS_TABLE,
        schema=SCHEMA,
        type_="foreignkey",
    )
    op.drop_column(DECISIONS_TABLE, "emission_method", schema=SCHEMA)
    op.drop_column(DECISIONS_TABLE, "authority_reference", schema=SCHEMA)
    op.drop_column(DECISIONS_TABLE, "authority_profile_id", schema=SCHEMA)
    op.execute(
        sa.text(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {SCHEMA}.{AUTHORITY_TABLE}")
    )
    op.drop_table(AUTHORITY_TABLE, schema=SCHEMA)
