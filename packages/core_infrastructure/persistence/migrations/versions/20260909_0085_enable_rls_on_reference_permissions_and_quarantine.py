"""Enable explicit RLS on permissions catalog and untrusted quarantine.

Revision ID: 20260909_0085
Revises: 20260909_0084
Create Date: 2026-09-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260909_0085"
down_revision: str | None = "20260909_0084"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

IDENTITY_SCHEMA = "core_identity"
MESSAGING_SCHEMA = "core_messaging"
PERMISSIONS_TABLE = "permissions"
QUARANTINE_TABLE = "untrusted_message_quarantine"
OWNER_CONTEXT = (
    "record_owner_organization_id = "
    "NULLIF(current_setting('titan.organization_id', true), '')::uuid"
)


def upgrade() -> None:
    op.execute(
        sa.text(f"ALTER TABLE {IDENTITY_SCHEMA}.{PERMISSIONS_TABLE} ENABLE ROW LEVEL SECURITY")
    )
    op.execute(
        sa.text(f"ALTER TABLE {IDENTITY_SCHEMA}.{PERMISSIONS_TABLE} FORCE ROW LEVEL SECURITY")
    )
    op.execute(
        sa.text(
            "CREATE POLICY permissions_select_reference_catalog ON "
            f"{IDENTITY_SCHEMA}.{PERMISSIONS_TABLE} FOR SELECT USING (true)"
        )
    )
    op.execute(
        sa.text(
            "CREATE POLICY permissions_insert_by_owner ON "
            f"{IDENTITY_SCHEMA}.{PERMISSIONS_TABLE} FOR INSERT WITH CHECK ({OWNER_CONTEXT})"
        )
    )

    op.add_column(
        QUARANTINE_TABLE,
        sa.Column(
            "record_owner_organization_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        schema=MESSAGING_SCHEMA,
    )
    op.create_foreign_key(
        "fk_untrusted_message_quarantine_owner",
        QUARANTINE_TABLE,
        "organizations",
        ["record_owner_organization_id"],
        ["organization_id"],
        source_schema=MESSAGING_SCHEMA,
        referent_schema=IDENTITY_SCHEMA,
    )
    op.execute(
        sa.text(
            f"""
            UPDATE {MESSAGING_SCHEMA}.{QUARANTINE_TABLE}
            SET record_owner_organization_id = alleged_organization::uuid
            WHERE alleged_organization IS NOT NULL
              AND alleged_organization ~* '^[0-9a-f]{{8}}-[0-9a-f]{{4}}-[0-9a-f]{{4}}-[0-9a-f]{{4}}-[0-9a-f]{{12}}$'
              AND EXISTS (
                  SELECT 1 FROM {IDENTITY_SCHEMA}.organizations
                  WHERE organization_id = alleged_organization::uuid
              )
            """
        )
    )
    op.execute(
        sa.text(f"ALTER TABLE {MESSAGING_SCHEMA}.{QUARANTINE_TABLE} ENABLE ROW LEVEL SECURITY")
    )
    op.execute(
        sa.text(f"ALTER TABLE {MESSAGING_SCHEMA}.{QUARANTINE_TABLE} FORCE ROW LEVEL SECURITY")
    )
    op.execute(
        sa.text(
            "CREATE POLICY untrusted_message_quarantine_select_by_owner ON "
            f"{MESSAGING_SCHEMA}.{QUARANTINE_TABLE} FOR SELECT USING ({OWNER_CONTEXT})"
        )
    )
    op.execute(
        sa.text(
            "CREATE POLICY untrusted_message_quarantine_insert_by_owner_or_unscoped ON "
            f"{MESSAGING_SCHEMA}.{QUARANTINE_TABLE} FOR INSERT WITH CHECK "
            f"(record_owner_organization_id IS NULL OR {OWNER_CONTEXT})"
        )
    )
    op.execute(sa.text(f"REVOKE ALL ON {MESSAGING_SCHEMA}.{QUARANTINE_TABLE} FROM PUBLIC"))


def downgrade() -> None:
    op.execute(
        sa.text(
            "DROP POLICY untrusted_message_quarantine_insert_by_owner_or_unscoped "
            f"ON {MESSAGING_SCHEMA}.{QUARANTINE_TABLE}"
        )
    )
    op.execute(
        sa.text(
            "DROP POLICY untrusted_message_quarantine_select_by_owner "
            f"ON {MESSAGING_SCHEMA}.{QUARANTINE_TABLE}"
        )
    )
    op.execute(
        sa.text(f"ALTER TABLE {MESSAGING_SCHEMA}.{QUARANTINE_TABLE} DISABLE ROW LEVEL SECURITY")
    )
    op.drop_constraint(
        "fk_untrusted_message_quarantine_owner",
        QUARANTINE_TABLE,
        schema=MESSAGING_SCHEMA,
    )
    op.drop_column(QUARANTINE_TABLE, "record_owner_organization_id", schema=MESSAGING_SCHEMA)
    op.execute(
        sa.text(f"DROP POLICY permissions_insert_by_owner ON {IDENTITY_SCHEMA}.{PERMISSIONS_TABLE}")
    )
    op.execute(
        sa.text(
            "DROP POLICY permissions_select_reference_catalog ON "
            f"{IDENTITY_SCHEMA}.{PERMISSIONS_TABLE}"
        )
    )
    op.execute(
        sa.text(f"ALTER TABLE {IDENTITY_SCHEMA}.{PERMISSIONS_TABLE} DISABLE ROW LEVEL SECURITY")
    )
