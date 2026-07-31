"""Raiz de composição HTTP da vertical Livestock (Passo 10.4a).

Aqui a requisição atravessa a pilha inteira:

    HTTP → OIDC → AuthenticatedPrincipal → OrganizationContext → Permission
         → Application Service → transação → contexto RLS → repositório → PostgreSQL

Três decisões que valem o comentário:

**Uma transação por requisição.** Ou tudo é gravado, ou nada. É o que impede a
entidade ficar salva sem o evento correspondente — o registro e a prova nascem
juntos ou não nascem.

**O RLS é configurado dentro da transação.** `set_config(..., true)` é local à
transação, então o isolamento acompanha exatamente a unidade de trabalho e não
sobra para a conexão seguinte no pool.

**A rota exige permissão, nunca papel.** Ver `livestock_application.authorization`.
"""

import os
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from functools import lru_cache
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, status
from sqlalchemy import Connection, Engine, text

from apps.api.authentication import require_authenticated_principal
from apps.api.problem import DomainProblem
from packages.core_application.organization_context import (
    OrganizationContextDenied,
    OrganizationContextService,
)
from packages.core_domain import (
    AuthenticatedPrincipal,
    ExternalIdentity,
    OrganizationContext,
    User,
)
from packages.core_infrastructure.organization_context import (
    PostgresqlIdentityAndAccessReader,
)
from packages.core_infrastructure.persistence.database import (
    DatabaseSettings,
    create_database_engine,
)
from packages.core_infrastructure.persistence.external_identities import (
    ExternalIdentityRepository,
)
from packages.core_infrastructure.persistence.organizations import set_local_organization_context
from packages.core_infrastructure.persistence.users import UserRepository
from packages.livestock_application.event_recorder import LivestockOperationContext
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference

ORGANIZATION_HEADER = "X-Titan-Organization-Id"


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    return create_database_engine(DatabaseSettings.from_environment(os.environ))


@lru_cache(maxsize=1)
def operator_organization_id() -> OrganizationId:
    """A Organization operadora, dona dos registros de User (ADR-0030).

    O leitor de identidade precisa dela para resolver o principal **antes** de
    saber em que organização ele quer operar — a identidade vive na operadora, o
    vínculo é que aponta para a organização de destino.
    """
    raw = os.environ.get("TITAN_OPERATOR_ORGANIZATION_ID", "")
    if not raw:
        raise RuntimeError("TITAN_OPERATOR_ORGANIZATION_ID não foi definida.")
    return OrganizationId.parse(raw)


def request_connection() -> Iterator[Connection]:
    """Conexão e transação com o tempo de vida da requisição."""
    with get_engine().connect() as connection, connection.begin():
        yield connection


ConnectionDependency = Annotated[Connection, Depends(request_connection)]


def _requested_organization(raw: str | None) -> OrganizationId:
    if not raw:
        raise DomainProblem(
            status_code=status.HTTP_400_BAD_REQUEST,
            reason_code="ORGANIZACAO_NAO_INFORMADA",
            title="Organização não informada",
            detail=f"O cabeçalho {ORGANIZATION_HEADER} é obrigatório.",
        )
    try:
        return OrganizationId.parse(raw)
    except (ValueError, TypeError) as error:
        raise DomainProblem(
            status_code=status.HTTP_400_BAD_REQUEST,
            reason_code="ORGANIZACAO_INVALIDA",
            title="Organização inválida",
            detail=f"O cabeçalho {ORGANIZATION_HEADER} deve conter um UUID.",
        ) from error


def resolve_organization_context(
    principal: AuthenticatedPrincipal,
    connection: Connection,
    raw_organization: str | None,
) -> OrganizationContext:
    """Resolve o contexto e arma o RLS da transação corrente."""
    organization_id = _requested_organization(raw_organization)
    servico = OrganizationContextService(
        reader=PostgresqlIdentityAndAccessReader(
            connection=connection,
            operator_organization_id=operator_organization_id(),
        )
    )
    try:
        contexto = servico.build(
            principal=principal,
            requested_organization_id=organization_id,
            instant=datetime.now(UTC),
        )
    except OrganizationContextDenied as error:
        # Negação indistinguível: vínculo ausente, inválido ou invisível respondem
        # igual, para a resposta não virar oráculo sobre o que existe noutra
        # organização.
        raise DomainProblem(
            status_code=status.HTTP_403_FORBIDDEN,
            reason_code="CONTEXTO_ORGANIZACIONAL_NEGADO",
            title="Acesso negado à organização",
            detail="O principal autenticado não opera nesta organização.",
        ) from error

    connection.execute(
        text("SELECT set_config('titan.organization_id', :organization_id, true)"),
        {"organization_id": str(contexto.organization_id.value)},
    )
    return contexto


def require_permission(code: str) -> Callable[..., OrganizationContext]:
    """Dependência que exige uma permissão nomeada, e devolve o contexto.

    Recebe permissão, e não papel: papéis novos passam a existir sem que nenhuma
    rota mude.
    """

    def dependency(
        principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_principal)],
        connection: ConnectionDependency,
        organizacao: Annotated[str | None, Header(alias=ORGANIZATION_HEADER)] = None,
    ) -> OrganizationContext:
        contexto = resolve_organization_context(principal, connection, organizacao)
        if code not in contexto.permission_codes:
            raise DomainProblem(
                status_code=status.HTTP_403_FORBIDDEN,
                reason_code="PERMISSAO_AUSENTE",
                title="Permissão ausente",
                detail=f"A operação exige a permissão {code}.",
            )
        return contexto

    return dependency


def operation_context(contexto: OrganizationContext) -> LivestockOperationContext:
    """Traduz o contexto do Core no contexto de operação da vertical.

    A autoria vem do principal autenticado, e não de um parâmetro do corpo: quem
    registra o fato é quem apresentou a credencial. A origem declara que o fato
    entrou por requisição HTTP, o que distingue captura online de sincronização
    offline quando esta existir. A correlação é uma por requisição, o que amarra
    numa unidade os eventos que uma mesma chamada produzir.
    """
    return LivestockOperationContext(
        organization_id=contexto.organization_id,
        actor_reference=UniversalReference(
            target_id=contexto.actor_id,
            organization_id=contexto.organization_id,
            contract_version=1,
        ),
        source_reference=UniversalReference(
            target_id=TypedId.new("http_request"),
            organization_id=contexto.organization_id,
            contract_version=1,
        ),
        correlation_id=TypedId.new("correlation"),
    )


def typed_id_or_problem(raw: str, *, entity_type: str, campo: str) -> TypedId:
    """Identificador malformado é erro do cliente, e ele precisa saber qual campo."""
    try:
        return TypedId.parse(entity_type, raw)
    except (ValueError, TypeError) as error:
        raise DomainProblem(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            reason_code="IDENTIFICADOR_INVALIDO",
            title="Identificador inválido",
            detail=f"O campo {campo} deve conter um UUID.",
        ) from error


def uuid_or_problem(raw: str, *, campo: str) -> UUID:
    try:
        return UUID(raw)
    except (ValueError, AttributeError) as error:
        raise DomainProblem(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            reason_code="IDENTIFICADOR_INVALIDO",
            title="Identificador inválido",
            detail=f"O campo {campo} deve conter um UUID.",
        ) from error


def resolve_or_provision_user(
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_principal)],
    connection: ConnectionDependency,
) -> TypedId:
    """Resolve o User vinculado ao principal, criando o vínculo no primeiro contato.

    Pedir para ser um tipo de entidade (EntityTypeRequest) é, por definição, algo
    que quem ainda não tem Membership faz — não dá para exigir OrganizationContext
    aqui, ele não existe ainda. A ADR-0005 permite criação automática de User "se
    permitida, com política e auditoria próprias" (não por claim do provider, e
    nunca concedendo Membership ou Role sozinha): esta é essa política, restrita a
    este único ponto de entrada, e auditável pelo próprio ExternalIdentity criado.
    """
    operadora = operator_organization_id()
    set_local_organization_context(connection, operadora)
    identidade = ExternalIdentityRepository(connection).resolve(principal)
    if identidade is not None:
        return identidade.internal_principal_id

    usuario = User.create(platform_operator_organization_id=operadora)
    UserRepository(connection).add(usuario)
    ExternalIdentityRepository(connection).add(
        ExternalIdentity.link_user(
            operator_organization_id=operadora,
            issuer=principal.issuer,
            subject=principal.subject,
            user_id=usuario.user_id,
            linked_at=datetime.now(UTC),
            linked_by_actor_id=TypedId(entity_type="actor", value=usuario.user_id.value),
        )
    )
    return usuario.user_id


UserIdDependency = Annotated[TypedId, Depends(resolve_or_provision_user)]
