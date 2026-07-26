"""Classificacao do produto medicamentoso (Passo 14.1).

Revision ID: 20260726_0047
Revises: 20260725_0046
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260726_0047"
down_revision: str | None = "20260725_0046"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "core_audit"
TABELA = "medications"


def upgrade() -> None:
    op.add_column(
        TABELA,
        sa.Column(
            "product_class",
            sa.String(length=50),
            nullable=False,
            server_default="PHARMACOLOGICAL",
        ),
        schema=SCHEMA,
    )
    op.alter_column(TABELA, "product_class", server_default=None, schema=SCHEMA)


def downgrade() -> None:
    op.drop_column(TABELA, "product_class", schema=SCHEMA)
