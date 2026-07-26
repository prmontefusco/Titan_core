"""HTTP minimo para governanca auditavel de regras (ADR-0043)."""

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy import Connection

from apps.api.livestock_dependencies import (
    ConnectionDependency,
    require_permission,
    typed_id_or_problem,
)
from apps.api.problem import RESPOSTAS_PADRAO, DomainProblem
from packages.core_application.rule_governance_authorization import (
    RULE_GOVERNANCE_CRIAR,
    RULE_GOVERNANCE_LER,
    RULE_GOVERNANCE_PUBLICAR,
)
from packages.core_application.rule_governance_service import RuleGovernanceService
from packages.core_domain import OrganizationContext
from packages.core_domain.rule import ComparisonOperator, Rule, RuleCondition, SeverityLevel
from packages.core_domain.rule_governance import (
    RuleIdentity,
    RuleSourceType,
    RuleTimelineEvent,
)
from packages.core_infrastructure.persistence.rule import TransactionalRuleRepository
from packages.core_infrastructure.persistence.rule_governance import (
    TransactionalRuleIdentityRepository,
    TransactionalRuleTimelineRepository,
)
from packages.shared_kernel import UniversalReference

router = APIRouter(prefix="/v1/rule-governance", tags=["rule-governance"])


class CriarIdentidadeRegraRequest(BaseModel):
    code: str = Field(min_length=1, max_length=120)
    purpose: str = Field(min_length=1, max_length=500)
    scope: str = Field(min_length=1, max_length=500)
    source_type: RuleSourceType
    vertical: str | None = Field(default=None, max_length=80)
    description: str = Field(default="", max_length=2000)


class RuleIdentityResponse(BaseModel):
    rule_identity_id: str
    organization_id: str
    code: str
    purpose: str
    scope: str
    source_type: str
    vertical: str | None
    description: str
    created_at: datetime


class RuleConditionRequest(BaseModel):
    fact_type: str = Field(min_length=1, max_length=120)
    payload_key: str = Field(min_length=1, max_length=120)
    operator: ComparisonOperator
    expected_value: Any = None
    description: str = Field(default="", max_length=1000)


class PublicarVersaoRegraRequest(BaseModel):
    policy_id: str
    name: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=2000)
    severity: SeverityLevel = SeverityLevel.BLOCKING
    normative_source: str = Field(default="", max_length=255)
    required_evidence_types: list[str] = Field(default_factory=list)
    conditions: list[RuleConditionRequest] = Field(default_factory=list)
    justification: str = Field(default="", max_length=2000)
    corrective_action: str = Field(default="", max_length=2000)
    valid_from: datetime | None = None
    valid_to: datetime | None = None


class RuleVersionResponse(BaseModel):
    rule_id: str
    policy_id: str
    organization_id: str
    code: str
    version: int
    name: str
    description: str
    severity: str
    normative_source: str
    required_evidence_types: list[str]
    conditions: list[dict[str, Any]]
    justification: str
    corrective_action: str
    valid_from: datetime | None
    valid_to: datetime | None
    created_at: datetime


class TimelineEventResponse(BaseModel):
    event_id: str
    rule_identity_id: str
    event_type: str
    actor_target_type: str
    actor_target_id: str
    actor_organization_id: str | None
    occurred_at: datetime
    rule_version_id: str | None
    reason: str


def _actor(contexto: OrganizationContext) -> UniversalReference:
    return UniversalReference(
        target_id=contexto.actor_id,
        organization_id=contexto.organization_id,
        contract_version=1,
    )


def _servico(connection: Connection) -> RuleGovernanceService:
    return RuleGovernanceService(
        identities=TransactionalRuleIdentityRepository(connection),
        timeline=TransactionalRuleTimelineRepository(connection),
        rules=TransactionalRuleRepository(connection),
    )


def _identity_response(identity: RuleIdentity) -> RuleIdentityResponse:
    return RuleIdentityResponse(
        rule_identity_id=str(identity.rule_identity_id.value),
        organization_id=str(identity.organization_id.value),
        code=identity.code,
        purpose=identity.purpose,
        scope=identity.scope,
        source_type=identity.source_type.value,
        vertical=identity.vertical,
        description=identity.description,
        created_at=identity.created_at,
    )


def _rule_response(rule: Rule) -> RuleVersionResponse:
    return RuleVersionResponse(
        rule_id=str(rule.rule_id.value),
        policy_id=str(rule.policy_id.value),
        organization_id=str(rule.organization_id.value),
        code=rule.code,
        version=rule.version,
        name=rule.name,
        description=rule.description,
        severity=rule.severity.value,
        normative_source=rule.normative_source,
        required_evidence_types=list(rule.required_evidence_types),
        conditions=[condition.to_dict() for condition in rule.conditions],
        justification=rule.justification,
        corrective_action=rule.corrective_action,
        valid_from=rule.valid_from,
        valid_to=rule.valid_to,
        created_at=rule.created_at,
    )


def _timeline_response(event: RuleTimelineEvent) -> TimelineEventResponse:
    return TimelineEventResponse(
        event_id=str(event.event_id.value),
        rule_identity_id=str(event.rule_identity_id.value),
        event_type=event.event_type.value,
        actor_target_type=event.actor.target_id.entity_type,
        actor_target_id=str(event.actor.target_id.value),
        actor_organization_id=(
            str(event.actor.organization_id.value) if event.actor.organization_id else None
        ),
        occurred_at=event.occurred_at,
        rule_version_id=str(event.rule_version_id.value) if event.rule_version_id else None,
        reason=event.reason,
    )


@router.post(
    "/rule-identities",
    response_model=RuleIdentityResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Criar uma identidade auditavel de regra",
    responses=RESPOSTAS_PADRAO,
)
def criar_identidade_regra(
    corpo: CriarIdentidadeRegraRequest,
    contexto: Annotated[OrganizationContext, Depends(require_permission(RULE_GOVERNANCE_CRIAR))],
    connection: ConnectionDependency,
) -> RuleIdentityResponse:
    try:
        identity = _servico(connection).create_identity(
            organization_id=contexto.organization_id,
            code=corpo.code,
            purpose=corpo.purpose,
            scope=corpo.scope,
            source_type=corpo.source_type,
            actor=_actor(contexto),
            vertical=corpo.vertical or "",
            description=corpo.description,
        )
    except ValueError as error:
        raise DomainProblem(
            status_code=status.HTTP_409_CONFLICT,
            reason_code="CONFLITO_DE_DOMINIO",
            title="Operacao recusada pelo dominio",
            detail=str(error),
        ) from error
    return _identity_response(identity)


@router.post(
    "/rule-identities/{rule_identity_id}/versions",
    response_model=RuleVersionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Publicar a primeira versao de uma regra governada",
    responses=RESPOSTAS_PADRAO,
)
def publicar_versao_regra(
    rule_identity_id: str,
    corpo: PublicarVersaoRegraRequest,
    contexto: Annotated[OrganizationContext, Depends(require_permission(RULE_GOVERNANCE_PUBLICAR))],
    connection: ConnectionDependency,
) -> RuleVersionResponse:
    identity_id = typed_id_or_problem(
        rule_identity_id, entity_type="rule_identity", campo="rule_identity_id"
    )
    policy_id = typed_id_or_problem(corpo.policy_id, entity_type="policy", campo="policy_id")
    try:
        rule = _servico(connection).publish_rule_version(
            organization_id=contexto.organization_id,
            rule_identity_id=identity_id,
            policy_id=policy_id,
            name=corpo.name,
            description=corpo.description,
            severity=corpo.severity,
            normative_source=corpo.normative_source,
            required_evidence_types=tuple(corpo.required_evidence_types),
            conditions=tuple(
                RuleCondition(
                    fact_type=condition.fact_type,
                    payload_key=condition.payload_key,
                    operator=condition.operator,
                    expected_value=condition.expected_value,
                    description=condition.description,
                )
                for condition in corpo.conditions
            ),
            justification=corpo.justification,
            corrective_action=corpo.corrective_action,
            valid_from=corpo.valid_from,
            valid_to=corpo.valid_to,
            actor=_actor(contexto),
        )
    except KeyError as error:
        raise DomainProblem(
            status_code=status.HTTP_404_NOT_FOUND,
            reason_code="RECURSO_NAO_ENCONTRADO",
            title="Recurso nao encontrado",
            detail=str(error),
        ) from error
    except ValueError as error:
        raise DomainProblem(
            status_code=status.HTTP_409_CONFLICT,
            reason_code="CONFLITO_DE_DOMINIO",
            title="Operacao recusada pelo dominio",
            detail=str(error),
        ) from error
    return _rule_response(rule)


@router.get(
    "/rule-identities/{rule_identity_id}/timeline",
    response_model=list[TimelineEventResponse],
    summary="Consultar a linha do tempo imutavel de uma regra",
    responses=RESPOSTAS_PADRAO,
)
def consultar_timeline_regra(
    rule_identity_id: str,
    contexto: Annotated[OrganizationContext, Depends(require_permission(RULE_GOVERNANCE_LER))],
    connection: ConnectionDependency,
) -> list[TimelineEventResponse]:
    identity_id = typed_id_or_problem(
        rule_identity_id, entity_type="rule_identity", campo="rule_identity_id"
    )
    identity = TransactionalRuleIdentityRepository(connection).get_by_id(identity_id)
    if identity is None or identity.organization_id != contexto.organization_id:
        raise DomainProblem(
            status_code=status.HTTP_404_NOT_FOUND,
            reason_code="RECURSO_NAO_ENCONTRADO",
            title="Recurso nao encontrado",
            detail="Identidade de regra nao encontrada nesta organizacao.",
        )
    events = TransactionalRuleTimelineRepository(connection).list_by_identity(
        contexto.organization_id, identity_id
    )
    return [_timeline_response(event) for event in events]
