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
from apps.api.pagination import Pagina, PaginacaoDependency, montar_pagina
from apps.api.problem import RESPOSTAS_PADRAO, DomainProblem
from packages.core_application.rule_governance_authorization import (
    RULE_GOVERNANCE_ADOTAR,
    RULE_GOVERNANCE_CRIAR,
    RULE_GOVERNANCE_LER,
    RULE_GOVERNANCE_PUBLICAR,
)
from packages.core_application.rule_governance_service import RuleGovernanceService
from packages.core_domain import OrganizationContext
from packages.core_domain.rule import ComparisonOperator, Rule, RuleCondition, SeverityLevel
from packages.core_domain.rule_governance import (
    RuleAdoption,
    RuleIdentity,
    RuleSourceType,
    RuleTimelineEvent,
)
from packages.core_infrastructure.persistence.rule import TransactionalRuleRepository
from packages.core_infrastructure.persistence.rule_governance import (
    TransactionalRuleAdoptionRepository,
    TransactionalRuleIdentityRepository,
    TransactionalRuleTimelineRepository,
)
from packages.livestock_application.establishment_qualification_service import (
    establishment_qualification_fact_type,
)
from packages.livestock_application.fact_provider import (
    ENVIRONMENTAL_EMBARGO_IBAMA_FACT_TYPE,
    WITHDRAWAL_FACT_TYPE,
    sanitary_requirement_fact_type,
)
from packages.livestock_application.market_eligibility import (
    ELIGIBILITY_RULE_CODE,
    ENVIRONMENTAL_EMBARGO_RULE_CODE,
    ESTABLISHMENT_RULE_CODE,
    SANITARY_RULE_CODE,
    TRACEABILITY_RULE_CODE,
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


class AdotarRegraRequest(BaseModel):
    rule_version_id: str
    purpose: str = Field(min_length=1, max_length=120)
    scope: str = Field(min_length=1, max_length=160)
    reason: str = Field(default="", max_length=2000)


class RuleAdoptionResponse(BaseModel):
    adoption_id: str
    organization_id: str
    rule_identity_id: str
    rule_version_id: str
    purpose: str
    scope: str
    adopted_at: datetime
    reason: str
    status: str


class SubstituirAdocaoRegraRequest(BaseModel):
    current_adoption_id: str
    new_rule_version_id: str
    reason: str = Field(min_length=1, max_length=2000)


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


class RuleTemplateConditionResponse(BaseModel):
    fact_type: str
    payload_key: str
    operator: str
    expected_value: Any = None
    description: str


class RuleTemplateParameterResponse(BaseModel):
    name: str
    description: str
    example: str


class RuleFactTypeCatalogResponse(BaseModel):
    fact_type: str
    description: str
    payload_keys: list[str]
    parameterized: bool = False
    example_fact_type: str | None = None


class RuleTemplateCatalogResponse(BaseModel):
    template_code: str
    rule_code: str
    name: str
    purpose_hint: str
    scope_hint: str
    normative_source_hint: str
    required_evidence_types: list[str]
    conditions: list[RuleTemplateConditionResponse]
    justification_hint: str
    corrective_action_hint: str
    parameters: list[RuleTemplateParameterResponse] = Field(default_factory=list)


class LivestockMarketRuleCatalogResponse(BaseModel):
    catalog_version: int
    vertical: str
    fact_types: list[RuleFactTypeCatalogResponse]
    templates: list[RuleTemplateCatalogResponse]


class MaterializarTemplateRegraRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=2000)
    normative_source: str = Field(default="", max_length=255)
    parameters: dict[str, str] = Field(default_factory=dict)


class MaterializedRuleDraftResponse(BaseModel):
    template_code: str
    rule_code: str
    name: str
    description: str
    severity: str
    normative_source: str
    required_evidence_types: list[str]
    conditions: list[RuleTemplateConditionResponse]
    justification: str
    corrective_action: str


class SugerirFluxoGovernancaRegraRequest(BaseModel):
    market_purpose: str = Field(min_length=1, max_length=120)
    adoption_scope: str = Field(min_length=1, max_length=160)
    name: str = Field(min_length=1, max_length=255)
    normative_source: str = Field(default="", max_length=255)
    identity_code: str | None = Field(default=None, max_length=120)
    identity_purpose: str | None = Field(default=None, max_length=500)
    identity_scope: str | None = Field(default=None, max_length=500)
    identity_description: str = Field(default="", max_length=2000)
    version_description: str = Field(default="", max_length=2000)
    adoption_reason: str = Field(default="", max_length=2000)
    parameters: dict[str, str] = Field(default_factory=dict)


class SuggestedRuleIdentityDraftResponse(BaseModel):
    code: str
    purpose: str
    scope: str
    source_type: str
    vertical: str
    description: str


class SuggestedRuleAdoptionDraftResponse(BaseModel):
    purpose: str
    scope: str
    reason: str


class SuggestedGovernanceFlowResponse(BaseModel):
    template_code: str
    identity: SuggestedRuleIdentityDraftResponse
    version: MaterializedRuleDraftResponse
    adoption: SuggestedRuleAdoptionDraftResponse


class ExecutarFluxoGovernancaRegraRequest(BaseModel):
    policy_id: str
    market_purpose: str = Field(min_length=1, max_length=120)
    adoption_scope: str = Field(min_length=1, max_length=160)
    name: str = Field(min_length=1, max_length=255)
    normative_source: str = Field(default="", max_length=255)
    identity_code: str | None = Field(default=None, max_length=120)
    identity_purpose: str | None = Field(default=None, max_length=500)
    identity_scope: str | None = Field(default=None, max_length=500)
    identity_description: str = Field(default="", max_length=2000)
    version_description: str = Field(default="", max_length=2000)
    adoption_reason: str = Field(default="", max_length=2000)
    create_adoption: bool = True
    parameters: dict[str, str] = Field(default_factory=dict)


class ExecutedGovernanceFlowResponse(BaseModel):
    template_code: str
    identity: RuleIdentityResponse
    version: RuleVersionResponse
    adoption: RuleAdoptionResponse | None


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
        adoptions=TransactionalRuleAdoptionRepository(connection),
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


def _adoption_response(adoption: RuleAdoption) -> RuleAdoptionResponse:
    return RuleAdoptionResponse(
        adoption_id=str(adoption.adoption_id.value),
        organization_id=str(adoption.organization_id.value),
        rule_identity_id=str(adoption.rule_identity_id.value),
        rule_version_id=str(adoption.rule_version_id.value),
        purpose=adoption.purpose,
        scope=adoption.scope,
        adopted_at=adoption.adopted_at,
        reason=adoption.reason,
        status=adoption.status.value,
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


def _catalogo_regras_mercado_livestock() -> LivestockMarketRuleCatalogResponse:
    return LivestockMarketRuleCatalogResponse(
        catalog_version=1,
        vertical="livestock",
        fact_types=[
            RuleFactTypeCatalogResponse(
                fact_type=WITHDRAWAL_FACT_TYPE,
                description="Fato consolidado de carencia farmacologica do animal.",
                payload_keys=[
                    "in_withdrawal",
                    "eligible_from",
                    "rule_version",
                    "blocking_batches",
                    "contributions",
                ],
            ),
            RuleFactTypeCatalogResponse(
                fact_type=ENVIRONMENTAL_EMBARGO_IBAMA_FACT_TYPE,
                description="Ultima assercao conhecida de embargo ambiental IBAMA da propriedade.",
                payload_keys=[
                    "status",
                    "property_id",
                    "geometry_id",
                    "geometry_version",
                    "source_name",
                    "source_layer",
                    "operation",
                    "restriction_count",
                    "version_ids",
                    "response_digest",
                ],
            ),
            RuleFactTypeCatalogResponse(
                fact_type=establishment_qualification_fact_type("exportacao-china"),
                description="Qualificacao de estabelecimento por mercado de destino.",
                payload_keys=[
                    "qualification_status",
                    "asserted_status",
                    "source_artifact_id",
                    "confidence_tier",
                ],
                parameterized=True,
                example_fact_type=establishment_qualification_fact_type("exportacao-china"),
            ),
            RuleFactTypeCatalogResponse(
                fact_type=sanitary_requirement_fact_type("brucelose"),
                description="Status de atendimento de uma campanha sanitaria especifica.",
                payload_keys=[
                    "status",
                    "campaign_id",
                    "application_id",
                ],
                parameterized=True,
                example_fact_type=sanitary_requirement_fact_type("brucelose"),
            ),
        ],
        templates=[
            RuleTemplateCatalogResponse(
                template_code="pharmacological-withdrawal-v1",
                rule_code=ELIGIBILITY_RULE_CODE,
                name="Carencia farmacologica do animal",
                purpose_hint=("Usar quando o mercado exige animal fora da carencia medicamentosa."),
                scope_hint="livestock.animal",
                normative_source_hint=(
                    "Lei nacional, protocolo do frigorifico ou exigencia do mercado."
                ),
                required_evidence_types=["livestock.treatment_applied"],
                conditions=[
                    RuleTemplateConditionResponse(
                        fact_type=WITHDRAWAL_FACT_TYPE,
                        payload_key="in_withdrawal",
                        operator=ComparisonOperator.EQUALS.value,
                        expected_value=False,
                        description=(
                            "O animal precisa estar fora da carencia no momento da avaliacao."
                        ),
                    )
                ],
                justification_hint="Mercado exige ausencia de carencia farmacologica ativa.",
                corrective_action_hint="Aguardar o fim da carencia antes da comercializacao.",
            ),
            RuleTemplateCatalogResponse(
                template_code="minimum-traceability-v1",
                rule_code=TRACEABILITY_RULE_CODE,
                name="Rastreabilidade minima por propriedade de origem",
                purpose_hint=(
                    "Usar quando o mercado exige vinculo minimo com propriedade e historico "
                    "auditavel."
                ),
                scope_hint="livestock.animal",
                normative_source_hint=(
                    "Exigencia contratual ou protocolo de rastreabilidade do mercado."
                ),
                required_evidence_types=["livestock.animal", "livestock.rural_property"],
                conditions=[
                    RuleTemplateConditionResponse(
                        fact_type="livestock.animal",
                        payload_key="birth_property_id",
                        operator=ComparisonOperator.NOT_EQUALS.value,
                        expected_value=None,
                        description="O animal precisa ter propriedade de nascimento conhecida.",
                    )
                ],
                justification_hint="Sem origem minima conhecida, a cadeia nao sustenta auditoria.",
                corrective_action_hint="Completar a origem auditavel do animal antes da venda.",
            ),
            RuleTemplateCatalogResponse(
                template_code="environmental-embargo-ibama-v1",
                rule_code=ENVIRONMENTAL_EMBARGO_RULE_CODE,
                name="Embargo ambiental IBAMA",
                purpose_hint=(
                    "Usar quando o mercado recusa animais vinculados a propriedade com "
                    "restricao ambiental."
                ),
                scope_hint="livestock.animal",
                normative_source_hint=(
                    "EUDR, regra do frigorifico ou protocolo ambiental do mercado."
                ),
                required_evidence_types=["livestock.property_geometry", "ibama.embargo_layer"],
                conditions=[
                    RuleTemplateConditionResponse(
                        fact_type=ENVIRONMENTAL_EMBARGO_IBAMA_FACT_TYPE,
                        payload_key="status",
                        operator=ComparisonOperator.EQUALS.value,
                        expected_value="SEM_RESTRICAO",
                        description=(
                            "A propriedade relevante do animal precisa estar sem restricao "
                            "conhecida."
                        ),
                    )
                ],
                justification_hint=(
                    "Restricao ambiental conhecida impede a elegibilidade deste mercado."
                ),
                corrective_action_hint=(
                    "Resolver a restricao ou redirecionar para mercado compativel."
                ),
            ),
            RuleTemplateCatalogResponse(
                template_code="slaughterhouse-qualification-v1",
                rule_code=ESTABLISHMENT_RULE_CODE,
                name="Habilitacao do estabelecimento por mercado",
                purpose_hint=(
                    "Usar quando o mercado depende da habilitacao do frigorifico escolhido."
                ),
                scope_hint="livestock.slaughterhouse",
                normative_source_hint=(
                    "Lista oficial do pais de destino ou protocolo do estabelecimento."
                ),
                required_evidence_types=["livestock.establishment_qualification.<mercado>"],
                conditions=[
                    RuleTemplateConditionResponse(
                        fact_type=establishment_qualification_fact_type("{{market_purpose}}"),
                        payload_key="qualification_status",
                        operator=ComparisonOperator.EQUALS.value,
                        expected_value="HABILITADO",
                        description=(
                            "O estabelecimento precisa estar habilitado para o mercado escolhido."
                        ),
                    )
                ],
                justification_hint=(
                    "Sem habilitacao do estabelecimento, o animal nao pode seguir para este "
                    "destino."
                ),
                corrective_action_hint=(
                    "Escolher estabelecimento habilitado ou aguardar habilitacao."
                ),
                parameters=[
                    RuleTemplateParameterResponse(
                        name="market_purpose",
                        description=(
                            "Codigo do mercado usado no fact_type da qualificacao do "
                            "estabelecimento."
                        ),
                        example="exportacao-china",
                    )
                ],
            ),
            RuleTemplateCatalogResponse(
                template_code="sanitary-requirement-campaign-v1",
                rule_code=SANITARY_RULE_CODE,
                name="Campanha sanitaria obrigatoria",
                purpose_hint="Usar quando o mercado exige uma campanha ou vacina especifica.",
                scope_hint="livestock.animal",
                normative_source_hint=(
                    "Lei nacional, protocolo internacional ou exigencia sanitaria do mercado."
                ),
                required_evidence_types=["livestock.sanitary_requirement.<campanha>"],
                conditions=[
                    RuleTemplateConditionResponse(
                        fact_type=sanitary_requirement_fact_type("{{campaign_code}}"),
                        payload_key="status",
                        operator=ComparisonOperator.EQUALS.value,
                        expected_value="SATISFEITO",
                        description="A campanha sanitaria exigida precisa estar satisfeita.",
                    )
                ],
                justification_hint="Campanha sanitaria exigida nao atendida para este destino.",
                corrective_action_hint=(
                    "Aplicar a campanha obrigatoria e aguardar a situacao ficar satisfeita."
                ),
                parameters=[
                    RuleTemplateParameterResponse(
                        name="campaign_code",
                        description="Codigo canonico da campanha sanitaria exigida.",
                        example="brucelose",
                    )
                ],
            ),
        ],
    )


def _obrigar_parametro(parameters: dict[str, str], nome: str) -> str:
    valor = parameters.get(nome, "").strip()
    if not valor:
        raise DomainProblem(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            reason_code="PARAMETRO_DE_TEMPLATE_INVALIDO",
            title="Parametro de template invalido",
            detail=f"O parametro '{nome}' precisa ser informado para materializar o template.",
        )
    return valor


def _substituir_placeholders(valor: str, parameters: dict[str, str]) -> str:
    materializado = valor
    for nome, conteudo in parameters.items():
        materializado = materializado.replace(f"{{{{{nome}}}}}", conteudo.strip())
    return materializado


def _materializar_template_livestock(
    template_code: str,
    body: MaterializarTemplateRegraRequest,
) -> MaterializedRuleDraftResponse:
    templates = {
        item.template_code: item for item in _catalogo_regras_mercado_livestock().templates
    }
    template = templates.get(template_code)
    if template is None:
        raise DomainProblem(
            status_code=status.HTTP_404_NOT_FOUND,
            reason_code="RECURSO_NAO_ENCONTRADO",
            title="Template nao encontrado",
            detail="Template de regra nao encontrado neste catalogo.",
        )

    parameters = {chave: valor.strip() for chave, valor in body.parameters.items()}
    for parametro in template.parameters:
        _obrigar_parametro(parameters, parametro.name)

    conditions = [
        RuleTemplateConditionResponse(
            fact_type=_substituir_placeholders(condition.fact_type, parameters),
            payload_key=condition.payload_key,
            operator=condition.operator,
            expected_value=condition.expected_value,
            description=condition.description,
        )
        for condition in template.conditions
    ]
    required_evidence_types = [
        _substituir_placeholders(item, parameters) for item in template.required_evidence_types
    ]
    normative_source = body.normative_source.strip() or template.normative_source_hint

    return MaterializedRuleDraftResponse(
        template_code=template.template_code,
        rule_code=template.rule_code,
        name=body.name,
        description=body.description,
        severity=SeverityLevel.BLOCKING.value,
        normative_source=normative_source,
        required_evidence_types=required_evidence_types,
        conditions=conditions,
        justification=template.justification_hint,
        corrective_action=template.corrective_action_hint,
    )


def _exigir_permissao(contexto: OrganizationContext, code: str) -> None:
    if code not in contexto.permission_codes:
        raise DomainProblem(
            status_code=status.HTTP_403_FORBIDDEN,
            reason_code="PERMISSAO_AUSENTE",
            title="Permissao ausente",
            detail=f"A operacao exige a permissao {code}.",
        )


def _slug_regra(valor: str) -> str:
    slug = "".join(caractere.lower() if caractere.isalnum() else "-" for caractere in valor.strip())
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-")


def _sugerir_fluxo_governanca_livestock(
    template_code: str,
    body: SugerirFluxoGovernancaRegraRequest,
) -> SuggestedGovernanceFlowResponse:
    versao = _materializar_template_livestock(
        template_code,
        MaterializarTemplateRegraRequest(
            name=body.name,
            description=body.version_description,
            normative_source=body.normative_source,
            parameters=body.parameters,
        ),
    )
    identity_code = (body.identity_code or versao.rule_code).strip()
    identity_purpose = (
        body.identity_purpose or f"Aplicar '{body.name}' para o mercado '{body.market_purpose}'."
    ).strip()
    identity_scope = (body.identity_scope or body.adoption_scope).strip()
    if not identity_code:
        identity_code = _slug_regra(f"{versao.rule_code}-{body.market_purpose}")
    adoption_reason = body.adoption_reason.strip() or (
        f"Ativar regra governada para o mercado '{body.market_purpose}'."
    )
    return SuggestedGovernanceFlowResponse(
        template_code=template_code,
        identity=SuggestedRuleIdentityDraftResponse(
            code=identity_code,
            purpose=identity_purpose,
            scope=identity_scope,
            source_type=RuleSourceType.INTERNAL_POLICY.value,
            vertical="livestock",
            description=body.identity_description,
        ),
        version=versao,
        adoption=SuggestedRuleAdoptionDraftResponse(
            purpose=body.market_purpose,
            scope=body.adoption_scope,
            reason=adoption_reason,
        ),
    )


def _executar_fluxo_governanca_livestock(
    connection: Connection,
    contexto: OrganizationContext,
    template_code: str,
    body: ExecutarFluxoGovernancaRegraRequest,
) -> ExecutedGovernanceFlowResponse:
    _exigir_permissao(contexto, RULE_GOVERNANCE_CRIAR)
    fluxo = _sugerir_fluxo_governanca_livestock(
        template_code,
        SugerirFluxoGovernancaRegraRequest(
            market_purpose=body.market_purpose,
            adoption_scope=body.adoption_scope,
            name=body.name,
            normative_source=body.normative_source,
            identity_code=body.identity_code,
            identity_purpose=body.identity_purpose,
            identity_scope=body.identity_scope,
            identity_description=body.identity_description,
            version_description=body.version_description,
            adoption_reason=body.adoption_reason,
            parameters=body.parameters,
        ),
    )
    policy_id = typed_id_or_problem(body.policy_id, entity_type="policy", campo="policy_id")
    service = _servico(connection)
    actor = _actor(contexto)
    try:
        identity = service.create_identity(
            organization_id=contexto.organization_id,
            code=fluxo.identity.code,
            purpose=fluxo.identity.purpose,
            scope=fluxo.identity.scope,
            source_type=RuleSourceType.INTERNAL_POLICY,
            actor=actor,
            vertical=fluxo.identity.vertical,
            description=fluxo.identity.description,
        )
        version = service.publish_rule_version(
            organization_id=contexto.organization_id,
            rule_identity_id=identity.rule_identity_id,
            policy_id=policy_id,
            name=fluxo.version.name,
            description=fluxo.version.description,
            severity=SeverityLevel(fluxo.version.severity),
            normative_source=fluxo.version.normative_source,
            required_evidence_types=tuple(fluxo.version.required_evidence_types),
            conditions=tuple(
                RuleCondition(
                    fact_type=condition.fact_type,
                    payload_key=condition.payload_key,
                    operator=ComparisonOperator(condition.operator),
                    expected_value=condition.expected_value,
                    description=condition.description,
                )
                for condition in fluxo.version.conditions
            ),
            justification=fluxo.version.justification,
            corrective_action=fluxo.version.corrective_action,
            actor=actor,
        )
        adoption = None
        if body.create_adoption:
            _exigir_permissao(contexto, RULE_GOVERNANCE_ADOTAR)
            adoption = service.adopt_rule_version(
                organization_id=contexto.organization_id,
                rule_identity_id=identity.rule_identity_id,
                rule_version_id=version.rule_id,
                purpose=fluxo.adoption.purpose,
                scope=fluxo.adoption.scope,
                reason=fluxo.adoption.reason,
                actor=actor,
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
    return ExecutedGovernanceFlowResponse(
        template_code=template_code,
        identity=_identity_response(identity),
        version=_rule_response(version),
        adoption=None if adoption is None else _adoption_response(adoption),
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


@router.post(
    "/rule-identities/{rule_identity_id}/adoptions",
    response_model=RuleAdoptionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Adotar uma versao de regra governada",
    responses=RESPOSTAS_PADRAO,
)
def adotar_regra(
    rule_identity_id: str,
    corpo: AdotarRegraRequest,
    contexto: Annotated[OrganizationContext, Depends(require_permission(RULE_GOVERNANCE_ADOTAR))],
    connection: ConnectionDependency,
) -> RuleAdoptionResponse:
    identity_id = typed_id_or_problem(
        rule_identity_id, entity_type="rule_identity", campo="rule_identity_id"
    )
    rule_version_id = typed_id_or_problem(
        corpo.rule_version_id, entity_type="rule", campo="rule_version_id"
    )
    try:
        adoption = _servico(connection).adopt_rule_version(
            organization_id=contexto.organization_id,
            rule_identity_id=identity_id,
            rule_version_id=rule_version_id,
            purpose=corpo.purpose,
            scope=corpo.scope,
            reason=corpo.reason,
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
    return _adoption_response(adoption)


@router.post(
    "/rule-identities/{rule_identity_id}/adoptions/replace",
    response_model=RuleAdoptionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Substituir a adocao ativa por outra versao da regra",
    responses=RESPOSTAS_PADRAO,
)
def substituir_adocao_regra(
    rule_identity_id: str,
    corpo: SubstituirAdocaoRegraRequest,
    contexto: Annotated[OrganizationContext, Depends(require_permission(RULE_GOVERNANCE_ADOTAR))],
    connection: ConnectionDependency,
) -> RuleAdoptionResponse:
    identity_id = typed_id_or_problem(
        rule_identity_id, entity_type="rule_identity", campo="rule_identity_id"
    )
    current_adoption_id = typed_id_or_problem(
        corpo.current_adoption_id,
        entity_type="rule_adoption",
        campo="current_adoption_id",
    )
    new_rule_version_id = typed_id_or_problem(
        corpo.new_rule_version_id,
        entity_type="rule",
        campo="new_rule_version_id",
    )
    try:
        adoption = _servico(connection).replace_rule_adoption(
            organization_id=contexto.organization_id,
            rule_identity_id=identity_id,
            current_adoption_id=current_adoption_id,
            new_rule_version_id=new_rule_version_id,
            reason=corpo.reason,
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
    return _adoption_response(adoption)


@router.get(
    "/rule-identities/{rule_identity_id}/timeline",
    response_model=Pagina[TimelineEventResponse],
    summary="Consultar a linha do tempo imutavel de uma regra",
    description=(
        "Uma regra ativamente governada acumula evento a cada versao publicada, "
        "adocao e substituicao de adocao, sem teto natural ao longo dos anos -- "
        "por isso paginada como as demais listagens da API."
    ),
    responses=RESPOSTAS_PADRAO,
)
def consultar_timeline_regra(
    rule_identity_id: str,
    contexto: Annotated[OrganizationContext, Depends(require_permission(RULE_GOVERNANCE_LER))],
    connection: ConnectionDependency,
    paginacao: PaginacaoDependency,
) -> dict[str, Any]:
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
        contexto.organization_id,
        identity_id,
        limit=paginacao.limite_de_sondagem,
        offset=paginacao.offset,
    )
    return montar_pagina([_timeline_response(event) for event in events], paginacao)


@router.get(
    "/catalogs/livestock-market-rules",
    response_model=LivestockMarketRuleCatalogResponse,
    summary="Consultar catalogo inicial de fatos e templates para regras de mercado da vertical",
    description=(
        "Publica os fact_types e templates base usados hoje pela vertical Livestock "
        "para que a criacao de regras governadas nao dependa de montar conditions "
        "do zero."
    ),
    responses=RESPOSTAS_PADRAO,
)
def consultar_catalogo_regras_mercado_livestock(
    contexto: Annotated[OrganizationContext, Depends(require_permission(RULE_GOVERNANCE_LER))],
) -> LivestockMarketRuleCatalogResponse:
    del contexto
    return _catalogo_regras_mercado_livestock()


@router.post(
    "/catalogs/livestock-market-rules/templates/{template_code}/drafts",
    response_model=MaterializedRuleDraftResponse,
    summary="Materializar um template de regra de mercado em rascunho publicavel",
    description=(
        "Transforma um template do catalogo em um rascunho pronto para ser usado "
        "no corpo de publicacao de versao de regra."
    ),
    responses=RESPOSTAS_PADRAO,
)
def materializar_template_regra_mercado_livestock(
    template_code: str,
    corpo: MaterializarTemplateRegraRequest,
    contexto: Annotated[OrganizationContext, Depends(require_permission(RULE_GOVERNANCE_PUBLICAR))],
) -> MaterializedRuleDraftResponse:
    del contexto
    return _materializar_template_livestock(template_code, corpo)


@router.post(
    "/catalogs/livestock-market-rules/templates/{template_code}/governance-flow",
    response_model=SuggestedGovernanceFlowResponse,
    summary="Sugerir o fluxo completo de governanca para uma regra de mercado",
    description=(
        "Devolve os rascunhos sugeridos para criar a identidade da regra, "
        "publicar a versao materializada e adotar a regra no mercado desejado."
    ),
    responses=RESPOSTAS_PADRAO,
)
def sugerir_fluxo_governanca_regra_mercado_livestock(
    template_code: str,
    corpo: SugerirFluxoGovernancaRegraRequest,
    contexto: Annotated[OrganizationContext, Depends(require_permission(RULE_GOVERNANCE_PUBLICAR))],
) -> SuggestedGovernanceFlowResponse:
    del contexto
    return _sugerir_fluxo_governanca_livestock(template_code, corpo)


@router.post(
    "/catalogs/livestock-market-rules/templates/{template_code}/execute",
    response_model=ExecutedGovernanceFlowResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Executar o fluxo assistido de governanca para uma regra de mercado",
    description=(
        "Cria a identidade da regra, publica a versao materializada e, quando "
        "solicitado, ja registra a adocao para o mercado informado."
    ),
    responses=RESPOSTAS_PADRAO,
)
def executar_fluxo_governanca_regra_mercado_livestock(
    template_code: str,
    corpo: ExecutarFluxoGovernancaRegraRequest,
    contexto: Annotated[OrganizationContext, Depends(require_permission(RULE_GOVERNANCE_PUBLICAR))],
    connection: ConnectionDependency,
) -> ExecutedGovernanceFlowResponse:
    return _executar_fluxo_governanca_livestock(connection, contexto, template_code, corpo)
