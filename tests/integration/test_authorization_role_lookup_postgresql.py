import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine

from packages.core_domain import Organization, Permission, Role
from packages.core_infrastructure.persistence import (
    AuthorizationRepository,
    OrganizationRepository,
    set_local_organization_context,
)

DATABASE_URL = os.environ.get("TITAN_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="TITAN_DATABASE_URL não configurada para teste PostgreSQL."
)


def test_get_permission_id_by_code_reencontra_permissao_ja_criada() -> None:
    assert DATABASE_URL is not None
    engine = create_engine(DATABASE_URL)
    with engine.connect() as connection, connection.begin():
        operador = Organization.create()
        set_local_organization_context(connection, operador.organization_id)
        OrganizationRepository(connection).add(operador)

        autorizacao = AuthorizationRepository(connection)
        codigo = f"TESTE_{uuid4().hex[:12].upper()}.LER"
        permissao = Permission.create(
            operator_organization_id=operador.organization_id, code=codigo
        )
        autorizacao.add_permission(permissao)

        assert autorizacao.get_permission_id_by_code(codigo) == permissao.permission_id
        assert autorizacao.get_permission_id_by_code(f"{codigo}_INEXISTENTE") is None
        connection.rollback()


def test_get_role_by_name_reencontra_role_com_suas_permissoes() -> None:
    assert DATABASE_URL is not None
    engine = create_engine(DATABASE_URL)
    with engine.connect() as connection, connection.begin():
        organizacao = Organization.create()
        set_local_organization_context(connection, organizacao.organization_id)
        OrganizationRepository(connection).add(organizacao)

        autorizacao = AuthorizationRepository(connection)
        codigo = f"TESTE_{uuid4().hex[:12].upper()}.LER"
        permissao = Permission.create(
            operator_organization_id=organizacao.organization_id, code=codigo
        )
        autorizacao.add_permission(permissao)

        nome_papel = f"papel_teste_{uuid4().hex[:8]}"
        papel = Role.create(
            organization_id=organizacao.organization_id,
            name=nome_papel,
            permission_ids=(permissao.permission_id,),
        )
        autorizacao.add_role(papel)

        encontrado = autorizacao.get_role_by_name(organizacao.organization_id, nome_papel)

        assert encontrado is not None
        assert encontrado.role_id == papel.role_id
        assert encontrado.permission_ids == (permissao.permission_id,)
        assert (
            autorizacao.get_role_by_name(organizacao.organization_id, "papel_inexistente") is None
        )
        connection.rollback()
