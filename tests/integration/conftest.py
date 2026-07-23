"""Guarda comum aos testes de integração.

Todo teste deste diretório exige o PostgreSQL autoritativo. Quando a variável
`TITAN_DATABASE_URL` não está configurada, o ambiente não tem banco — é o caso do
CI — e a suíte inteira é pulada em vez de falhar por conexão recusada.

A guarda vive aqui, e não em cada arquivo, porque o modo por arquivo já falhou:
catorze módulos de integração foram escritos sem ela e só quebraram ao chegar no
CI. Um único ponto torna o esquecimento impossível para os próximos.
"""

import os
from pathlib import Path

import pytest

_INTEGRATION_DIR = Path(__file__).parent


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if os.environ.get("TITAN_DATABASE_URL"):
        return

    skip_marker = pytest.mark.skip(
        reason="TITAN_DATABASE_URL não configurada: PostgreSQL indisponível neste ambiente."
    )
    for item in items:
        if _INTEGRATION_DIR in Path(str(item.path)).parents:
            item.add_marker(skip_marker)
