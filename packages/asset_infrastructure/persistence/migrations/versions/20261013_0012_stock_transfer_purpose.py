"""Adicionar purpose às transferências de estoque.

Revision ID: 20261013_0012
Revises: 20261008_0011
Create Date: 2026-10-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261013_0012"
down_revision: str | None = "20261008_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "core_audit"


def upgrade() -> None:
    op.add_column(
        "stock_transfers",
        sa.Column("purpose", sa.String(length=30), nullable=True),
        schema=SCHEMA,
    )
    op.execute(
        sa.text(
            """
            UPDATE core_audit.stock_transfers AS transfer
            SET purpose = (
                SELECT min(source.purpose) AS purpose
                FROM core_audit.stock_positions AS source
                JOIN core_audit.stock_positions AS destination
                  ON destination.record_owner_organization_id = source.record_owner_organization_id
                 AND destination.part_id = source.part_id
                 AND destination.purpose = source.purpose
                WHERE source.record_owner_organization_id = transfer.record_owner_organization_id
                  AND source.part_id = transfer.part_id
                  AND source.location_id = transfer.from_location_id
                  AND destination.location_id = transfer.to_location_id
                HAVING count(DISTINCT source.purpose) = 1
            )
            """
        )
    )
    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM core_audit.stock_transfers WHERE purpose IS NULL
                ) THEN
                    RAISE EXCEPTION
                        'Não foi possível inferir purpose de StockTransfer legada';
                END IF;
            END $$
            """
        )
    )
    op.alter_column("stock_transfers", "purpose", nullable=False, schema=SCHEMA)


def downgrade() -> None:
    op.drop_column("stock_transfers", "purpose", schema=SCHEMA)
