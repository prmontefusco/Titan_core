"""HTTP minimo para gestao de Policies versionadas (ADR-0038/Passo 6.1).

Pre-requisito do fluxo de governanca de regras (`livestock_rule_governance.py`):
publicar uma versao de regra exige um `policy_id` ja existente, e ate aqui a
unica forma de criar uma Policy era chamando `PolicyService` direto no banco
(como o roteiro `apps/validacao/governanca_regras.py` faz). Este router expoe
o mesmo `PolicyService` -- ja completo -- sem duplicar nenhuma regra nele.

**Por que o prefixo eh `/v1/rule-governance/policies`, e nao `/v1/policies`:**
`test_endpoints_de_dominio_do_core_continuam_fechados` proibe expressamente
publicar uma primitiva do Core (`Policy`, `Rule`, `Evaluation`, `Decision`...)
como rota generica e vertical-agnostica -- isso daria a terceiros acesso
direto ao Core sem passar por nenhum caso de uso. `RuleGovernanceService` ja
tinha a mesma tensao com `Rule` e resolveu compondo-a dentro de um caso de uso
proprio da vertical (identidade auditavel, timeline, adocao). Aqui a Policy
existe *a servico* do mesmo caso de uso -- eh a Policy a que uma regra
governada se vincula -- entao ela nasce sob o mesmo prefixo aprovado
`/v1/rule-governance`, e nao como CRUD solto do Core.
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy import Connection

from apps.api.livestock_dependencies import (
    ConnectionDependency,
    require_permission,
    typed_id_or_problem,
)
from apps.api.pagination import Pagina, PaginacaoDependency, montar_pagina
from apps.api.problem import RESPOSTAS_PADRAO, DomainProblem
from packages.core_application.policy_authorization import (
    POLICY_CRIAR,
    POLICY_LER,
    POLICY_PUBLICAR,
)
from packages.core_application.policy_service import PolicyService
from packages.core_domain import OrganizationContext
from packages.core_domain.policy import Policy
from packages.core_infrastructure.persistence.policy import TransactionalPolicyRepository

router = APIRouter(prefix="/v1/rule-governance/policies", tags=["rule-governance"])


class CriarPolicyRequest(BaseModel):
    code: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=2000)
    valid_from: datetime | None = None
    valid_to: datetime | None = None


class PublicarPolicyRequest(BaseModel):
    published_at: datetime | None = None


class PolicyResponse(BaseModel):
    policy_id: str
    organization_id: str
    code: str
    name: str
    description: str
    version: int
    status: str
    valid_from: datetime | None
    valid_to: datetime | None
    created_at: datetime
    published_at: datetime | None


def _servico(connection: Connection) -> PolicyService:
    return PolicyService(TransactionalPolicyRepository(connection))


def _resposta(policy: Policy) -> PolicyResponse:
    return PolicyResponse(
        policy_id=str(policy.policy_id.value),
        organization_id=str(policy.organization_id.value),
        code=policy.code,
        name=policy.name,
        description=policy.description,
        version=policy.version,
        status=policy.status.value,
        valid_from=policy.valid_from,
        valid_to=policy.valid_to,
        created_at=policy.created_at,
        published_at=policy.published_at,
    )


def _obter_ou_404(connection: Connection, contexto: OrganizationContext, policy_id: str) -> Policy:
    identificador = typed_id_or_problem(policy_id, entity_type="policy", campo="policy_id")
    policy = TransactionalPolicyRepository(connection).get_by_id(identificador)
    if policy is None or policy.organization_id != contexto.organization_id:
        raise DomainProblem(
            status_code=status.HTTP_404_NOT_FOUND,
            reason_code="RECURSO_NAO_ENCONTRADO",
            title="Recurso nao encontrado",
            detail="Policy nao encontrada nesta organizacao.",
        )
    return policy


@router.post(
    "",
    response_model=PolicyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Criar o rascunho de uma Policy versionada",
    responses=RESPOSTAS_PADRAO,
)
def criar_policy(
    corpo: CriarPolicyRequest,
    contexto: Annotated[OrganizationContext, Depends(require_permission(POLICY_CRIAR))],
    connection: ConnectionDependency,
) -> PolicyResponse:
    try:
        policy = _servico(connection).create_draft(
            organization_id=contexto.organization_id,
            code=corpo.code,
            name=corpo.name,
            description=corpo.description,
            valid_from=corpo.valid_from,
            valid_to=corpo.valid_to,
        )
    except ValueError as error:
        raise DomainProblem(
            status_code=status.HTTP_409_CONFLICT,
            reason_code="CONFLITO_DE_DOMINIO",
            title="Operacao recusada pelo dominio",
            detail=str(error),
        ) from error
    return _resposta(policy)


@router.post(
    "/{policy_id}/publish",
    response_model=PolicyResponse,
    summary="Publicar um rascunho de Policy",
    responses=RESPOSTAS_PADRAO,
)
def publicar_policy(
    policy_id: str,
    corpo: PublicarPolicyRequest,
    contexto: Annotated[OrganizationContext, Depends(require_permission(POLICY_PUBLICAR))],
    connection: ConnectionDependency,
) -> PolicyResponse:
    atual = _obter_ou_404(connection, contexto, policy_id)
    try:
        policy = _servico(connection).publish_policy(
            atual.policy_id, published_at=corpo.published_at
        )
    except ValueError as error:
        raise DomainProblem(
            status_code=status.HTTP_409_CONFLICT,
            reason_code="CONFLITO_DE_DOMINIO",
            title="Operacao recusada pelo dominio",
            detail=str(error),
        ) from error
    return _resposta(policy)


@router.get(
    "/{policy_id}",
    response_model=PolicyResponse,
    summary="Consultar uma Policy pelo identificador",
    responses=RESPOSTAS_PADRAO,
)
def consultar_policy(
    policy_id: str,
    contexto: Annotated[OrganizationContext, Depends(require_permission(POLICY_LER))],
    connection: ConnectionDependency,
) -> PolicyResponse:
    return _resposta(_obter_ou_404(connection, contexto, policy_id))


@router.get(
    "",
    response_model=Pagina[PolicyResponse],
    summary="Listar Policies desta Organization",
    responses=RESPOSTAS_PADRAO,
)
def listar_policies(
    contexto: Annotated[OrganizationContext, Depends(require_permission(POLICY_LER))],
    connection: ConnectionDependency,
    paginacao: PaginacaoDependency,
) -> dict[str, object]:
    policies = TransactionalPolicyRepository(connection).list_by_organization(
        contexto.organization_id,
        limit=paginacao.limite_de_sondagem,
        offset=paginacao.offset,
    )
    return montar_pagina([_resposta(item) for item in policies], paginacao)
