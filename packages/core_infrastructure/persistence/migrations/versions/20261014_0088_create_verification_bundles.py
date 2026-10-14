"""Persist byte-identical VerificationBundles append-only (ADR-0083).

Revision ID: 20261014_0088
Revises: 20260916_0087
Create Date: 2026-10-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261014_0088"
down_revision: str | None = "20260916_0087"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "core_audit"
TABLE = "verification_bundles"


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_dossiers_owner_dossier",
        "dossiers",
        ["record_owner_organization_id", "dossier_id"],
        schema=SCHEMA,
    )
    op.create_table(
        TABLE,
        sa.Column("bundle_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("record_owner_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dossier_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("purpose", sa.String(255), nullable=False),
        sa.Column("audience", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("format_version", sa.Integer(), nullable=False),
        sa.Column("serialization_version", sa.String(80), nullable=False),
        sa.Column("manifest_digest", sa.String(64), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("serialized_payload_digest", sa.String(64), nullable=False),
        sa.Column("serialized_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("payload_bytes", sa.LargeBinary(), nullable=False),
        sa.CheckConstraint("serialized_size_bytes > 0", name="ck_verification_bundle_size"),
        sa.CheckConstraint(
            "octet_length(payload_bytes) = serialized_size_bytes",
            name="ck_verification_bundle_payload_size",
        ),
        sa.CheckConstraint(
            "content_type = 'application/json'",
            name="ck_verification_bundle_content_type",
        ),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id"],
            ["core_identity.organizations.organization_id"],
            name="fk_verification_bundles_organization",
        ),
        sa.ForeignKeyConstraint(
            ["record_owner_organization_id", "dossier_id"],
            [
                "core_audit.dossiers.record_owner_organization_id",
                "core_audit.dossiers.dossier_id",
            ],
            name="fk_verification_bundles_owner_dossier",
        ),
        sa.UniqueConstraint(
            "record_owner_organization_id",
            "bundle_id",
            name="uq_verification_bundles_owner_bundle",
        ),
        schema=SCHEMA,
        comment="titan.classification=PROTECTED;titan.module_owner=core_audit",
    )
    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{TABLE} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {SCHEMA}.{TABLE} FORCE ROW LEVEL SECURITY"))
    owner_context = (
        "record_owner_organization_id = "
        "NULLIF(current_setting('titan.organization_id', true), '')::uuid"
    )
    op.execute(
        sa.text(
            f"CREATE POLICY {TABLE}_select_by_owner ON {SCHEMA}.{TABLE} "
            f"FOR SELECT USING ({owner_context})"
        )
    )
    op.execute(
        sa.text(
            f"CREATE POLICY {TABLE}_insert_by_owner ON {SCHEMA}.{TABLE} "
            f"FOR INSERT WITH CHECK ({owner_context})"
        )
    )
    op.execute(
        sa.text(
            f"""
            CREATE FUNCTION {SCHEMA}.reject_verification_bundle_mutation()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                RAISE EXCEPTION 'VERIFICATION_BUNDLE_IMUTAVEL' USING ERRCODE = '55000';
            END;
            $$
            """
        )
    )
    op.execute(
        sa.text(
            f"CREATE TRIGGER verification_bundles_reject_update_delete "
            f"BEFORE UPDATE OR DELETE ON {SCHEMA}.{TABLE} FOR EACH ROW "
            f"EXECUTE FUNCTION {SCHEMA}.reject_verification_bundle_mutation()"
        )
    )
    op.execute(
        sa.text(
            f"CREATE TRIGGER verification_bundles_reject_truncate "
            f"BEFORE TRUNCATE ON {SCHEMA}.{TABLE} FOR EACH STATEMENT "
            f"EXECUTE FUNCTION {SCHEMA}.reject_verification_bundle_mutation()"
        )
    )
    op.execute(sa.text(f"REVOKE UPDATE, DELETE, TRUNCATE ON {SCHEMA}.{TABLE} FROM PUBLIC"))


def downgrade() -> None:
    op.execute(
        sa.text(f"DROP TRIGGER IF EXISTS verification_bundles_reject_truncate ON {SCHEMA}.{TABLE}")
    )
    op.execute(
        sa.text(
            f"DROP TRIGGER IF EXISTS verification_bundles_reject_update_delete ON {SCHEMA}.{TABLE}"
        )
    )
    op.drop_table(TABLE, schema=SCHEMA)
    op.execute(sa.text(f"DROP FUNCTION {SCHEMA}.reject_verification_bundle_mutation()"))
    op.drop_constraint("uq_dossiers_owner_dossier", "dossiers", schema=SCHEMA)
