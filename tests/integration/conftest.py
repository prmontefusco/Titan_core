"""Guarda comum aos testes de integração.

Todo teste deste diretório exige o PostgreSQL autoritativo. Quando a variável
`TITAN_DATABASE_URL` não está configurada, o ambiente não tem banco — é o caso do
CI — e a suíte inteira é pulada em vez de falhar por conexão recusada.

A guarda vive aqui, e não em cada arquivo, porque o modo por arquivo já falhou:
catorze módulos de integração foram escritos sem ela e só quebraram ao chegar no
CI. Um único ponto torna o esquecimento impossível para os próximos.
"""

import os
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import Connection, create_engine, text

from apps.api.livestock_dependencies import operator_organization_id, request_connection
from apps.api.main import app
from tests.livestock_api_support import DATABASE_URL, Ambiente

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


@pytest.fixture
def ambiente() -> Iterator[Ambiente]:
    """Um ambiente por teste, desfeito ao final: nada vaza para o teste seguinte."""
    assert DATABASE_URL is not None
    engine = create_engine(DATABASE_URL)
    with engine.connect() as connection:
        transaction = connection.begin()
        montado = Ambiente(connection)

        # A API reusa esta mesma conexão e transação, para que o que ela grava
        # seja desfeito junto com o cenário.
        # O usuário `titan` é superusuário e IGNORA RLS. Sob ele, o isolamento
        # entre organizações não é exercido de verdade — a consulta de vínculos
        # enxergaria o vínculo de outra organização e o contexto seria concedido.
        # As requisições da API rodam sob um role sem BYPASSRLS, que é o único
        # jeito de a prova valer.
        role = f"titan_api_{uuid4().hex[:12]}"
        connection.execute(
            text(
                f'CREATE ROLE "{role}" NOLOGIN NOSUPERUSER NOCREATEDB '
                "NOCREATEROLE NOINHERIT NOBYPASSRLS"
            )
        )
        for schema in ("core_identity", "core_audit"):
            connection.execute(text(f'GRANT USAGE ON SCHEMA {schema} TO "{role}"'))
            connection.execute(
                text(f'GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA {schema} TO "{role}"')
            )

        originais = dict(app.dependency_overrides)

        def conexao_sob_role_restrito() -> Iterator[Connection]:
            connection.execute(text(f'SET LOCAL ROLE "{role}"'))
            try:
                yield connection
            finally:
                connection.execute(text("RESET ROLE"))

        app.dependency_overrides[request_connection] = conexao_sob_role_restrito
        os.environ["TITAN_OPERATOR_ORGANIZATION_ID"] = str(montado.operadora.organization_id.value)
        operator_organization_id.cache_clear()
        try:
            yield montado
        finally:
            # Restaura em vez de limpar: o `main` registra aqui a autenticação
            # real, e apagá-la deixaria a aplicação sem autenticação para os
            # testes seguintes.
            app.dependency_overrides.clear()
            app.dependency_overrides.update(originais)
            operator_organization_id.cache_clear()
            connection.execute(text("RESET ROLE"))
            transaction.rollback()
