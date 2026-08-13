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

import pytest
from sqlalchemy import Connection, create_engine, text

from apps.api.livestock_dependencies import operator_organization_id, request_connection
from apps.api.main import app
from tests.livestock_api_support import DATABASE_URL, Ambiente

_INTEGRATION_DIR = Path(__file__).parent
_RUNTIME_ROLE_ENVIRONMENT_VARIABLE = "TITAN_RUNTIME_DATABASE_ROLE"
_DEFAULT_RUNTIME_ROLE = "titan_app"


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

        # A fixture semeia e reverte pelo administrador. A API usa a role de
        # runtime na mesma transação, mantendo os dados semeados visíveis e RLS
        # efetivo sem conceder permissões próprias a uma role de teste.
        role = os.environ.get(_RUNTIME_ROLE_ENVIRONMENT_VARIABLE, _DEFAULT_RUNTIME_ROLE)
        role_row = connection.execute(
            text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = :role"),
            {"role": role},
        ).one_or_none()
        assert role_row is not None, f"Role de runtime {role!r} inexistente."
        assert not role_row.rolsuper and not role_row.rolbypassrls
        quoted_role = connection.dialect.identifier_preparer.quote(role)

        originais = dict(app.dependency_overrides)

        def conexao_sob_role_restrito() -> Iterator[Connection]:
            connection.execute(text(f"SET LOCAL ROLE {quoted_role}"))
            try:
                assert connection.execute(text("SELECT current_user")).scalar_one() == role
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
