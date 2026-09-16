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
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import Connection
from sqlalchemy.exc import IntegrityError

from apps.api.livestock_dependencies import (
    ConnectionDependency,
    require_permission,
    typed_id_or_problem,
)
from apps.api.pagination import Pagina, PaginacaoDependency, montar_pagina
from apps.api.problem import RESPOSTAS_PADRAO, DomainProblem, problem_response
from packages.core_application.evaluation_service import (
    PolicyEvaluationService,
    RuleEvaluationEngine,
)
from packages.core_application.policy_authorization import (
    POLICY_AVALIAR,
    POLICY_AVALIAR_COMPARTILHADA,
    POLICY_COMPARTILHAMENTO_COMPOR,
    POLICY_COMPARTILHAMENTO_LER,
    POLICY_COMPARTILHAMENTO_PROPOR,
    POLICY_COMPARTILHAMENTO_REVISAR,
    POLICY_COMPARTILHAR,
    POLICY_CRIAR,
    POLICY_LER,
    POLICY_PUBLICAR,
)
from packages.core_application.policy_origin import is_buyer_policy_origin, resolve_policy_origin
from packages.core_application.policy_service import PolicyService
from packages.core_application.policy_sharing_service import PolicySharingService
from packages.core_application.shared_decision_service import SharedDecisionService
from packages.core_domain import OrganizationContext
from packages.core_domain.evaluation import EvaluationOutcome
from packages.core_domain.policy import Policy
from packages.core_domain.policy_sharing import (
    SHARED_POLICY_ACCESS_ACTION_COMPOSE,
    SHARED_POLICY_ACCESS_ACTION_EVALUATE,
    SHARED_POLICY_ACCESS_ACTION_READ,
    SHARED_POLICY_ACCESS_ENTITY_TYPE,
    SharedDecision,
    SharedPolicyAccessLogEntry,
)
from packages.core_domain.rule_governance import RuleSourceType
from packages.core_infrastructure.persistence.authorization_grant import (
    TransactionalAuthorizationGrantRepository,
)
from packages.core_infrastructure.persistence.decision_governance import (
    TransactionalDecisionAuthorityProfileRepository,
    TransactionalDecisionGovernanceRepository,
)
from packages.core_infrastructure.persistence.evaluation import TransactionalEvaluationRepository
from packages.core_infrastructure.persistence.organizations import set_local_organization_context
from packages.core_infrastructure.persistence.policy import TransactionalPolicyRepository
from packages.core_infrastructure.persistence.rule import TransactionalRuleRepository
from packages.core_infrastructure.persistence.rule_governance import (
    TransactionalRuleAdoptionRepository,
    TransactionalRuleIdentityRepository,
)
from packages.core_infrastructure.persistence.shared_decision import (
    TransactionalSharedDecisionRepository,
)
from packages.core_infrastructure.persistence.shared_policy_access_log import (
    TransactionalSharedPolicyAccessLogRepository,
)
from packages.core_infrastructure.rate_limiter import (
    shared_policy_evaluation_key,
    shared_policy_evaluation_rate_limiter,
)
from packages.livestock_application.requirement_authority import RecognitionBoundary
from packages.livestock_infrastructure.persistence.animal_repository import (
    TransactionalAnimalRepository,
)
from packages.shared_kernel import OrganizationId, TypedId

router = APIRouter(prefix="/v1/rule-governance/policies", tags=["rule-governance"])

# ADR-0064 (BuyerPolicy Fase 1): origem e boundary sao derivados, nao persistidos.
_ORIGIN_NAO_CLASSIFICADO = "NAO_CLASSIFICADO_COMO_BUYERPOLICY"

# ADR-0065: a Fase 2 restringe a autoavaliacao compartilhada aos sujeitos que a
# vertical Livestock ja reconhece. Ampliar exige decisao propria.
_SUBJECT_TYPE_ANIMAL = "ANIMAL"


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


class CriarCompartilhamentoPolicyRequest(BaseModel):
    beneficiary_organization_id: str = Field(min_length=1)
    access_purpose: str = Field(min_length=1, max_length=100)
    valid_until: datetime
    field_scope_profile: str = Field(min_length=1, max_length=100)


class AuthorizationGrantResponse(BaseModel):
    grant_id: str
    policy_id: str
    owner_organization_id: str
    beneficiary_organization_id: str
    status: str
    valid_from: datetime
    valid_until: datetime
    access_purpose: str
    field_scope_profile: str


class RevogarCompartilhamentoPolicyRequest(BaseModel):
    revocation_reason: str | None = Field(default=None, max_length=1000)


class SharedPolicyResponse(BaseModel):
    policy_id: str
    code: str
    version: int
    origin: str
    rules: list[dict[str, object]]
    grant_id: str
    owner_organization_id: str


class AvaliarCompartilhadaPolicyRequest(BaseModel):
    subject_type: str = Field(min_length=1, max_length=100)
    subject_id: str = Field(min_length=1, max_length=100)
    purpose: str = Field(min_length=1, max_length=500)
    reference_time: datetime | None = None


class SharedPolicyEvaluationResponse(BaseModel):
    evaluation_id: str
    policy_id: str
    origin: str
    outcome: str
    rule_results: list[RuleResultResponse]
    missing_facts: list[str]
    evaluation_hash: str


class ComposeComMatrizRequest(BaseModel):
    grant_id: str = Field(min_length=1)
    evaluation_id: str = Field(min_length=1)
    market: str = Field(min_length=1, max_length=100)


class ComposeComMatrizResponse(BaseModel):
    grant_id: str
    evaluation_id: str
    market: str
    composite_verdict: str


class CriarSharedDecisionRequest(BaseModel):
    grant_id: str = Field(min_length=1)
    evaluation_id: str = Field(min_length=1)
    proposal_content: str = Field(min_length=1, max_length=4000)
    evidence_references: list[str] = Field(default_factory=list, max_length=50)


class RevisarSharedDecisionRequest(BaseModel):
    review_decision: str = Field(min_length=1, max_length=50)
    review_content: str = Field(min_length=1, max_length=4000)


class SharedDecisionResponse(BaseModel):
    decision_id: str
    grant_id: str
    evaluation_id: str
    policy_id: str
    proposer_organization_id: str
    reviewer_organization_id: str
    status: str
    proposal_content: str
    proposal_evidence_references: list[str]
    proposed_at: datetime
    created_by: str
    review_decision: str | None
    review_content: str | None
    reviewed_at: datetime | None
    reviewed_by: str | None


class AccessLogResponse(BaseModel):
    access_id: str
    grant_id: str
    policy_id: str
    organization_id: str
    action: str
    http_status_code: int
    accessed_at: datetime
    subject_type: str | None
    subject_id: str | None


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


def _shared_decision_service(connection: Connection) -> SharedDecisionService:
    return SharedDecisionService(
        grants=TransactionalAuthorizationGrantRepository(connection),
        evaluations=TransactionalEvaluationRepository(connection),
        decisions=TransactionalSharedDecisionRepository(connection),
        set_organization_context=lambda organization_id: set_local_organization_context(
            connection, organization_id
        ),
    )


def _shared_decision_response(decision: SharedDecision) -> SharedDecisionResponse:
    return SharedDecisionResponse(
        decision_id=str(decision.decision_id.value),
        grant_id=str(decision.grant_id),
        evaluation_id=str(decision.evaluation_id.value),
        policy_id=str(decision.policy_id.value),
        proposer_organization_id=str(decision.proposer_organization_id.value),
        reviewer_organization_id=str(decision.reviewer_organization_id.value),
        status=decision.status,
        proposal_content=decision.proposal_content,
        proposal_evidence_references=list(decision.proposal_evidence_references),
        proposed_at=decision.proposed_at,
        created_by=decision.created_by,
        review_decision=decision.review_decision,
        review_content=decision.review_content,
        reviewed_at=decision.reviewed_at,
        reviewed_by=decision.reviewed_by,
    )


def _registrar_acesso_compartilhado(
    connection: Connection,
    *,
    grant_id: UUID,
    policy_id: TypedId,
    organization_id: OrganizationId,
    owner_organization_id: OrganizationId,
    action: str,
    http_status_code: int,
    subject_type: str | None = None,
    subject_id: str | None = None,
) -> None:
    """Grava um acesso consumado a Policy compartilhada.

    A gravacao vive na mesma transacao da requisicao, entao ela acompanha o
    destino do que registrou: acesso que nao se completou nao deixa trilha de
    acesso concedido. Por isso a recusa por limite de taxa e devolvida como
    resposta -- e nao levantada como excecao: o 429 e justamente o evento que a
    trilha precisa preservar.
    """
    TransactionalSharedPolicyAccessLogRepository(connection).log_access(
        SharedPolicyAccessLogEntry(
            access_id=TypedId.new(SHARED_POLICY_ACCESS_ENTITY_TYPE),
            grant_id=grant_id,
            policy_id=policy_id,
            organization_id=organization_id,
            action=action,
            http_status_code=http_status_code,
            accessed_at=datetime.now(UTC),
            record_owner_organization_id=owner_organization_id,
            subject_type=subject_type,
            subject_id=subject_id,
        )
    )


def _resposta_access_log(entrada: SharedPolicyAccessLogEntry) -> AccessLogResponse:
    return AccessLogResponse(
        access_id=str(entrada.access_id.value),
        grant_id=str(entrada.grant_id),
        policy_id=str(entrada.policy_id.value),
        organization_id=str(entrada.organization_id.value),
        action=entrada.action,
        http_status_code=entrada.http_status_code,
        accessed_at=entrada.accessed_at,
        subject_type=entrada.subject_type,
        subject_id=entrada.subject_id,
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
    except IntegrityError as error:
        raise DomainProblem(
            status_code=status.HTTP_404_NOT_FOUND,
            reason_code="RECURSO_NAO_ENCONTRADO",
            title="Recurso nao encontrado",
            detail="Evaluation nao encontrada ou nao acessivel.",
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


@router.post(
    "/{policy_id}/shares",
    response_model=AuthorizationGrantResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Compartilhar uma BuyerPolicy contratual com outra Organization",
    description="ADR-0065: cria grant bilateral para compartilhamento de Policy contratual",
    responses=RESPOSTAS_PADRAO,
)
def compartilhar_policy(
    policy_id: str,
    corpo: CriarCompartilhamentoPolicyRequest,
    contexto: Annotated[OrganizationContext, Depends(require_permission(POLICY_COMPARTILHAR))],
    connection: ConnectionDependency,
) -> AuthorizationGrantResponse:
    from packages.shared_kernel import OrganizationId as OrgId

    policy = _obter_ou_404(connection, contexto, policy_id)
    beneficiary_org_id = OrgId(
        typed_id_or_problem(
            corpo.beneficiary_organization_id,
            entity_type="organization",
            campo="beneficiary_organization_id",
        ).value
    )

    service = PolicySharingService(
        policies=TransactionalPolicyRepository(connection),
        rules=TransactionalRuleRepository(connection),
        identities=TransactionalRuleIdentityRepository(connection),
        grants=TransactionalAuthorizationGrantRepository(connection),
    )

    try:
        grant = service.create_grant(
            owner_organization_id=contexto.organization_id,
            policy_id=policy.policy_id,
            beneficiary_organization_id=beneficiary_org_id,
            access_purpose=corpo.access_purpose,
            field_scope_profile=corpo.field_scope_profile,
            valid_until=corpo.valid_until,
            created_by=str(contexto.user_id.value),
        )
    except (KeyError, ValueError) as error:
        raise DomainProblem(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            reason_code="COMPARTILHAMENTO_RECUSADO",
            title="Compartilhamento recusado",
            detail=str(error),
        ) from error

    return AuthorizationGrantResponse(
        grant_id=str(grant.grant_id),
        policy_id=str(grant.policy_id.value),
        owner_organization_id=str(grant.owner_organization_id.value),
        beneficiary_organization_id=str(grant.beneficiary_organization_id.value),
        status=grant.status,
        valid_from=grant.valid_from,
        valid_until=grant.valid_until,
        access_purpose=grant.access_purpose,
        field_scope_profile=grant.field_scope_profile,
    )


@router.post(
    "/{policy_id}/shares/{grant_id}/revoke",
    response_model=AuthorizationGrantResponse,
    summary="Revogar um compartilhamento de BuyerPolicy",
    responses=RESPOSTAS_PADRAO,
)
def revogar_compartilhamento_policy(
    policy_id: str,
    grant_id: str,
    corpo: RevogarCompartilhamentoPolicyRequest,
    contexto: Annotated[OrganizationContext, Depends(require_permission(POLICY_COMPARTILHAR))],
    connection: ConnectionDependency,
) -> AuthorizationGrantResponse:
    _obter_ou_404(connection, contexto, policy_id)

    try:
        grant_uuid = UUID(grant_id)
    except ValueError as error:
        raise DomainProblem(
            status_code=status.HTTP_400_BAD_REQUEST,
            reason_code="FORMATO_INVALIDO",
            title="Formato invalido",
            detail="grant_id deve ser um UUID valido",
        ) from error

    service = PolicySharingService(
        policies=TransactionalPolicyRepository(connection),
        rules=TransactionalRuleRepository(connection),
        identities=TransactionalRuleIdentityRepository(connection),
        grants=TransactionalAuthorizationGrantRepository(connection),
    )

    try:
        service.revoke_grant(
            owner_organization_id=contexto.organization_id,
            grant_id=grant_uuid,
            revocation_reason=corpo.revocation_reason,
            revoked_by=str(contexto.user_id.value),
        )
    except (KeyError, ValueError) as error:
        raise DomainProblem(
            status_code=status.HTTP_409_CONFLICT,
            reason_code="CONFLITO_DE_DOMINIO",
            title="Operacao recusada pelo dominio",
            detail=str(error),
        ) from error

    grant = TransactionalAuthorizationGrantRepository(connection).get_by_id(grant_uuid)
    assert grant is not None

    return AuthorizationGrantResponse(
        grant_id=str(grant.grant_id),
        policy_id=str(grant.policy_id.value),
        owner_organization_id=str(grant.owner_organization_id.value),
        beneficiary_organization_id=str(grant.beneficiary_organization_id.value),
        status=grant.status,
        valid_from=grant.valid_from,
        valid_until=grant.valid_until,
        access_purpose=grant.access_purpose,
        field_scope_profile=grant.field_scope_profile,
    )


@router.get(
    "/shared-policies/{policy_id}",
    response_model=SharedPolicyResponse,
    summary="Consultar uma Policy compartilhada por outra Organization",
    description="ADR-0065: retorna Policy se o grant bilateral for valido",
    responses=RESPOSTAS_PADRAO,
)
def consultar_shared_policy(
    policy_id: str,
    contexto: Annotated[
        OrganizationContext, Depends(require_permission(POLICY_COMPARTILHAMENTO_LER))
    ],
    connection: ConnectionDependency,
) -> SharedPolicyResponse:
    policy_typed_id = typed_id_or_problem(policy_id, entity_type="policy", campo="policy_id")
    grant = TransactionalAuthorizationGrantRepository(
        connection
    ).get_active_by_policy_and_beneficiary(
        policy_id=policy_typed_id,
        beneficiary_organization_id=contexto.organization_id,
    )

    if grant is None:
        raise DomainProblem(
            status_code=status.HTTP_404_NOT_FOUND,
            reason_code="RECURSO_NAO_ENCONTRADO",
            title="Recurso nao encontrado",
            detail="Grant nao encontrado ou expirado",
        )

    set_local_organization_context(connection, grant.owner_organization_id)
    policy = TransactionalPolicyRepository(connection).get_by_id(policy_typed_id)
    if policy is None:
        raise DomainProblem(
            status_code=status.HTTP_404_NOT_FOUND,
            reason_code="RECURSO_NAO_ENCONTRADO",
            title="Recurso nao encontrado",
            detail="Policy nao encontrada",
        )

    if grant.valid_until < datetime.now(UTC):
        raise DomainProblem(
            status_code=status.HTTP_403_FORBIDDEN,
            reason_code="GRANT_EXPIRADO",
            title="Acesso recusado",
            detail="Grant expirou",
        )

    _registrar_acesso_compartilhado(
        connection,
        grant_id=grant.grant_id,
        policy_id=policy_typed_id,
        organization_id=contexto.organization_id,
        owner_organization_id=grant.owner_organization_id,
        action=SHARED_POLICY_ACCESS_ACTION_READ,
        http_status_code=status.HTTP_200_OK,
    )

    return SharedPolicyResponse(
        policy_id=str(policy.policy_id.value),
        code=policy.code,
        version=policy.version,
        origin="CONTRACT",
        rules=[],
        grant_id=str(grant.grant_id),
        owner_organization_id=str(policy.organization_id.value),
    )


@router.post(
    "/shared-policies/{policy_id}/evaluate",
    response_model=SharedPolicyEvaluationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Avaliar uma BuyerPolicy compartilhada (autoavaliacao contratual)",
    description="ADR-0065: fornecedor autoavalia Policy contratual compartilhada pelo comprador",
    responses={
        **RESPOSTAS_PADRAO,
        429: {"description": "Cota de avaliacoes por minuto do grant atingida"},
    },
)
def avaliar_shared_policy(
    policy_id: str,
    corpo: AvaliarCompartilhadaPolicyRequest,
    request: Request,
    contexto: Annotated[
        OrganizationContext, Depends(require_permission(POLICY_AVALIAR_COMPARTILHADA))
    ],
    connection: ConnectionDependency,
) -> SharedPolicyEvaluationResponse | JSONResponse:
    policy_typed_id = typed_id_or_problem(policy_id, entity_type="policy", campo="policy_id")
    grant = TransactionalAuthorizationGrantRepository(
        connection
    ).get_active_by_policy_and_beneficiary(
        policy_id=policy_typed_id,
        beneficiary_organization_id=contexto.organization_id,
    )

    if grant is None or grant.status != "ATIVO" or grant.valid_until < datetime.now(UTC):
        raise DomainProblem(
            status_code=status.HTTP_403_FORBIDDEN,
            reason_code="GRANT_INVALIDO",
            title="Acesso recusado",
            detail="Grant nao valido ou expirado",
        )

    # ADR-0066 secao 3: a cota e verificada antes de qualquer leitura da Policy.
    # Repetir a autoavaliacao e barato para quem consulta e caro para quem
    # compartilhou -- e uma sequencia rapida o bastante reconstroi, por
    # tentativa e erro, o criterio contratual que a Policy nao expoe.
    limite = shared_policy_evaluation_rate_limiter().check_rate_limit(
        shared_policy_evaluation_key(grant.grant_id)
    )
    if not limite.is_allowed:
        _registrar_acesso_compartilhado(
            connection,
            grant_id=grant.grant_id,
            policy_id=policy_typed_id,
            organization_id=contexto.organization_id,
            owner_organization_id=grant.owner_organization_id,
            action=SHARED_POLICY_ACCESS_ACTION_EVALUATE,
            http_status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            subject_type=corpo.subject_type,
            subject_id=corpo.subject_id,
        )
        recusa = problem_response(
            request=request,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            reason_code="LIMITE_DE_AVALIACOES_EXCEDIDO",
            title="Limite de avaliacoes atingido",
            detail=(
                f"Limite de {limite.limit} avaliacoes por minuto atingido para este "
                f"grant. Tente novamente em {limite.reset_after_seconds}s."
            ),
            extra={
                "limit_per_minute": limite.limit,
                "retry_after_seconds": limite.reset_after_seconds,
            },
        )
        recusa.headers["Retry-After"] = str(limite.reset_after_seconds)
        return recusa

    set_local_organization_context(connection, grant.owner_organization_id)
    policy = TransactionalPolicyRepository(connection).get_by_id(policy_typed_id)
    if policy is None:
        raise DomainProblem(
            status_code=status.HTTP_404_NOT_FOUND,
            reason_code="RECURSO_NAO_ENCONTRADO",
            title="Recurso nao encontrado",
            detail="Policy nao encontrada",
        )

    rules = TransactionalRuleRepository(connection).list_by_policy(
        organization_id=policy.organization_id,
        policy_id=policy_typed_id,
    )

    # Verifica que a Policy eh homogeneamente CONTRACT (ADR-0065)
    origin = resolve_policy_origin(
        policy.organization_id,
        rules,
        TransactionalRuleIdentityRepository(connection),
    )

    if not origin.homogeneous or origin.source_type != RuleSourceType.CONTRACT:
        raise DomainProblem(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            reason_code="POLICY_NAO_CONTRATUAL",
            title="Policy invalida para compartilhamento",
            detail="Apenas Policies contratuais homogeneas podem ser compartilhadas",
        )

    # ADR-0065/0068: daqui para a frente tudo corre sob a Organization
    # beneficiaria. A Policy e as Rules ja foram lidas sob a do owner acima; o
    # sujeito, os facts e a Evaluation resultante sao do fornecedor, e e isso que
    # impede o snapshot dele de atravessar para dentro da RLS do comprador.
    set_local_organization_context(connection, contexto.organization_id)

    if corpo.subject_type.strip().upper() != _SUBJECT_TYPE_ANIMAL:
        raise DomainProblem(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            reason_code="SUJEITO_NAO_SUPORTADO",
            title="Sujeito nao suportado",
            detail=(
                f"A autoavaliacao contratual compartilhada avalia somente "
                f"{_SUBJECT_TYPE_ANIMAL} (ADR-0065)."
            ),
        )

    animal_id = typed_id_or_problem(corpo.subject_id, entity_type="animal", campo="subject_id")
    animal_repository = TransactionalAnimalRepository(connection=connection)
    if animal_repository.get_by_id(animal_id) is None:
        # A resposta nao distingue sujeito inexistente de sujeito de outra
        # Organization: quem avalia so pode avaliar o que ja lhe pertence (D5).
        raise DomainProblem(
            status_code=status.HTTP_404_NOT_FOUND,
            reason_code="RECURSO_NAO_ENCONTRADO",
            title="Recurso nao encontrado",
            detail="Sujeito nao encontrado nesta organizacao.",
        )

    # Import local pelo mesmo motivo de `avaliar_policy`: nao acoplar o modulo de
    # Policy do Core a toda a superficie de `livestock_queries.py`.
    from apps.api.livestock_queries import _eligibility_components

    _aplicacoes, _avaliacoes, _decisoes, fact_provider = _eligibility_components(
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
            evaluating_organization_id=contexto.organization_id,
        )
    except ValueError as error:
        raise DomainProblem(
            status_code=status.HTTP_409_CONFLICT,
            reason_code="CONFLITO_DE_DOMINIO",
            title="Operacao recusada pelo dominio",
            detail=str(error),
        ) from error

    TransactionalEvaluationRepository(connection=connection).save(evaluation)

    _registrar_acesso_compartilhado(
        connection,
        grant_id=grant.grant_id,
        policy_id=policy_typed_id,
        organization_id=contexto.organization_id,
        owner_organization_id=grant.owner_organization_id,
        action=SHARED_POLICY_ACCESS_ACTION_EVALUATE,
        http_status_code=status.HTTP_201_CREATED,
        subject_type=corpo.subject_type,
        subject_id=corpo.subject_id,
    )

    return SharedPolicyEvaluationResponse(
        evaluation_id=str(evaluation.evaluation_id.value),
        policy_id=str(policy.policy_id.value),
        origin="CONTRACT",
        outcome=evaluation.outcome.value,
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
        missing_facts=sorted(
            {
                tipo
                for resultado in evaluation.rule_results
                for tipo in resultado.missing_evidence_types
            }
        ),
        evaluation_hash=evaluation.evaluation_hash,
    )


_COMPOSITE_ELEGIVEL = "ELEGIVEL"
_COMPOSITE_INELEGIVEL = "INELEGIVEL"
_COMPOSITE_REQUER_REVISAO = "REQUER_REVISAO"


@router.post(
    "/shared-policies/{policy_id}/compose-with-matrix",
    response_model=ComposeComMatrizResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Compor avaliacao contratual compartilhada com a matriz de elegibilidade regulatoria",
    description=(
        "ADR-0066 Incremento 3 (Fluxo B): somente o comprador (owner do grant) compoe. O "
        "fornecedor nunca ve o efeito da matriz do comprador -- a resposta contem apenas o "
        "veredito composto, sem rule_results de nenhum dos dois lados."
    ),
    responses={
        **RESPOSTAS_PADRAO,
        429: {"description": "Cota de avaliacoes por minuto do grant atingida"},
    },
)
def compor_shared_policy_com_matriz(
    policy_id: str,
    corpo: ComposeComMatrizRequest,
    request: Request,
    contexto: Annotated[
        OrganizationContext, Depends(require_permission(POLICY_COMPARTILHAMENTO_COMPOR))
    ],
    connection: ConnectionDependency,
) -> ComposeComMatrizResponse | JSONResponse:
    policy_typed_id = typed_id_or_problem(policy_id, entity_type="policy", campo="policy_id")
    evaluation_typed_id = typed_id_or_problem(
        corpo.evaluation_id, entity_type="evaluation", campo="evaluation_id"
    )
    try:
        grant_id = UUID(corpo.grant_id)
    except ValueError as error:
        raise DomainProblem(
            status_code=status.HTTP_400_BAD_REQUEST,
            reason_code="FORMATO_INVALIDO",
            title="Formato invalido",
            detail="grant_id deve ser um UUID valido",
        ) from error

    # Import local pelo mesmo motivo de `avaliar_shared_policy`: nao acoplar o
    # modulo de Policy do Core a toda a superficie de mercado da vertical.
    from packages.livestock_application.market_eligibility import (
        DEFAULT_MARKET_PROFILES,
        MarketEligibilityPurpose,
        MarketEligibilityService,
        MarketEligibilityStatus,
    )

    try:
        mercado = MarketEligibilityPurpose(corpo.market)
    except ValueError as error:
        raise DomainProblem(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            reason_code="PARAMETRO_INVALIDO",
            title="Mercado invalido",
            detail=f"'{corpo.market}' nao e um mercado reconhecido.",
        ) from error
    perfil = next((item for item in DEFAULT_MARKET_PROFILES if item.market is mercado), None)
    if perfil is None:
        raise DomainProblem(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            reason_code="PARAMETRO_INVALIDO",
            title="Mercado invalido",
            detail=f"Nao ha perfil de elegibilidade configurado para '{corpo.market}'.",
        )

    # Comprador -- nao beneficiario: `compose-with-matrix` e o unico passo da
    # Fase 3 iniciado pelo owner do grant, nao pelo fornecedor (D1/D4).
    grant = TransactionalAuthorizationGrantRepository(connection).get_by_id(grant_id)
    if (
        grant is None
        or grant.policy_id != policy_typed_id
        or grant.owner_organization_id != contexto.organization_id
        or grant.status != "ATIVO"
        or grant.valid_until < datetime.now(UTC)
    ):
        raise DomainProblem(
            status_code=status.HTTP_403_FORBIDDEN,
            reason_code="GRANT_INVALIDO",
            title="Acesso recusado",
            detail="Grant nao valido, nao pertence a esta Organization ou expirado",
        )

    # ADR-0066 secao 3 / D3: compose usa a mesma cota e a mesma chave de
    # `/evaluate` -- e mais uma forma de sondar o fornecedor sob o mesmo
    # grant, nao merece orcamento proprio.
    limite = shared_policy_evaluation_rate_limiter().check_rate_limit(
        shared_policy_evaluation_key(grant.grant_id)
    )
    if not limite.is_allowed:
        _registrar_acesso_compartilhado(
            connection,
            grant_id=grant.grant_id,
            policy_id=policy_typed_id,
            organization_id=contexto.organization_id,
            owner_organization_id=grant.owner_organization_id,
            action=SHARED_POLICY_ACCESS_ACTION_COMPOSE,
            http_status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )
        recusa = problem_response(
            request=request,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            reason_code="LIMITE_DE_AVALIACOES_EXCEDIDO",
            title="Limite de avaliacoes atingido",
            detail=(
                f"Limite de {limite.limit} avaliacoes por minuto atingido para este "
                f"grant. Tente novamente em {limite.reset_after_seconds}s."
            ),
            extra={
                "limit_per_minute": limite.limit,
                "retry_after_seconds": limite.reset_after_seconds,
            },
        )
        recusa.headers["Retry-After"] = str(limite.reset_after_seconds)
        return recusa

    # Daqui para a frente corre sob a Organization do fornecedor -- a mesma
    # troca de contexto de `avaliar_shared_policy` (ADR-0068): a Evaluation
    # contratual e os facts do sujeito sao dele, nunca da RLS do comprador.
    set_local_organization_context(connection, grant.beneficiary_organization_id)
    evaluation = TransactionalEvaluationRepository(connection).get_by_id(evaluation_typed_id)
    if (
        evaluation is None
        or evaluation.policy_id != policy_typed_id
        or evaluation.organization_id != grant.beneficiary_organization_id
    ):
        raise DomainProblem(
            status_code=status.HTTP_404_NOT_FOUND,
            reason_code="RECURSO_NAO_ENCONTRADO",
            title="Recurso nao encontrado",
            detail="Evaluation nao encontrada ou nao acessivel.",
        )

    # Import local pelo mesmo motivo de `avaliar_shared_policy`.
    from apps.api.livestock_queries import _eligibility_components
    from packages.livestock_application.eligibility import HumanReviewRequired

    animal_repository = TransactionalAnimalRepository(connection=connection)
    _aplicacoes, evaluations, decisions, fact_provider = _eligibility_components(
        connection, animal_repository
    )

    matriz_status: MarketEligibilityStatus | None
    try:
        matrix = MarketEligibilityService(
            adoption_reader=TransactionalRuleAdoptionRepository(connection),
            rule_reader=TransactionalRuleRepository(connection=connection),
            policy_reader=TransactionalPolicyRepository(connection=connection),
            fact_provider=fact_provider,
            evaluation_repository=evaluations,
            decision_repository=decisions,
            authority_profile_repository=TransactionalDecisionAuthorityProfileRepository(
                connection
            ),
            governance_repository=TransactionalDecisionGovernanceRepository(connection),
            profiles=(perfil,),
        ).evaluate(
            organization_id=grant.beneficiary_organization_id,
            subject_id=evaluation.subject_id,
            at_time=datetime.now(UTC),
        )
    except HumanReviewRequired:
        # A propria semantica de "precisa de revisao humana" ja e o que
        # REQUER_REVISAO representa para o comprador -- sem propagar o 409
        # bruto nem qualquer detalhe da avaliacao que a produziu.
        matriz_status = None
    except Exception as debug_temp_exc:  # TEMP DEBUG -- remove before merge
        import traceback

        raise DomainProblem(
            status_code=500,
            reason_code="DEBUG_TEMP",
            title="debug",
            detail=(f"{type(debug_temp_exc).__name__}: {debug_temp_exc}\n{traceback.format_exc()}"),
        ) from debug_temp_exc
    else:
        matriz_status = matrix.entries[0].status

    if (
        evaluation.outcome is EvaluationOutcome.CONDICOES_NAO_SATISFEITAS
        or matriz_status is MarketEligibilityStatus.NAO_ELEGIVEL
    ):
        veredito = _COMPOSITE_INELEGIVEL
    elif (
        evaluation.outcome is EvaluationOutcome.CONDICOES_SATISFEITAS
        and matriz_status is MarketEligibilityStatus.ELEGIVEL
    ):
        veredito = _COMPOSITE_ELEGIVEL
    else:
        veredito = _COMPOSITE_REQUER_REVISAO

    _registrar_acesso_compartilhado(
        connection,
        grant_id=grant.grant_id,
        policy_id=policy_typed_id,
        organization_id=contexto.organization_id,
        owner_organization_id=grant.owner_organization_id,
        action=SHARED_POLICY_ACCESS_ACTION_COMPOSE,
        http_status_code=status.HTTP_201_CREATED,
        subject_type=_SUBJECT_TYPE_ANIMAL,
        subject_id=str(evaluation.subject_id.value),
    )

    return ComposeComMatrizResponse(
        grant_id=str(grant.grant_id),
        evaluation_id=str(evaluation.evaluation_id.value),
        market=corpo.market,
        composite_verdict=veredito,
    )


@router.post(
    "/shared-policies/{policy_id}/decisions",
    response_model=SharedDecisionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Criar proposta sobre uma Evaluation compartilhada",
    description=(
        "BuyerPolicy Fase 3 Incremento 1: fornecedor beneficiario propoe revisao estruturada."
    ),
    responses=RESPOSTAS_PADRAO,
)
def criar_shared_decision(
    policy_id: str,
    corpo: CriarSharedDecisionRequest,
    contexto: Annotated[
        OrganizationContext, Depends(require_permission(POLICY_COMPARTILHAMENTO_PROPOR))
    ],
    connection: ConnectionDependency,
) -> SharedDecisionResponse:
    policy_typed_id = typed_id_or_problem(policy_id, entity_type="policy", campo="policy_id")
    evaluation_id = typed_id_or_problem(
        corpo.evaluation_id, entity_type="evaluation", campo="evaluation_id"
    )
    try:
        grant_id = UUID(corpo.grant_id)
    except ValueError as error:
        raise DomainProblem(
            status_code=status.HTTP_400_BAD_REQUEST,
            reason_code="FORMATO_INVALIDO",
            title="Formato invalido",
            detail="grant_id deve ser um UUID valido",
        ) from error

    try:
        decision = _shared_decision_service(connection).create_proposal(
            policy_id=policy_typed_id,
            grant_id=grant_id,
            evaluation_id=evaluation_id,
            proposal_content=corpo.proposal_content,
            evidence_references=tuple(corpo.evidence_references),
            proposer_organization_id=contexto.organization_id,
            created_by=str(contexto.user_id.value),
        )
    except KeyError as error:
        raise DomainProblem(
            status_code=status.HTTP_404_NOT_FOUND,
            reason_code="RECURSO_NAO_ENCONTRADO",
            title="Recurso nao encontrado",
            detail="Recurso nao encontrado ou nao acessivel.",
        ) from error
    except PermissionError as error:
        raise DomainProblem(
            status_code=status.HTTP_403_FORBIDDEN,
            reason_code="PERMISSAO_AUSENTE",
            title="Acesso recusado",
            detail=str(error),
        ) from error
    except ValueError as error:
        raise DomainProblem(
            status_code=status.HTTP_409_CONFLICT,
            reason_code="CONFLITO_DE_DOMINIO",
            title="Operacao recusada pelo dominio",
            detail=str(error),
        ) from error

    return _shared_decision_response(decision)


@router.post(
    "/shared-policies/{policy_id}/decisions/{decision_id}/review",
    response_model=SharedDecisionResponse,
    summary="Revisar proposta sobre uma Evaluation compartilhada",
    description="BuyerPolicy Fase 3 Incremento 1: comprador owner revisa proposta do fornecedor.",
    responses=RESPOSTAS_PADRAO,
)
def revisar_shared_decision(
    policy_id: str,
    decision_id: str,
    corpo: RevisarSharedDecisionRequest,
    contexto: Annotated[
        OrganizationContext, Depends(require_permission(POLICY_COMPARTILHAMENTO_REVISAR))
    ],
    connection: ConnectionDependency,
) -> SharedDecisionResponse:
    policy_typed_id = typed_id_or_problem(policy_id, entity_type="policy", campo="policy_id")
    decision_typed_id = typed_id_or_problem(
        decision_id, entity_type="shared_decision", campo="decision_id"
    )

    try:
        decision = _shared_decision_service(connection).review_proposal(
            decision_id=decision_typed_id,
            policy_id=policy_typed_id,
            review_decision=corpo.review_decision,
            review_content=corpo.review_content,
            reviewer_organization_id=contexto.organization_id,
            reviewed_by=str(contexto.user_id.value),
        )
    except KeyError as error:
        raise DomainProblem(
            status_code=status.HTTP_404_NOT_FOUND,
            reason_code="RECURSO_NAO_ENCONTRADO",
            title="Recurso nao encontrado",
            detail="SharedDecision nao encontrada ou nao acessivel.",
        ) from error
    except PermissionError as error:
        raise DomainProblem(
            status_code=status.HTTP_403_FORBIDDEN,
            reason_code="PERMISSAO_AUSENTE",
            title="Acesso recusado",
            detail=str(error),
        ) from error
    except ValueError as error:
        raise DomainProblem(
            status_code=status.HTTP_409_CONFLICT,
            reason_code="CONFLITO_DE_DOMINIO",
            title="Operacao recusada pelo dominio",
            detail=str(error),
        ) from error

    return _shared_decision_response(decision)


@router.get(
    "/shared-policies/{policy_id}/decisions",
    response_model=list[SharedDecisionResponse],
    summary="Listar propostas e revisoes de uma Policy compartilhada",
    responses=RESPOSTAS_PADRAO,
)
def listar_shared_decisions(
    policy_id: str,
    contexto: Annotated[
        OrganizationContext, Depends(require_permission(POLICY_COMPARTILHAMENTO_LER))
    ],
    connection: ConnectionDependency,
) -> list[SharedDecisionResponse]:
    policy_typed_id = typed_id_or_problem(policy_id, entity_type="policy", campo="policy_id")
    decisions = _shared_decision_service(connection).list_for_policy(
        policy_id=policy_typed_id,
        organization_id=contexto.organization_id,
    )
    return [_shared_decision_response(decision) for decision in decisions]


@router.get(
    "/{policy_id}/access-log",
    response_model=Pagina[AccessLogResponse],
    summary="Listar acessos a uma Policy compartilhada",
    description=(
        "BuyerPolicy Fase 3 Incremento 2: a Organization dona da Policy le a trilha "
        "de leituras e avaliacoes feitas sob os grants que ela concedeu."
    ),
    responses=RESPOSTAS_PADRAO,
)
def listar_access_log(
    policy_id: str,
    contexto: Annotated[
        OrganizationContext, Depends(require_permission(POLICY_COMPARTILHAMENTO_LER))
    ],
    connection: ConnectionDependency,
    paginacao: PaginacaoDependency,
    http_status_code: Annotated[int | None, Query(ge=100, le=599)] = None,
) -> dict[str, object]:
    # A trilha e do lado que compartilhou: quem recebeu o acesso ja sabe o que
    # pediu, e devolver a ela a serie completa de acessos entregaria o ritmo de
    # consulta das demais beneficiarias do mesmo contrato. `_obter_ou_404`
    # responde 404 -- e nao 403 -- a quem nao e dono, mantendo a resposta
    # indistinguivel de Policy inexistente.
    policy = _obter_ou_404(connection, contexto, policy_id)

    entradas = TransactionalSharedPolicyAccessLogRepository(connection).list_by_policy(
        policy.policy_id,
        http_status_code=http_status_code,
        limit=paginacao.limite_de_sondagem,
        offset=paginacao.offset,
    )
    return montar_pagina([_resposta_access_log(entrada) for entrada in entradas], paginacao)
