"""Bootstrap do primeiro admin (ADMIN_MESTRE) de uma Organization.

Resolve o problema do ovo e da galinha do EntityTypeRequest: aprovar um pedido
exige alguém que já tenha a permissão de decisão, e ninguém chega lá por
autoatribuição (ADR-0031). Este script concede esse primeiro vínculo por fora
do fluxo de pedido/aprovação — e por isso mesmo precisa ser executado de forma
deliberada e auditável, nunca automática.

python -m uv run --locked python -m apps.bootstrap_admin
"""

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import Engine, text

from packages.core_domain import (
    ExternalIdentity,
    Membership,
    MembershipRoleAssignment,
    Organization,
    Permission,
    Role,
    User,
)
from packages.core_infrastructure.persistence import (
    AuthorizationRepository,
    MembershipRepository,
    OrganizationRepository,
    UserRepository,
    set_local_organization_context,
)
from packages.core_infrastructure.persistence.database import (
    DatabaseSettings,
    create_database_engine,
)
from packages.core_infrastructure.persistence.external_identities import (
    ExternalIdentityRepository,
)
from packages.livestock_application.authorization import ADMIN_MESTRE, ROLE_PERMISSIONS
from packages.shared_kernel import OrganizationId, TypedId


class BootstrapAdminConfigurationError(ValueError):
    """Configuração administrativa ausente ou inválida."""


@dataclass(frozen=True, slots=True)
class BootstrapAdminSettings:
    operator_organization_id: OrganizationId
    target_organization_id: OrganizationId
    issuer: str
    subject: str
    authority_actor_id: UUID

    @classmethod
    def from_environment(cls) -> "BootstrapAdminSettings":
        def _obrigatoria(nome: str) -> str:
            valor = os.environ.get(nome, "").strip()
            if not valor:
                raise BootstrapAdminConfigurationError(f"{nome} não foi definida.")
            return valor

        try:
            operadora = OrganizationId.parse(_obrigatoria("TITAN_OPERATOR_ORGANIZATION_ID"))
            organizacao = OrganizationId.parse(_obrigatoria("TITAN_BOOTSTRAP_ORGANIZATION_ID"))
            ator = UUID(_obrigatoria("TITAN_BOOTSTRAP_AUTHORITY_ACTOR_ID"))
        except ValueError as erro:
            raise BootstrapAdminConfigurationError(str(erro)) from erro

        return cls(
            operator_organization_id=operadora,
            target_organization_id=organizacao,
            issuer=_obrigatoria("TITAN_BOOTSTRAP_ISSUER"),
            subject=_obrigatoria("TITAN_BOOTSTRAP_SUBJECT"),
            authority_actor_id=ator,
        )


def apply_admin_bootstrap(engine: Engine, settings: BootstrapAdminSettings) -> dict[str, str]:
    """Concede ADMIN_MESTRE a `(issuer, subject)` na Organization-alvo.

    Idempotente em cada passo — reexecutar com os mesmos parâmetros reusa
    Organization, User/ExternalIdentity e Role já existentes, e só cria o que
    faltar. A exceção é a última etapa (Membership e atribuição): nada no
    domínio impede duas Membership do mesmo User na mesma Organization, então
    rodar duas vezes concede dois vínculos redundantes — inofensivo, mas quem
    reexecuta deve saber que essa parte não se protege sozinha.
    """
    agora = datetime.now(UTC)
    with engine.begin() as connection:
        set_local_organization_context(connection, settings.target_organization_id)
        existe_organizacao = connection.execute(
            text("SELECT 1 FROM core_identity.organizations WHERE organization_id = :o"),
            {"o": settings.target_organization_id.value},
        ).scalar_one_or_none()
        if existe_organizacao is None:
            OrganizationRepository(connection).add(
                Organization(organization_id=settings.target_organization_id)
            )

        set_local_organization_context(connection, settings.operator_organization_id)
        vinculo_existente = connection.execute(
            text(
                "SELECT internal_principal_id FROM core_identity.external_identities "
                "WHERE issuer = :i AND subject = :s"
            ),
            {"i": settings.issuer, "s": settings.subject},
        ).scalar_one_or_none()
        if vinculo_existente is not None:
            user_id = TypedId(entity_type="user", value=vinculo_existente)
        else:
            usuario = User.create(
                platform_operator_organization_id=settings.operator_organization_id
            )
            UserRepository(connection).add(usuario)
            ExternalIdentityRepository(connection).add(
                ExternalIdentity.link_user(
                    operator_organization_id=settings.operator_organization_id,
                    issuer=settings.issuer,
                    subject=settings.subject,
                    user_id=usuario.user_id,
                    linked_at=agora,
                    linked_by_actor_id=TypedId(
                        entity_type="actor", value=settings.authority_actor_id
                    ),
                )
            )
            user_id = usuario.user_id

        set_local_organization_context(connection, settings.target_organization_id)
        autorizacao = AuthorizationRepository(connection)
        papel = autorizacao.get_role_by_name(settings.target_organization_id, ADMIN_MESTRE)
        if papel is None:
            permission_ids: list[TypedId] = []
            for codigo in sorted(ROLE_PERMISSIONS[ADMIN_MESTRE]):
                permission_id = autorizacao.get_permission_id_by_code(codigo)
                if permission_id is None:
                    permissao = Permission.create(
                        operator_organization_id=settings.operator_organization_id,
                        code=codigo,
                    )
                    autorizacao.add_permission(permissao)
                    permission_id = permissao.permission_id
                permission_ids.append(permission_id)
            papel = Role.create(
                organization_id=settings.target_organization_id,
                name=ADMIN_MESTRE,
                permission_ids=tuple(permission_ids),
            )
            autorizacao.add_role(papel)

        vinculo = Membership.create(
            user_id=user_id,
            organization_id=settings.target_organization_id,
            valid_from=agora,
            valid_until=None,
            origin_reference=TypedId.new("platform_bootstrap"),
            granted_by_actor_id=TypedId(entity_type="actor", value=settings.authority_actor_id),
        )
        MembershipRepository(connection).add(vinculo)
        autorizacao.assign_role(
            MembershipRoleAssignment.create(
                membership_id=vinculo.membership_id,
                role_id=papel.role_id,
                organization_id=settings.target_organization_id,
                valid_from=agora,
                valid_until=None,
                granted_by_actor_id=TypedId(entity_type="actor", value=settings.authority_actor_id),
            )
        )

    return {
        "organization_id": str(settings.target_organization_id.value),
        "user_id": str(user_id.value),
        "role_id": str(papel.role_id.value),
        "membership_id": str(vinculo.membership_id.value),
    }


def main() -> None:
    if os.environ.get("TITAN_BOOTSTRAP_ADMIN_CONFIRM") != "1":
        raise SystemExit(
            "Concede acesso administrativo real. Confirme com TITAN_BOOTSTRAP_ADMIN_CONFIRM=1."
        )
    settings = BootstrapAdminSettings.from_environment()
    engine = create_database_engine(DatabaseSettings.from_environment())
    try:
        resultado = apply_admin_bootstrap(engine, settings)
    finally:
        engine.dispose()
    print(json.dumps(resultado, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
