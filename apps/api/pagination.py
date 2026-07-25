"""Contrato de paginação das listagens (Marco 12).

Um teto explícito existe porque listagem sem limite é o caminho mais curto para
derrubar o serviço: basta um cliente pedir tudo de uma organização grande. O
padrão é modesto e o teto é rígido — pedir acima dele é recusado, e não
silenciosamente reduzido, para o cliente não acreditar que recebeu tudo.

**A contagem total não é devolvida.** Contar exige varrer a tabela inteira a cada
página, e o custo cresce com o acervo — justamente onde a paginação deveria
aliviar. Em vez disso, `has_more` responde a única pergunta que a interface
precisa fazer: existe próxima página? Isso se obtém pedindo um registro a mais
do que o solicitado e descartando-o.
"""

from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import Depends, Query
from pydantic import BaseModel

LIMITE_PADRAO = 50
LIMITE_MAXIMO = 200


@dataclass(frozen=True, slots=True)
class Paginacao:
    limit: int
    offset: int

    @property
    def limite_de_sondagem(self) -> int:
        """Um a mais do que o pedido, para saber se há próxima página."""
        return self.limit + 1

    def recortar(self, encontrados: list[Any]) -> tuple[list[Any], bool]:
        tem_mais = len(encontrados) > self.limit
        return encontrados[: self.limit], tem_mais


def paginacao(
    limit: Annotated[int, Query(ge=1, le=LIMITE_MAXIMO)] = LIMITE_PADRAO,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Paginacao:
    return Paginacao(limit=limit, offset=offset)


PaginacaoDependency = Annotated[Paginacao, Depends(paginacao)]


class Pagina[T](BaseModel):
    """Uma página de resultados, sem total e com indicação de continuidade."""

    items: list[T]
    limit: int
    offset: int
    has_more: bool


def montar_pagina(itens: list[Any], paginacao: Paginacao) -> dict[str, Any]:
    recortados, tem_mais = paginacao.recortar(itens)
    return {
        "items": recortados,
        "limit": paginacao.limit,
        "offset": paginacao.offset,
        "has_more": tem_mais,
    }
