"""Separa evidencia tipada de anotacao livre na aplicacao de tratamento (Passo 10.2a).

`evidence_references` guardava texto livre. Texto livre nao sustenta prova: um
dossie que citasse "evidence:foto-1" nao permitiria a ninguem conferir nada. A
coluna passa a guardar referencias a `Evidence` do Core, na mesma convencao que
`decisions` e `nonconformities` ja usam.

Os valores existentes nao sao descartados. Eles nunca foram evidencia: eram
anotacao de operador, e vao para `evidence_notes`, que e o nome honesto deles.

Revision ID: 20260724_0042
Revises: 20260723_0041
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260724_0042"
down_revision: str | None = "20260723_0041"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "core_audit"
TABLE = "treatment_applications"


def upgrade() -> None:
    op.add_column(
        TABLE,
        sa.Column(
            "evidence_notes",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default="[]",
        ),
        schema=SCHEMA,
    )

    # Preserva o que havia antes de trocar o significado da coluna. A ordem
    # importa: copiar primeiro, esvaziar depois.
    op.execute(
        f"UPDATE {SCHEMA}.{TABLE} "
        "SET evidence_notes = evidence_references "
        "WHERE evidence_references <> '[]'::jsonb"
    )
    op.execute(f"UPDATE {SCHEMA}.{TABLE} SET evidence_references = '[]'::jsonb")


def downgrade() -> None:
    # Devolve as anotacoes a coluna de origem antes de remover o destino, para
    # que descer a migration nao perca o que subir preservou.
    op.execute(
        f"UPDATE {SCHEMA}.{TABLE} "
        "SET evidence_references = evidence_notes "
        "WHERE evidence_notes <> '[]'::jsonb"
    )
    op.drop_column(TABLE, "evidence_notes", schema=SCHEMA)
