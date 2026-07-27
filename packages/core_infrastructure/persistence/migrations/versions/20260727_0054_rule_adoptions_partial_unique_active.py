"""Permitir historico de adocoes superseded com unicidade apenas nas ativas.

Revision ID: 20260727_0054
Revises: 20260726_0053
Create Date: 2026-07-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260727_0054"
down_revision: str | None = "20260726_0053"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "core_audit"
TABLE = "rule_adoptions"
OLD_CONSTRAINT = "uq_rule_adoptions_active_scope"
NEW_INDEX = "ix_rule_adoptions_active_scope_unique"


def upgrade() -> None:
    op.drop_constraint(OLD_CONSTRAINT, TABLE, schema=SCHEMA, type_="unique")
    op.create_index(
        NEW_INDEX,
        TABLE,
        [
            "record_owner_organization_id",
            "rule_identity_id",
            "purpose",
            "scope",
        ],
        unique=True,
        schema=SCHEMA,
        postgresql_where=sa.text("status = 'active'"),
    )


def downgrade() -> None:
    op.drop_index(NEW_INDEX, table_name=TABLE, schema=SCHEMA)
    op.create_unique_constraint(
        OLD_CONSTRAINT,
        TABLE,
        [
            "record_owner_organization_id",
            "rule_identity_id",
            "purpose",
            "scope",
            "status",
        ],
        schema=SCHEMA,
    )
