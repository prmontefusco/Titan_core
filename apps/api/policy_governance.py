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

from datetime import UTC, datetime
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
from packages.core_application.evaluation_service import (
    PolicyEvaluationService,
    RuleEvaluationEngine,
)
from packages.core_application.policy_authorization import (
    POLICY_AVALIAR,
    POLICY_CRIAR,
    POLICY_LER,
    POLICY_PUBLICAR,
)
from packages.core_application.policy_origin import is_buyer_policy_origin, resolve_policy_origin
from packages.core_application.policy_service import PolicyService
from packages.core_domain import OrganizationContext
from packages.core_domain.policy import Policy
from packages.core_infrastructure.persistence.evaluation import TransactionalEvaluationRepository
from packages.core_infrastructure.persistence.policy import TransactionalPolicyRepository
from packages.core_infrastructure.persistence.rule import TransactionalRuleRepository
from packages.core_infrastructure.persistence.rule_governance import (
    TransactionalRuleIdentityRepository,
)
from packages.livestock_application.requirement_authority import RecognitionBoundary
from packages.livestock_infrastructure.persistence.animal_repository import (
    TransactionalAnimalRepository,
)

router = APIRouter(prefix="/v1/rule-governance/policies", tags=["rule-governance"])

# ADR-0064 (BuyerPolicy Fase 1): origem e boundary sao derivados, nao persistidos.
_ORIGIN_NAO_CLASSIFICADO = "NAO_CLASSIFICADO_COMO_BUYERPOLICY"


class CriarPolicyRequest(BaseModel):
    code: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=2000)
    valid_from: datetime | None = None
    valid_to: datetime | None = None


class PublicarPolicyRequest(BaseModel):
    published_at: datetime | None = None


class AvaliarPolicyRequest(BaseModel):
    """ADR-0064 (BuyerPolicy Fase 1): avalia somente Animal ja visivel a propria
    Organization -- nenhum sujeito de outra Organization e alcancado por esta
    rota."""

    animal_id: str = Field(min_length=1, max_length=100)
    purpose: str = Field(min_length=1, max_length=500)
    reference_time: datetime | None = None


class RuleResultResponse(BaseModel):
    rule_id: str
    rule_code: str
    rule_version: int
    status: str
    severity: str
    reason: str
    corrective_action: str
    missing_evidence_types: list[str]


class PolicyEvaluationResponse(BaseModel):
    evaluation_id: str
    policy_id: str
    policy_code: str
    policy_version: int
    animal_id: str
    purpose: str
    outcome: str
    engine_version: int
    evaluated_at: datetime
    snapshot_hash: str
    context_hash: str
    evaluation_hash: str
    rule_results: list[RuleResultResponse]
    origin: str
    recognition_boundary: str
    owner_organization_id: str
    requesting_organization_id: str


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


@router.post(
    "/{policy_id}/evaluate",
    response_model=PolicyEvaluationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Avaliar uma BuyerPolicy interna do comprador",
    description=(
        "ADR-0064 (BuyerPolicy Fase 1): executa a Policy sobre um Animal ja "
        "visivel a propria Organization e produz uma Evaluation isolada, nunca "
        "fundida com a matriz de elegibilidade regulatoria. So avalia Policies "
        "cujas Rules publicadas compartilhem RuleSourceType.INTERNAL_POLICY -- "
        "caso contrario a operacao inteira e recusada, sem resultado parcial."
    ),
    responses=RESPOSTAS_PADRAO,
)
def avaliar_policy(
    policy_id: str,
    corpo: AvaliarPolicyRequest,
    contexto: Annotated[OrganizationContext, Depends(require_permission(POLICY_AVALIAR))],
    connection: ConnectionDependency,
) -> PolicyEvaluationResponse:
    policy = _obter_ou_404(connection, contexto, policy_id)
    animal_id = typed_id_or_problem(corpo.animal_id, entity_type="animal", campo="animal_id")

    animal_repository = TransactionalAnimalRepository(connection=connection)
    if animal_repository.get_by_id(animal_id) is None:
        raise DomainProblem(
            status_code=status.HTTP_404_NOT_FOUND,
            reason_code="RECURSO_NAO_ENCONTRADO",
            title="Recurso nao encontrado",
            detail="Animal nao encontrado nesta organizacao.",
        )

    rules = TransactionalRuleRepository(connection=connection).list_by_policy(
        organization_id=contexto.organization_id, policy_id=policy.policy_id
    )
    origin = resolve_policy_origin(
        contexto.organization_id,
        rules,
        TransactionalRuleIdentityRepository(connection=connection),
    )
    if not is_buyer_policy_origin(origin):
        raise DomainProblem(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            reason_code="POLICY_NAO_RECONHECIDA_COMO_BUYERPOLICY",
            title="Policy nao reconhecida como BuyerPolicy",
            detail=(
                "Esta rota avalia somente Policies cujas Rules publicadas "
                "compartilhem RuleSourceType.INTERNAL_POLICY (ADR-0064). A "
                "Policy informada esta vazia, tem Rule sem RuleIdentity "
                "correspondente, ou mistura origens diferentes."
            ),
        )

    # Import local: evita acoplar o carregamento do modulo de Policy (Core) a
    # toda a superficie de `livestock_queries.py`; a composicao concreta do
    # FactProvider e responsabilidade da vertical (ADR-0064 Fase 1 restringe a
    # sujeitos e fact types Livestock ja existentes).
    from apps.api.livestock_queries import _eligibility_components

    _application_repository, _evaluations, _decisions, fact_provider = _eligibility_components(
        connection, animal_repository
    )
    reference_time = corpo.reference_time or datetime.now(UTC)
    snapshot = fact_provider.get_snapshot(contexto.organization_id, animal_id, reference_time)

    try:
        evaluation = PolicyEvaluationService(engine=RuleEvaluationEngine()).evaluate_policy(
            policy=policy,
            rules=rules,
            snapshot=snapshot,
            purpose=corpo.purpose,
        )
    except ValueError as error:
        raise DomainProblem(
            status_code=status.HTTP_409_CONFLICT,
            reason_code="CONFLITO_DE_DOMINIO",
            title="Operacao recusada pelo dominio",
            detail=str(error),
        ) from error

    TransactionalEvaluationRepository(connection=connection).save(evaluation)

    return PolicyEvaluationResponse(
        evaluation_id=str(evaluation.evaluation_id.value),
        policy_id=str(policy.policy_id.value),
        policy_code=policy.code,
        policy_version=policy.version,
        animal_id=str(animal_id.value),
        purpose=evaluation.purpose,
        outcome=evaluation.outcome.value,
        engine_version=evaluation.engine_version,
        evaluated_at=evaluation.evaluated_at,
        snapshot_hash=evaluation.fact_snapshot.snapshot_hash,
        context_hash=evaluation.context_hash,
        evaluation_hash=evaluation.evaluation_hash,
        rule_results=[
            RuleResultResponse(
                rule_id=str(resultado.rule_id.value),
                rule_code=resultado.rule_code,
                rule_version=resultado.rule_version,
                status=resultado.status.value,
                severity=resultado.severity.value,
                reason=resultado.reason,
                corrective_action=resultado.corrective_action,
                missing_evidence_types=list(resultado.missing_evidence_types),
            )
            for resultado in evaluation.rule_results
        ],
        origin=(origin.source_type.value if origin.source_type else _ORIGIN_NAO_CLASSIFICADO),
        recognition_boundary=RecognitionBoundary.INTERNAL_ONLY.value,
        owner_organization_id=str(policy.organization_id.value),
        requesting_organization_id=str(contexto.organization_id.value),
    )
