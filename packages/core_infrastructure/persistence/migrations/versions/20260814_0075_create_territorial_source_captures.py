"""Cria capturas territoriais sinteticas append-only.

Revision ID: 20260814_0075
Revises: 20260813_0074
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260814_0075"
down_revision = "20260813_0074"
branch_labels = None
depends_on = None

_SCHEMA = "core_audit"
_TABLE = "territorial_source_captures"
_CONTEXT = (
    "record_owner_organization_id = "
    "NULLIF(current_setting('titan.organization_id', true), '')::uuid"
)


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_rural_properties_owner_property",
        "rural_properties",
        ["record_owner_organization_id", "property_id"],
        schema=_SCHEMA,
    )
    op.create_unique_constraint(
        "uq_property_geometries_owner_geometry",
        "property_geometries",
        ["record_owner_organization_id", "geometry_id"],
        schema=_SCHEMA,
    )
    op.create_table(
        _TABLE,
        sa.Column("capture_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("property_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("geometry_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("geometry_version", sa.Integer(), nullable=False),
        sa.Column("source_profile_code", sa.String(120), nullable=False),
        sa.Column("source_environment", sa.String(40), nullable=False),
        sa.Column("source_name", sa.String(120), nullable=False),
        sa.Column("source_layer", sa.String(120), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("operation", sa.String(80), nullable=False),
        sa.Column("request_scope_digest", sa.String(64), nullable=False),
        sa.Column("response_schema", sa.String(160), nullable=False),
        sa.Column("response_schema_version", sa.Integer(), nullable=False),
        sa.Column("canonicalization_version", sa.String(120), nullable=False),
        sa.Column("response_digest", sa.String(64), nullable=False),
        sa.Column("response_summary", postgresql.JSONB(), nullable=False),
        sa.Column("source_version_ids", postgresql.JSONB(), nullable=False),
        sa.Column("source_valid_from", sa.DateTime(timezone=True)),
        sa.Column("source_valid_to", sa.DateTime(timezone=True)),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("known_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("limitations", postgresql.JSONB(), nullable=False),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_territorial_source_captures_organization",
        ),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id", "property_id"],
            [
                "core_audit.rural_properties.record_owner_organization_id",
                "core_audit.rural_properties.property_id",
            ],
            name="fk_territorial_source_captures_property_same_owner",
        ),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id", "geometry_id"],
            [
                "core_audit.property_geometries.record_owner_organization_id",
                "core_audit.property_geometries.geometry_id",
            ],
            name="fk_territorial_source_captures_geometry_same_owner",
        ),
        sa.CheckConstraint("geometry_version >= 1", name="ck_territorial_capture_geometry_version"),
        sa.CheckConstraint(
            "source_valid_to IS NULL OR source_valid_from IS NULL "
            "OR source_valid_to > source_valid_from",
            name="ck_territorial_capture_source_valid_interval",
        ),
        sa.CheckConstraint(
            "request_scope_digest ~ '^[0-9a-f]{64}$'",
            name="ck_territorial_capture_request_digest",
        ),
        sa.CheckConstraint(
            "response_digest ~ '^[0-9a-f]{64}$'",
            name="ck_territorial_capture_response_digest",
        ),
        sa.CheckConstraint(
            "source_environment = 'SYNTHETIC'",
            name="ck_territorial_capture_environment",
        ),
        sa.CheckConstraint(
            "source_profile_code = 'TERRITORIAL_TEST_SOURCE'",
            name="ck_territorial_capture_source_profile",
        ),
        sa.CheckConstraint(
            "kind IN ('TIMELINE', 'OVERLAP')",
            name="ck_territorial_capture_kind",
        ),
        sa.CheckConstraint(
            "response_schema_version >= 1",
            name="ck_territorial_capture_response_schema_version",
        ),
        sa.CheckConstraint(
            "canonicalization_version = 'TERRITORIAL_RESPONSE_SUMMARY_CANONICAL_JSON_V1'",
            name="ck_territorial_capture_canonicalization",
        ),
        sa.CheckConstraint(
            "(kind = 'TIMELINE' AND source_layer = 'TERRITORIAL_TEST_TIMELINE') OR "
            "(kind = 'OVERLAP' AND source_layer = 'TERRITORIAL_TEST_OVERLAP')",
            name="ck_territorial_capture_kind_layer",
        ),
        schema=_SCHEMA,
        comment="titan.classification=PROTECTED;titan.module_owner=livestock",
    )
    op.create_index(
        "ix_territorial_captures_property_temporal",
        _TABLE,
        [
            "record_owner_organization_id",
            "property_id",
            "source_profile_code",
            "source_layer",
            "operation",
            "known_at",
        ],
        schema=_SCHEMA,
    )
    op.execute(sa.text(f"ALTER TABLE {_SCHEMA}.{_TABLE} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {_SCHEMA}.{_TABLE} FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            f"CREATE POLICY {_TABLE}_select_by_owner ON {_SCHEMA}.{_TABLE} "
            f"FOR SELECT USING ({_CONTEXT})"
        )
    )
    op.execute(
        sa.text(
            f"CREATE POLICY {_TABLE}_insert_by_owner ON {_SCHEMA}.{_TABLE} "
            f"FOR INSERT WITH CHECK ({_CONTEXT})"
        )
    )


def downgrade() -> None:
    op.drop_table(_TABLE, schema=_SCHEMA)
    op.drop_constraint(
        "uq_property_geometries_owner_geometry", "property_geometries", schema=_SCHEMA
    )
    op.drop_constraint("uq_rural_properties_owner_property", "rural_properties", schema=_SCHEMA)
