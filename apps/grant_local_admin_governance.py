"""Concede papéis operacionais extras ao vínculo de um usuário, localmente.

`apps.bootstrap_admin` concede deliberadamente só o mínimo — aprovar/ler
pedidos de tipo de entidade (ver o docstring dele e o comentário de
`ADMIN_MESTRE` em `packages/livestock_application/authorization.py`: "admin
com toda LEITURA ou ESCRITA sem evidência de necessidade seria conveniência,
não capacidade comprovada"). Depois de um reset local, quem quer testar o
produto de ponta a ponta como o próprio usuário administrador precisa de mais
que isso, e este script concede exatamente o que cada caso de uso real já
provou precisar — sem alterar `ADMIN_MESTRE` nem inventar um papel de
produção:

- `GOVERNANCA_DE_REGRAS_LOCAL` — RULE_GOVERNANCE.* e POLICY.* (tela de
  Regras de mercado).
- `OPERADOR_LOCAL` — o mesmo conjunto de LIVESTOCK_PERMISSIONS de
  `OPERADOR_PECUARIO` (buscar/cadastrar animal, lote, tratamento etc.).

Cria a permissão que ainda não existir (mesmo padrão de
`apps/seed/__main__.py::_permissoes`), então nunca depende de rodar depois
de `apps.seed`. Idempotente: reexecutar reusa cada papel e não duplica
atribuição.

Vive em `apps/`, e não em `scripts/`, porque importa de `packages/` --
rodar como caminho de arquivo (`python scripts/....py`) não coloca a raiz do
repositório no `sys.path`, só o módulo (`python -m apps....`) faz isso.

Uso:
    $env:TITAN_DATABASE_URL = "postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
    $env:TITAN_OPERATOR_ORGANIZATION_ID = "<uuid da Organization operadora>"
    $env:TITAN_GRANT_ORGANIZATION_ID = "<uuid da Organization de uso>"
    $env:TITAN_GRANT_ISSUER = "http://localhost:8080/realms/titan"
    $env:TITAN_GRANT_SUBJECT = "<subject do usuario no Keycloak>"
    python -m uv run --locked python -m apps.grant_local_admin_governance
"""

import os
from datetime import UTC, datetime

from sqlalchemy import Connection, text

from packages.core_application.policy_authorization import POLICY_PERMISSIONS
from packages.core_application.rule_governance_authorization import RULE_GOVERNANCE_PERMISSIONS
from packages.core_domain import MembershipRoleAssignment, Permission, Role
from packages.core_infrastructure.persistence import (
    AuthorizationRepository,
    set_local_organization_context,
)
from packages.core_infrastructure.persistence.database import (
    DatabaseSettings,
    create_database_engine,
)
from packages.livestock_application.authorization import OPERADOR_PECUARIO, ROLE_PERMISSIONS
from packages.shared_kernel import OrganizationId, TypedId

PAPEIS_CONCEDIDOS: dict[str, frozenset[str]] = {
    "GOVERNANCA_DE_REGRAS_LOCAL": RULE_GOVERNANCE_PERMISSIONS | POLICY_PERMISSIONS,
    "OPERADOR_LOCAL": ROLE_PERMISSIONS[OPERADOR_PECUARIO],
}


def _obrigatoria(nome: str) -> str:
    valor = os.environ.get(nome, "").strip()
    if not valor:
        raise SystemExit(f"Defina {nome} antes de rodar este script.")
    return valor


def _resolver_permission_ids(
    connection: Connection,
    autorizacao: AuthorizationRepository,
    operadora: OrganizationId,
    codigos: frozenset[str],
) -> tuple[TypedId, ...]:
    permission_ids: list[TypedId] = []
    for codigo in sorted(codigos):
        permission_id = autorizacao.get_permission_id_by_code(codigo)
        if permission_id is None:
            permissao = Permission.create(operator_organization_id=operadora, code=codigo)
            autorizacao.add_permission(permissao)
            permission_id = permissao.permission_id
        permission_ids.append(permission_id)
    return tuple(permission_ids)


def _conceder_papel(
    autorizacao: AuthorizationRepository,
    organization_id: OrganizationId,
    membership_id: TypedId,
    nome_papel: str,
    permission_ids: tuple[TypedId, ...],
) -> None:
    papel = autorizacao.get_role_by_name(organization_id, nome_papel)
    if papel is None:
        papel = Role.create(
            organization_id=organization_id, name=nome_papel, permission_ids=permission_ids
        )
        autorizacao.add_role(papel)
        print(f"Papel '{nome_papel}' criado.")
    else:
        print(f"Papel '{nome_papel}' já existia, reusado.")

    agora = datetime.now(UTC)
    if papel.role_id in autorizacao.effective_role_ids(membership_id, agora):
        print(f"Papel '{nome_papel}' já estava atribuído a este vínculo.")
        return

    autorizacao.assign_role(
        MembershipRoleAssignment.create(
            membership_id=membership_id,
            role_id=papel.role_id,
            organization_id=organization_id,
            valid_from=agora,
            valid_until=None,
            granted_by_actor_id=TypedId.new("actor"),
        )
    )
    print(f"Papel '{nome_papel}' atribuído ao vínculo {membership_id.value}.")


def main() -> None:
    operadora = OrganizationId.parse(_obrigatoria("TITAN_OPERATOR_ORGANIZATION_ID"))
    organization_id = OrganizationId.parse(_obrigatoria("TITAN_GRANT_ORGANIZATION_ID"))
    issuer = _obrigatoria("TITAN_GRANT_ISSUER")
    subject = _obrigatoria("TITAN_GRANT_SUBJECT")

    engine = create_database_engine(DatabaseSettings.from_environment())

    with engine.begin() as connection:
        set_local_organization_context(connection, organization_id)

        membership_id_raw = connection.execute(
            text(
                """
                SELECT m.membership_id
                FROM core_identity.memberships m
                JOIN core_identity.external_identities ei
                  ON ei.internal_principal_id = m.user_id
                WHERE ei.issuer = :issuer AND ei.subject = :subject
                  AND m.organization_id = :org
                  AND m.status = 'ATIVA'
                ORDER BY m.valid_from DESC
                LIMIT 1
                """
            ),
            {"issuer": issuer, "subject": subject, "org": organization_id.value},
        ).scalar_one_or_none()
        if membership_id_raw is None:
            raise SystemExit(
                f"Nenhum vínculo ATIVA para (issuer={issuer}, subject={subject}) em "
                f"{organization_id.value}. Rode apps.bootstrap_admin antes."
            )
        membership_id = TypedId("membership", membership_id_raw)

        autorizacao = AuthorizationRepository(connection)
        for nome_papel, codigos in PAPEIS_CONCEDIDOS.items():
            permission_ids = _resolver_permission_ids(connection, autorizacao, operadora, codigos)
            _conceder_papel(autorizacao, organization_id, membership_id, nome_papel, permission_ids)


if __name__ == "__main__":
    main()
