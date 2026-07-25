"""Atributos da fonte na geometria da propriedade (Passo 17.2, ADR-0026).

O CAR entrega mais do que o poligono: municipio, area, modulos fiscais, condicao
do cadastro e a data da ultima atualizacao. Descartar isso obrigaria a consultar
de novo para saber o que a importacao viu — e a consulta de amanha pode devolver
outra coisa, porque o CAR e retificavel.

`source_attributes` guarda o que veio junto, e `response_digest` identifica a
resposta INTEIRA. O digest ja existente identifica apenas o poligono: um diz qual
e o limite, o outro diz qual foi o material recebido.

Nenhum desses atributos e interpretado como conformidade. `des_condic` diz onde o
cadastro esta na fila do SICAR, e nao se a fazenda esta regular.

Revision ID: 20260725_0046
Revises: 20260725_0045
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260725_0046"
down_revision: str | None = "20260725_0045"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "core_audit"
TABELA = "property_geometries"


def upgrade() -> None:
    op.add_column(
        TABELA,
        sa.Column("source_attributes", postgresql.JSONB(), nullable=False, server_default="{}"),
        schema=SCHEMA,
    )
    op.add_column(
        TABELA,
        sa.Column("response_digest", sa.String(length=64), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        TABELA,
        sa.Column("layer_version", sa.String(length=120), nullable=True),
        schema=SCHEMA,
    )
    op.create_check_constraint(
        "ck_property_geometries_response_digest",
        TABELA,
        "response_digest IS NULL OR char_length(response_digest) = 64",
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_constraint("ck_property_geometries_response_digest", TABELA, schema=SCHEMA)
    op.drop_column(TABELA, "layer_version", schema=SCHEMA)
    op.drop_column(TABELA, "response_digest", schema=SCHEMA)
    op.drop_column(TABELA, "source_attributes", schema=SCHEMA)
