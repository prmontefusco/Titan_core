"""Concede RULE_GOVERNANCE.* e POLICY.* ao vínculo de um usuário, localmente.

`apps.bootstrap_admin` concede deliberadamente só o mínimo — aprovar/ler
pedidos de tipo de entidade (ver o docstring dele: resolve o ovo-e-a-galinha
do primeiro admin, nada além disso). Depois de um reset local, quem quer
testar a tela de Regras de mercado também precisa de `RULE_GOVERNANCE.*` e
`POLICY.*`, e este script fecha essa lacuna sem alterar o escopo do
bootstrap_admin nem inventar um papel de produção.

Cria a permissão que ainda não existir (mesmo padrão de
`apps/seed/__main__.py::_permissoes`), então nunca depende de rodar depois
de `apps.seed`. Idempotente: reexecutar reusa o papel e não duplica a
atribuição.

Uso:
    $env:TITAN_DATABASE_URL = "postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
    $env:TITAN_OPERATOR_ORGANIZATION_ID = "<uuid da Organization operadora>"
    $env:TITAN_GRANT_ORGANIZATION_ID = "<uuid da Organization de uso>"
    $env:TITAN_GRANT_ISSUER = "http://localhost:8080/realms/titan"
    $env:TITAN_GRANT_SUBJECT = "<subject do usuario no Keycloak>"
    python -m uv run --locked python scripts/grant_local_admin_governance.py
"""

import os
from datetime import UTC, datetime

from sqlalchemy import text

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
from packages.shared_kernel import OrganizationId, TypedId

NOME_PAPEL = "GOVERNANCA_DE_REGRAS_LOCAL"


def _obrigatoria(nome: str) -> str:
    valor = os.environ.get(nome, "").strip()
    if not valor:
        raise SystemExit(f"Defina {nome} antes de rodar este script.")
    return valor


def main() -> None:
    operadora = OrganizationId.parse(_obrigatoria("TITAN_OPERATOR_ORGANIZATION_ID"))
    organization_id = OrganizationId.parse(_obrigatoria("TITAN_GRANT_ORGANIZATION_ID"))
    issuer = _obrigatoria("TITAN_GRANT_ISSUER")
    subject = _obrigatoria("TITAN_GRANT_SUBJECT")

    engine = create_database_engine(DatabaseSettings.from_environment())
    codigos = sorted(RULE_GOVERNANCE_PERMISSIONS | POLICY_PERMISSIONS)

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
        permission_ids: list[TypedId] = []
        for codigo in codigos:
            permission_id = autorizacao.get_permission_id_by_code(codigo)
            if permission_id is None:
                permissao = Permission.create(operator_organization_id=operadora, code=codigo)
                autorizacao.add_permission(permissao)
                permission_id = permissao.permission_id
            permission_ids.append(permission_id)

        papel = autorizacao.get_role_by_name(organization_id, NOME_PAPEL)
        if papel is None:
            papel = Role.create(
                organization_id=organization_id,
                name=NOME_PAPEL,
                permission_ids=tuple(permission_ids),
            )
            autorizacao.add_role(papel)
            print(f"Papel '{NOME_PAPEL}' criado.")
        else:
            print(f"Papel '{NOME_PAPEL}' já existia, reusado.")

        agora = datetime.now(UTC)
        if papel.role_id in autorizacao.effective_role_ids(membership_id, agora):
            print("Papel já estava atribuído a este vínculo.")
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
        print(f"Papel '{NOME_PAPEL}' atribuído ao vínculo {membership_id.value}.")


if __name__ == "__main__":
    main()
