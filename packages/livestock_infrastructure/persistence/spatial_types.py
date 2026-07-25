"""Tipo espacial mínimo para o SQLAlchemy (Passo 17.1, ADR-0026).

**Por que não `geoalchemy2`.** A biblioteca é boa e resolve muito mais do que
isto — carregamento de geometrias como objetos Python, conversões automáticas,
suporte a dezenas de tipos. Nada disso é usado aqui: a geometria entra por
expressão SQL, é comparada dentro do banco e nunca vira objeto no domínio, que
guarda o GeoJSON declarado.

O que falta ao SQLAlchemy é apenas **saber escrever `geometry(...)` no DDL** para
que o `alembic check` compare a metadata com o banco. Trazer uma dependência de
produção por causa de uma linha de DDL seria caro pelo motivo errado — é o mesmo
critério que manteve o cliente do Keycloak na biblioteca padrão.

O escopo é deliberadamente minúsculo, e ampliá-lo é sinal de que a decisão
precisa ser revista: se o Titan passar a manipular geometria em Python, a
biblioteca especializada passa a valer o custo.
"""

from typing import Any

from sqlalchemy import types


class Geometry(types.UserDefinedType[Any]):
    """Coluna `geometry` do PostGIS, com tipo e SRID fixados no DDL.

    Fixar os dois na definição não é detalhe: uma coluna `geometry` genérica
    aceitaria ponto onde se espera polígono, e geometria sem SRID declarado não
    localiza nada — a ADR-0026 recusa as duas coisas.
    """

    cache_ok = True

    def __init__(self, geometry_type: str, srid: int) -> None:
        self.geometry_type = geometry_type
        self.srid = srid

    def get_col_spec(self, **_: Any) -> str:
        return f"geometry({self.geometry_type},{self.srid})"
