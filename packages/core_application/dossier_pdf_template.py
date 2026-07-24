"""Contrato de template de vertical para a representação PDF (Passo 10.3).

O PLANO exige que o template do PDF seja **fornecido pela vertical**, e o Core
não pode conhecer vertical alguma. A porta resolve isso trocando **dados**, não
objetos de renderização: a vertical devolve blocos com título, colunas e linhas
de texto, e quem sabe desenhar tabela é a Infrastructure do Core.

Duas consequências úteis. A vertical não depende de biblioteca de PDF — ela não
sabe que existe PDF, só descreve o que deve ser mostrado e em que ordem. E o
resultado é conferível em teste sem gerar arquivo nenhum, o que torna a validação
"comparar JSON e PDF campo a campo" uma comparação de dados, e não de pixels.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class PdfSection:
    """Um bloco apresentável: título, cabeçalho de colunas e linhas de texto."""

    title: str
    columns: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]

    def __post_init__(self) -> None:
        if not isinstance(self.title, str) or not self.title.strip():
            raise ValueError("PdfSection exige título não vazio.")
        if not self.columns:
            raise ValueError("PdfSection exige ao menos uma coluna.")
        for row in self.rows:
            if len(row) != len(self.columns):
                raise ValueError(
                    f"Linha com {len(row)} células não cabe em {len(self.columns)} colunas."
                )


class VerticalPdfTemplate(Protocol):
    """Template que uma vertical fornece para apresentar sua própria seção."""

    @property
    def namespace(self) -> str:
        """Deve coincidir com o namespace da seção que este template apresenta."""
        ...

    def render(self, content: Mapping[str, Any]) -> Sequence[PdfSection]: ...
