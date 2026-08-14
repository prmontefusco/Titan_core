"""Elegibilidade, linha do tempo e dossiê (Passo 10.4b).

**A elegibilidade é POST, e não GET, porque ela não é uma consulta.** Executá-la
produz uma `Evaluation`, uma `Decision` e um `Dossier` — três registros
permanentes. Um GET que grava prova quebra a expectativa de quem integra, e
qualquer intermediário que decida repetir a chamada produziria registros
duplicados.

A linha do tempo e o dossiê são GET de verdade: leem e não escrevem nada.
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel
from sqlalchemy import Connection

from apps.api.geodata_dependencies import car_lookup_opcional
from apps.api.livestock_dependencies import (
    ConnectionDependency,
    require_permission,
    typed_id_or_problem,
)
from apps.api.livestock_transformations import BalancoResponse, _balanco_resposta
from apps.api.pagination import PaginacaoDependency, montar_pagina
from apps.api.problem import RESPOSTAS_PADRAO, DomainProblem
from packages.core_application.decision_governance_service import (
    DecisionGovernanceService,
)
from packages.core_application.dossier_service import DossierService, evidence_content
from packages.core_application.recall_service import RecallService
from packages.core_domain import OrganizationContext
from packages.core_domain.decision_authority import DecisionEmissionMethod
from packages.core_domain.decision_governance import (
    DecisionAuthorityProfile,
    DecisionProposal,
    ReviewConclusion,
)
from packages.core_domain.evaluation import Evaluation
from packages.core_domain.policy import Policy
from packages.core_domain.recall import (
    RecallDirection,
    RecallMode,
    RecallRequest,
    RecallResult,
)
from packages.core_infrastructure.persistence.authorization import AuthorizationRepository
from packages.core_infrastructure.persistence.decision import TransactionalDecisionRepository
from packages.core_infrastructure.persistence.decision_governance import (
    TransactionalDecisionAuthorityProfileRepository,
    TransactionalDecisionGovernanceRepository,
)
from packages.core_infrastructure.persistence.dossier import TransactionalDossierRepository
from packages.core_infrastructure.persistence.evaluation import (
    TransactionalEvaluationRepository,
)
from packages.core_infrastructure.persistence.events import DomainEventRepository
from packages.core_infrastructure.persistence.evidence import TransactionalEvidenceRepository
from packages.core_infrastructure.persistence.policy import TransactionalPolicyRepository
from packages.core_infrastructure.persistence.relations import TransactionalRelationRepository
from packages.core_infrastructure.persistence.rule import TransactionalRuleRepository
from packages.core_infrastructure.persistence.rule_governance import (
    TransactionalRuleAdoptionRepository,
)
from packages.livestock_application.authorization import (
    DECISION_REVIEW_EXECUTE,
    DOSSIER_LER,
    ELIGIBILITY_EXECUTAR,
    TIMELINE_LER,
    TRACEABILITY_LER,
)
from packages.livestock_application.dossier_template import LivestockDossierTemplate
from packages.livestock_application.eligibility import (
    ELIGIBILITY_PURPOSE,
    ELIGIBILITY_RULE_ADOPTION_SCOPE,
    ELIGIBILITY_RULE_CODE,
    GovernedRuleReference,
    HumanReviewRequired,
    PharmacologicalEligibilityService,
)
from packages.livestock_application.eligibility_policy_provider import (
    EligibilityPolicyProvider,
)
from packages.livestock_application.event_recorder import AGGREGATE_CONTRACT_VERSION
from packages.livestock_application.fact_provider import LivestockFactProvider
from packages.livestock_application.market_eligibility import (
    DEFAULT_MARKET_PROFILES,
    MarketEligibilityService,
    MarketProfile,
)
from packages.livestock_application.temporal_campaign import TemporalSanitaryCampaignReader
from packages.livestock_application.temporal_identifier import TemporalAnimalIdentifierReader
from packages.livestock_application.temporal_treatment import TemporalTreatmentApplicationReader
from packages.livestock_application.temporal_withdrawal import TemporalWithdrawalReader
from packages.livestock_application.territorial_overlap_service import (
    TerritorialOverlapService,
)
from packages.livestock_application.territorial_timeline_service import (
    TerritorialTimelineService,
)
from packages.livestock_application.timeline_service import (
    LivestockTimelineService,
    TimelineCutoff,
    TimelineEntry,
)
from packages.livestock_application.transformation_service import (
    TRANSFORMATION_INPUT_OF,
    TRANSFORMATION_OUTPUT_OF,
    operational_status_now,
)
from packages.livestock_application.withdrawal_service import WithdrawalCalculator
from packages.livestock_domain.transformation import (
    TraceableItem,
    TraceableItemType,
    TransformationEvent,
    TransformationParticipant,
)
from packages.livestock_infrastructure.persistence import (
    TransactionalPropertyEnvironmentalEmbargoAssertionRepository,
)
from packages.livestock_infrastructure.persistence.animal_repository import (
    TransactionalAnimalRepository,
)
from packages.livestock_infrastructure.persistence.coverage_contribution_repository import (
    TransactionalCoverageContributionRepository,
)
from packages.livestock_infrastructure.persistence.establishment_qualification_repository import (
    TransactionalEstablishmentQualificationRepository,
)
from packages.livestock_infrastructure.persistence.external_counterparty_repository import (
    TransactionalExternalCounterpartyRepository,
)
from packages.livestock_infrastructure.persistence.geometry_repository import (
    TransactionalPropertyGeometryRepository,
)
from packages.livestock_infrastructure.persistence.imported_fact_repository import (
    TransactionalImportedLivestockFactRepository,
)
from packages.livestock_infrastructure.persistence.lot_repository import (
    TransactionalLivestockLotRepository,
    TransactionalLotMembershipRepository,
)
from packages.livestock_infrastructure.persistence.medication_classification_repository import (
    TransactionalMedicationClassificationRepository,
)
from packages.livestock_infrastructure.persistence.medication_repository import (
    TransactionalMedicationBatchRepository,
    TransactionalMedicationRepository,
)
from packages.livestock_infrastructure.persistence.movement_repository import (
    TransactionalAnimalMovementRepository,
    TransactionalPropertyStayRepository,
)
from packages.livestock_infrastructure.persistence.property_repository import (
    TransactionalRuralPropertyRepository,
)
from packages.livestock_infrastructure.persistence.qualification_assertion_repository import (
    TransactionalEstablishmentQualificationAssertionRepository,
)
from packages.livestock_infrastructure.persistence.sanitary_campaign_repository import (
    TransactionalSanitaryCampaignRepository,
)
from packages.livestock_infrastructure.persistence.transfer_artifact_repository import (
    TransactionalReceivedTransferArtifactRepository,
)
from packages.livestock_infrastructure.persistence.transformation_repository import (
    TransactionalTraceableItemRepository,
    TransactionalTransformationEventRepository,
)
from packages.livestock_infrastructure.persistence.treatment_repository import (
    TransactionalTreatmentApplicationRepository,
)
from packages.shared_kernel import OrganizationId, UniversalReference
from packages.shared_kernel import TypedId as SharedTypedId

router = APIRouter(prefix="/v1/livestock", tags=["livestock"])


def _human_review_problem(exc: HumanReviewRequired) -> DomainProblem:
    return DomainProblem(
        status_code=status.HTTP_409_CONFLICT,
        reason_code="REVISAO_HUMANA_NECESSARIA",
        title="Revisao humana necessaria",
        detail=(
            "A avaliacao foi preservada, mas a emissao automatica da decision foi "
            "recusada e uma proposta formal de revisao humana foi aberta."
        ),
        extra={
            "evaluation_id": str(exc.evaluation.evaluation_id.value),
            "evaluation_outcome": exc.evaluation.outcome.value,
            "knowledge_cutoff": (
                exc.evaluation.fact_snapshot.effective_knowledge_cutoff().isoformat()
            ),
            "knowledge_limitations": list(exc.evaluation.fact_snapshot.knowledge_limitations),
            "proposal_id": str(exc.proposal.proposal_id.value),
            "proposal_result": exc.proposal.proposed_result.value,
        },
    )


class ElegibilidadeResponse(BaseModel):
    animal_id: str
    result: str
    outcome: str
    evaluation_id: str
    knowledge_cutoff: str
    knowledge_limitations: list[str]
    decision_id: str
    dossier_id: str
    reasons: list[str]
    governed_rule: dict[str, str] | None = None


class LinhaDoTempoResponse(BaseModel):
    animal_id: str
    known_until: str | None
    entry_count: int
    entries: list[dict[str, Any]]


class MatrizMercadoResponse(BaseModel):
    animal_id: str
    evaluation_id: str
    knowledge_cutoff: str
    knowledge_limitations: list[str]
    decision_id: str
    dossier_id: str
    markets: list[dict[str, Any]]


class AvaliacaoMercadosRequest(BaseModel):
    animal_id: str
    markets: list[str] | None = None
    slaughterhouse_counterparty_id: str | None = None


class AvaliacaoMercadosResponse(BaseModel):
    animal_id: str
    requested_markets: list[str]
    commercial_outlook: str
    can_sell_to_any_requested_market: bool
    executive_summary: str
    eligible_markets: list[str]
    blocked_markets: list[str]
    conditioned_markets: list[str]
    indeterminate_markets: list[str]
    missing_markets: list[str]
    required_subjects: list[dict[str, str]]
    market_gaps: list[dict[str, str]]
    evaluation_id: str
    knowledge_cutoff: str
    knowledge_limitations: list[str]
    decision_id: str
    dossier_id: str
    markets: list[dict[str, Any]]


class AvaliacaoMercadosLoteRequest(BaseModel):
    lot_id: str
    markets: list[str] | None = None
    slaughterhouse_counterparty_id: str | None = None


class AvaliacaoMercadosLoteResponse(BaseModel):
    lot_id: str
    member_count: int
    requested_markets: list[str]
    commercial_outlook: str
    can_sell_to_any_requested_market: bool
    executive_summary: str
    eligible_markets: list[str]
    blocked_markets: list[str]
    conditioned_markets: list[str]
    indeterminate_markets: list[str]
    missing_markets: list[str]
    required_subjects: list[dict[str, str]]
    market_gaps: list[dict[str, str]]
    markets: list[dict[str, Any]]


class PerfilMercadoRequisitoResponse(BaseModel):
    rule_code: str
    scope: str
    dependent_subject_key: str | None = None
    dependent_subject_label: str | None = None


class PerfilMercadoResponse(BaseModel):
    market: str
    declared_withdrawal_period_days: int | None
    withdrawal_basis: dict[str, Any] | None = None
    requirements: list[PerfilMercadoRequisitoResponse]


class DecisionProposalResponse(BaseModel):
    proposal_id: str
    evaluation_id: str
    evaluation_hash: str
    purpose: str
    proposed_result: str
    proposed_reasons: list[dict[str, Any]]
    justification_required: bool
    created_at: str
    review_count: int
    current_proposal: bool


class DecisionReviewRequest(BaseModel):
    conclusion: ReviewConclusion
    reasoning: str


class DecisionReviewExecutionResponse(BaseModel):
    proposal_id: str
    review_id: str
    workflow_status: str
    decision_id: str | None = None
    dossier_id: str | None = None


class ExplicacaoComercialRequest(BaseModel):
    animal_id: str | None = None
    lot_id: str | None = None
    markets: list[str] | None = None
    slaughterhouse_counterparty_id: str | None = None


class ExplicacaoMercadoResponse(BaseModel):
    market: str
    status: str
    summary: str
    why: list[str]
    next_action: str | None = None
    affected_animal_ids: list[str] = []


class ExplicacaoComercialResponse(BaseModel):
    subject_type: str
    subject_id: str
    requested_markets: list[str]
    commercial_outlook: str
    can_sell_to_any_requested_market: bool
    executive_summary: str
    narrative: str
    recommended_next_action: str | None = None
    markets: list[ExplicacaoMercadoResponse]


class LinhaDoTempoItemResponse(BaseModel):
    item_id: str
    known_until: str | None
    entry_count: int
    entries: list[dict[str, Any]]


class RecallPassoResponse(BaseModel):
    relation_type: str
    de_tipo: str
    de_id: str
    de_status: str | None = None
    para_tipo: str
    para_id: str
    para_status: str | None = None
    direcao: str


class RecallCaminhoResponse(BaseModel):
    passos: list[RecallPassoResponse]
    explicacao: str


class RecallLacunaResponse(BaseModel):
    motivo: str
    profundidade: int
    descricao: str


class RecallResponse(BaseModel):
    recall_id: str
    subject_type: str
    subject_id: str
    status: str
    visited_nodes: int
    caminhos: list[RecallCaminhoResponse]
    lacunas: list[RecallLacunaResponse]


class MatrizMercadoRequest(BaseModel):
    slaughterhouse_counterparty_id: str | None = None


class ItemResponse(BaseModel):
    item_id: str
    item_type: TraceableItemType
    label: str | None
    created_at: datetime
    created_by_transformation_id: str | None


class QuantidadeResponse(BaseModel):
    quantity: str | None
    unit: str
    measurement_basis: str | None


class TransformacaoResumoResponse(BaseModel):
    transformation_id: str
    process_type: str
    occurred_at: datetime
    facility_id: str
    balance: BalancoResponse
    status: str
    corrected_by_transformation_id: str | None = None


class EvidenciaDossierResponse(BaseModel):
    id: str
    content_status: str
    content: dict[str, Any] | None


class ItemDossierResponse(BaseModel):
    item: ItemResponse
    transformation: TransformacaoResumoResponse
    quantitative: QuantidadeResponse | None
    timeline: LinhaDoTempoItemResponse
    origins: RecallResponse
    evidences: list[EvidenciaDossierResponse]


def _timeline_service(connection: Connection) -> LivestockTimelineService:
    return LivestockTimelineService(
        event_reader=DomainEventRepository(connection=connection),
        movement_repository=TransactionalAnimalMovementRepository(connection=connection),
        application_repository=TransactionalTreatmentApplicationRepository(connection=connection),
        membership_repository=TransactionalLotMembershipRepository(connection=connection),
        batch_repository=TransactionalMedicationBatchRepository(connection=connection),
        evaluation_repository=TransactionalEvaluationRepository(connection=connection),
        decision_repository=TransactionalDecisionRepository(connection=connection),
        relation_repository=TransactionalRelationRepository(connection=connection),
    )


def _entradas_para_json(entradas: Sequence[TimelineEntry]) -> list[dict[str, Any]]:
    return [
        {
            "occurred_at": entrada.occurred_at.isoformat(),
            "recorded_at": entrada.recorded_at.isoformat(),
            "entry_type": entrada.entry_type,
            "source_kind": entrada.source_kind.value,
            "aggregate_type": entrada.aggregate_id.entity_type,
            "aggregate_id": str(entrada.aggregate_id.value),
            "superseded_by": (str(entrada.superseded_by.value) if entrada.superseded_by else None),
        }
        for entrada in entradas
    ]


def _eligibility_components(
    connection: Connection,
    animal_repository: TransactionalAnimalRepository,
) -> tuple[
    TransactionalTreatmentApplicationRepository,
    TransactionalEvaluationRepository,
    TransactionalDecisionRepository,
    LivestockFactProvider,
]:
    application_repository = TransactionalTreatmentApplicationRepository(connection=connection)
    batch_repository = TransactionalMedicationBatchRepository(connection=connection)
    evaluations = TransactionalEvaluationRepository(connection=connection)
    decisions = TransactionalDecisionRepository(connection=connection)
    geodata = car_lookup_opcional()
    fact_provider = LivestockFactProvider(
        property_repository=TransactionalRuralPropertyRepository(connection=connection),
        animal_repository=animal_repository,
        external_counterparty_repository=TransactionalExternalCounterpartyRepository(
            connection=connection
        ),
        establishment_qualification_repository=TransactionalEstablishmentQualificationRepository(
            connection=connection
        ),
        establishment_qualification_assertion_repository=(
            TransactionalEstablishmentQualificationAssertionRepository(connection=connection)
        ),
        environmental_embargo_assertion_repository=(
            TransactionalPropertyEnvironmentalEmbargoAssertionRepository(connection=connection)
        ),
        imported_fact_repository=TransactionalImportedLivestockFactRepository(
            connection=connection
        ),
        transfer_artifact_repository=TransactionalReceivedTransferArtifactRepository(
            connection=connection
        ),
        stay_repository=TransactionalPropertyStayRepository(connection=connection),
        movement_repository=TransactionalAnimalMovementRepository(connection=connection),
        temporal_identifier_reader=TemporalAnimalIdentifierReader(
            event_reader=DomainEventRepository(connection=connection)
        ),
        temporal_treatment_reader=TemporalTreatmentApplicationReader(
            application_repository=application_repository,
            event_reader=DomainEventRepository(connection=connection),
        ),
        temporal_withdrawal_reader=TemporalWithdrawalReader(
            treatment_reader=TemporalTreatmentApplicationReader(
                application_repository=application_repository,
                event_reader=DomainEventRepository(connection=connection),
            ),
            batch_repository=batch_repository,
            medication_repository=TransactionalMedicationRepository(connection=connection),
            event_reader=DomainEventRepository(connection=connection),
        ),
        temporal_campaign_reader=TemporalSanitaryCampaignReader(
            campaign_repository=TransactionalSanitaryCampaignRepository(connection=connection),
            event_reader=DomainEventRepository(connection=connection),
        ),
        withdrawal_calculator=WithdrawalCalculator(
            application_repository=application_repository,
            batch_repository=batch_repository,
            medication_repository=TransactionalMedicationRepository(connection=connection),
        ),
        sanitary_campaign_repository=TransactionalSanitaryCampaignRepository(connection=connection),
        treatment_application_repository=application_repository,
        coverage_contribution_repository=TransactionalCoverageContributionRepository(
            connection=connection
        ),
        medication_classification_repository=TransactionalMedicationClassificationRepository(
            connection=connection
        ),
        territorial_timeline_service=(
            TerritorialTimelineService(
                property_repository=TransactionalRuralPropertyRepository(connection=connection),
                geometry_repository=TransactionalPropertyGeometryRepository(connection=connection),
                geodata_lookup=geodata,
            )
            if geodata is not None
            else None
        ),
        territorial_overlap_service=(
            TerritorialOverlapService(
                property_repository=TransactionalRuralPropertyRepository(connection=connection),
                geometry_repository=TransactionalPropertyGeometryRepository(connection=connection),
                geodata_lookup=geodata,
            )
            if geodata is not None
            else None
        ),
        # Necessário para a elegibilidade de LOTE (rule-carencia-lote): sem o
        # repositório de vínculos, o fact_provider não consegue enumerar quem
        # está no lote para computar has_animal_in_withdrawal/blocking_animals.
        membership_repository=TransactionalLotMembershipRepository(connection=connection),
    )
    return application_repository, evaluations, decisions, fact_provider


def _governed_rule_reference(
    connection: Connection, organizacao: OrganizationId
) -> GovernedRuleReference | None:
    adoption = TransactionalRuleAdoptionRepository(connection).get_active_by_code_purpose_and_scope(
        organizacao,
        ELIGIBILITY_RULE_CODE,
        ELIGIBILITY_PURPOSE,
        ELIGIBILITY_RULE_ADOPTION_SCOPE,
    )
    if adoption is None:
        return None
    return GovernedRuleReference(
        adoption_id=adoption.adoption_id,
        rule_identity_id=adoption.rule_identity_id,
        rule_version_id=adoption.rule_version_id,
        purpose=adoption.purpose,
        scope=adoption.scope,
    )


def _animal_existente_ou_404(
    connection: Connection,
    animal_id: SharedTypedId,
) -> TransactionalAnimalRepository:
    animal_repository = TransactionalAnimalRepository(connection=connection)
    if animal_repository.get_by_id(animal_id) is None:
        raise DomainProblem(
            status_code=status.HTTP_404_NOT_FOUND,
            reason_code="RECURSO_NAO_ENCONTRADO",
            title="Recurso nao encontrado",
            detail="Animal nao encontrado nesta organizacao.",
        )
    return animal_repository


def _selected_subjects_from_market_request(
    slaughterhouse_counterparty_id: str | None,
) -> dict[str, SharedTypedId]:
    if slaughterhouse_counterparty_id is None:
        return {}
    return {
        "slaughterhouse": typed_id_or_problem(
            slaughterhouse_counterparty_id,
            entity_type="external_counterparty",
            campo="slaughterhouse_counterparty_id",
        )
    }


def _market_profiles_for_codes(
    market_codes: Sequence[str] | None,
) -> tuple[MarketProfile, ...]:
    if market_codes is None:
        return DEFAULT_MARKET_PROFILES

    requested = [code.strip() for code in market_codes]
    if not requested:
        raise DomainProblem(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            reason_code="ENTRADA_INVALIDA",
            title="Entrada invalida",
            detail="Informe ao menos um mercado ou omita o campo para usar os mercados padrao.",
        )

    duplicated: set[str] = set()
    unique_requested: list[str] = []
    for code in requested:
        if code in unique_requested:
            duplicated.add(code)
            continue
        unique_requested.append(code)
    if duplicated:
        repetidos = ", ".join(sorted(duplicated))
        raise DomainProblem(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            reason_code="ENTRADA_INVALIDA",
            title="Entrada invalida",
            detail=f"Mercados repetidos na solicitacao: {repetidos}.",
        )

    profiles_by_code = {profile.market.code: profile for profile in DEFAULT_MARKET_PROFILES}
    invalid = [code for code in unique_requested if code not in profiles_by_code]
    if invalid:
        supported = ", ".join(sorted(profiles_by_code))
        invalid_list = ", ".join(invalid)
        raise DomainProblem(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            reason_code="ENTRADA_INVALIDA",
            title="Entrada invalida",
            detail=f"Mercados nao suportados: {invalid_list}. Suportados: {supported}.",
        )
    return tuple(profiles_by_code[code] for code in unique_requested)


def _perfil_mercado_response(profile: MarketProfile) -> PerfilMercadoResponse:
    return PerfilMercadoResponse(
        market=profile.market.code,
        declared_withdrawal_period_days=profile.declared_withdrawal_period_days,
        withdrawal_basis=(
            None if profile.withdrawal_basis is None else profile.withdrawal_basis.to_dict()
        ),
        requirements=[
            PerfilMercadoRequisitoResponse(
                rule_code=requirement.rule_code,
                scope=requirement.scope,
                dependent_subject_key=requirement.dependent_subject_key,
                dependent_subject_label=requirement.dependent_subject_label,
            )
            for requirement in profile.requirements
        ],
    )


def _market_codes_by_status(
    matrix: Any,
) -> tuple[list[str], list[str], list[str], list[str], list[str]]:
    eligible_markets: list[str] = []
    blocked_markets: list[str] = []
    conditioned_markets: list[str] = []
    indeterminate_markets: list[str] = []
    missing_markets: list[str] = []

    for entry in matrix.entries:
        code = entry.market.code
        if entry.status.value == "ELEGIVEL":
            eligible_markets.append(code)
        elif entry.status.value == "NAO_ELEGIVEL":
            blocked_markets.append(code)
        elif entry.status.value == "CONDICIONADO":
            conditioned_markets.append(code)
        elif entry.status.value == "INDETERMINADO":
            indeterminate_markets.append(code)
        elif entry.status.value == "AUSENTE":
            missing_markets.append(code)

    return (
        eligible_markets,
        blocked_markets,
        conditioned_markets,
        indeterminate_markets,
        missing_markets,
    )


def _proposal_response(
    proposal: DecisionProposal,
    *,
    review_count: int,
    current_proposal: bool,
) -> DecisionProposalResponse:
    return DecisionProposalResponse(
        proposal_id=str(proposal.proposal_id.value),
        evaluation_id=str(proposal.evaluation_id.value),
        evaluation_hash=proposal.evaluation_hash,
        purpose=proposal.purpose,
        proposed_result=proposal.proposed_result.value,
        proposed_reasons=[reason.to_dict() for reason in proposal.proposed_reasons],
        justification_required=proposal.justification_required,
        created_at=proposal.created_at.isoformat(),
        review_count=review_count,
        current_proposal=current_proposal,
    )


def _resolve_decision_review_authority(
    connection: Connection,
    contexto: OrganizationContext,
    *,
    purpose: str,
) -> DecisionAuthorityProfile:
    authorization = AuthorizationRepository(connection)
    permission_id = authorization.get_permission_id_by_code(DECISION_REVIEW_EXECUTE)
    if permission_id is None:
        raise DomainProblem(
            status_code=status.HTTP_409_CONFLICT,
            reason_code="AUTORIDADE_DE_DECISAO_AUSENTE",
            title="Autoridade de decisao indisponivel",
            detail="A permissao tecnica do fluxo de revisao humana nao esta catalogada.",
        )

    matching_roles = []
    for role_id in contexto.role_ids:
        role = authorization.get_role_by_id(contexto.organization_id, role_id)
        if role is None:
            continue
        if permission_id in role.permission_ids:
            matching_roles.append(role)

    if not matching_roles:
        raise DomainProblem(
            status_code=status.HTTP_403_FORBIDDEN,
            reason_code="AUTORIDADE_DE_DECISAO_AUSENTE",
            title="Autoridade de decisao ausente",
            detail="Nenhum perfil de papel compativel com a emissao humana foi resolvido.",
        )
    if len(matching_roles) > 1:
        raise DomainProblem(
            status_code=status.HTTP_409_CONFLICT,
            reason_code="AUTORIDADE_DE_DECISAO_INDETERMINADA",
            title="Autoridade de decisao indeterminada",
            detail=(
                "Mais de um papel compativel com a emissao humana foi resolvido para este contexto."
            ),
        )

    authority = DecisionAuthorityProfile(
        authority_id=SharedTypedId.new("authority_profile"),
        organization_id=contexto.organization_id,
        principal_reference=UniversalReference(
            target_id=contexto.actor_id,
            organization_id=contexto.organization_id,
            contract_version=1,
        ),
        role_name=matching_roles[0].name,
        purpose=purpose,
        emission_method=DecisionEmissionMethod.HUMAN,
        approvals_required=1,
        is_active=True,
        valid_from=contexto.validated_at,
    )
    TransactionalDecisionAuthorityProfileRepository(connection).save(authority)
    return authority


def _resolve_current_human_emission_material(
    connection: Connection,
    contexto: OrganizationContext,
    proposal: DecisionProposal,
) -> tuple[Evaluation, Policy]:
    governance = TransactionalDecisionGovernanceRepository(connection)
    evaluation_repository = TransactionalEvaluationRepository(connection=connection)
    policy_repository = TransactionalPolicyRepository(connection=connection)

    latest_proposal = governance.latest_proposal_for_evaluation(
        contexto.organization_id,
        proposal.evaluation_id,
        proposal.purpose,
    )
    if latest_proposal is None or latest_proposal.proposal_id != proposal.proposal_id:
        raise DomainProblem(
            status_code=status.HTTP_409_CONFLICT,
            reason_code="PROPOSTA_NAO_CORRENTE",
            title="Proposta nao corrente",
            detail=(
                "A proposta aprovada nao e mais a proposta corrente para esta "
                "evaluation/purpose; uma emissao humana sobre material superado foi bloqueada."
            ),
        )

    evaluation = evaluation_repository.get_by_id(proposal.evaluation_id)
    if evaluation is None or evaluation.organization_id != contexto.organization_id:
        raise DomainProblem(
            status_code=status.HTTP_404_NOT_FOUND,
            reason_code="RECURSO_NAO_ENCONTRADO",
            title="Recurso nao encontrado",
            detail="Evaluation da proposta nao foi encontrada nesta organizacao.",
        )

    current_evaluation = next(
        (
            item
            for item in evaluation_repository.list_by_subject(
                contexto.organization_id,
                evaluation.subject_id,
            )
            if item.purpose == evaluation.purpose
        ),
        None,
    )
    if current_evaluation is None or current_evaluation.evaluation_id != evaluation.evaluation_id:
        raise DomainProblem(
            status_code=status.HTTP_409_CONFLICT,
            reason_code="EVALUATION_NAO_CORRENTE",
            title="Evaluation nao corrente",
            detail=(
                "A proposal referencia uma evaluation superada por material mais recente; "
                "a emissao humana foi bloqueada."
            ),
        )

    policy = policy_repository.get_by_id(evaluation.policy_id)
    if policy is None:
        raise DomainProblem(
            status_code=status.HTTP_404_NOT_FOUND,
            reason_code="RECURSO_NAO_ENCONTRADO",
            title="Recurso nao encontrado",
            detail="Policy da evaluation nao foi encontrada nesta organizacao.",
        )
    current_policy = policy_repository.get_active_at(
        contexto.organization_id,
        policy.code,
        contexto.validated_at,
    )
    if current_policy is None or current_policy.policy_id != policy.policy_id:
        raise DomainProblem(
            status_code=status.HTTP_409_CONFLICT,
            reason_code="POLICY_NAO_CORRENTE",
            title="Policy nao corrente",
            detail=(
                "A policy da evaluation nao e mais a policy corrente para esta purpose; "
                "a emissao humana foi bloqueada."
            ),
        )
    return evaluation, policy


def _required_subjects(matrix: Any) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    required: list[dict[str, str]] = []
    for entry in matrix.entries:
        dependency = entry.dependency
        if dependency is None or dependency.selected_subject_id is not None:
            continue
        key = (dependency.subject_key, entry.market.code)
        if key in seen:
            continue
        seen.add(key)
        required.append(
            {
                "market": entry.market.code,
                "subject_key": dependency.subject_key,
                "subject_label": dependency.subject_label,
            }
        )
    return required


def _market_gaps(matrix: Any) -> list[dict[str, str]]:
    gaps: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for entry in matrix.entries:
        for gap in entry.gaps:
            key = (entry.market.code, gap.code.value)
            if key in seen:
                continue
            seen.add(key)
            gaps.append(
                {
                    "market": entry.market.code,
                    "code": gap.code.value,
                    "message": gap.message,
                }
            )
    return gaps


def _market_entry_summary(entry: dict[str, Any]) -> str:
    status_value = str(entry.get("status"))
    dependency = entry.get("dependency")
    if status_value == "ELEGIVEL":
        if isinstance(dependency, dict) and dependency.get("selected_subject_id") is not None:
            label = str(dependency.get("subject_label", "sujeito"))
            return f"Mercado elegivel com o {label} selecionado."
        return "Mercado elegivel para comercializacao."
    if status_value == "CONDICIONADO":
        if isinstance(dependency, dict) and dependency.get("selected_subject_id") is None:
            label = str(dependency.get("subject_label", "sujeito"))
            return f"Mercado condicionado: selecione o {label} exigido para concluir a analise."
        gaps = entry.get("gaps", [])
        if gaps:
            first_gap = gaps[0]
            if isinstance(first_gap, dict):
                return f"Mercado condicionado: {first_gap.get('message', 'existem pendencias.')}"
        return "Mercado condicionado por pendencias ainda nao resolvidas."
    if status_value == "NAO_ELEGIVEL":
        reasons = entry.get("reasons", [])
        if reasons:
            first_reason = reasons[0]
            if isinstance(first_reason, dict):
                message = first_reason.get("message", "houve nao conformidade.")
                return f"Mercado bloqueado: {message}"
        return "Mercado bloqueado para comercializacao."
    if status_value == "AUSENTE":
        return "Mercado ainda nao pode ser avaliado porque faltam regras governadas publicadas."
    gaps = entry.get("gaps", [])
    if gaps:
        first_gap = gaps[0]
        if isinstance(first_gap, dict):
            message = first_gap.get("message", "faltam elementos para concluir.")
            if first_gap.get("code") == "CARENCIA_POR_MERCADO_AUSENTE":
                return (
                    "Mercado inconclusivo: nao existe prazo de carencia aplicavel "
                    f"declarado para este mercado; {message}"
                )
            return f"Mercado inconclusivo: {message}"
    return "Mercado inconclusivo com o conhecimento atual."


def _lot_market_summary(*, market_status: str, entries: Sequence[dict[str, Any]]) -> str:
    member_count = len(entries)
    if market_status == "ELEGIVEL":
        return (
            f"Todos os {member_count} animais vigentes do lote estao elegiveis para este mercado."
        )

    if market_status == "CONDICIONADO":
        missing_dependency = next(
            (
                entry.get("dependency")
                for entry in entries
                if isinstance(entry.get("dependency"), dict)
                and entry["dependency"].get("selected_subject_id") is None
            ),
            None,
        )
        if isinstance(missing_dependency, dict):
            label = str(missing_dependency.get("subject_label", "sujeito"))
            return (
                "O lote depende da escolha do "
                f"{label} exigido para concluir a analise deste mercado."
            )
        conditioned_count = sum(1 for entry in entries if entry["status"] == "CONDICIONADO")
        return (
            f"O lote permanece condicionado porque {conditioned_count} de "
            f"{member_count} animais ainda possuem pendencias neste mercado."
        )

    if market_status == "NAO_ELEGIVEL":
        blocked_count = sum(1 for entry in entries if entry["status"] == "NAO_ELEGIVEL")
        return (
            f"O lote esta bloqueado para este mercado porque {blocked_count} de "
            f"{member_count} animais aparecem nao elegiveis."
        )

    if market_status == "AUSENTE":
        return "O lote ainda nao pode ser avaliado neste mercado porque faltam regras publicadas."

    indeterminate_count = sum(
        1 for entry in entries if entry["status"] in {"INDETERMINADO", "AUSENTE"}
    )
    if any(
        isinstance(entry.get("dependency"), dict)
        and entry["dependency"].get("selected_subject_id") is None
        and any(
            isinstance(gap, dict) and gap.get("code") == "CARENCIA_POR_MERCADO_AUSENTE"
            for gap in entry.get("gaps", [])
        )
        for entry in entries
        if isinstance(entry, dict)
    ):
        return (
            "O lote continua inconclusivo neste mercado porque nao existe prazo "
            "de carencia aplicavel declarado para todos os animais vigentes."
        )
    return (
        f"O lote continua inconclusivo neste mercado porque {indeterminate_count} de "
        f"{member_count} animais ainda nao possuem base suficiente para conclusao."
    )


def _is_only_missing_withdrawal_basis(entry: dict[str, Any]) -> bool:
    gaps = entry.get("gaps", [])
    if isinstance(gaps, list) and gaps:
        return all(
            isinstance(gap, dict) and gap.get("code") == "CARENCIA_POR_MERCADO_AUSENTE"
            for gap in gaps
        )
    animals = entry.get("animals", [])
    if not isinstance(animals, list) or not animals:
        return False
    return all(
        isinstance(animal, dict)
        and str(animal.get("status")) == "INDETERMINADO"
        and any(
            isinstance(gap, dict) and gap.get("code") == "CARENCIA_POR_MERCADO_AUSENTE"
            for gap in animal.get("gaps", [])
        )
        for animal in animals
    )


def _commercial_projection_status(entry: dict[str, Any]) -> str:
    status_value = str(entry.get("status"))
    dependency = entry.get("dependency")
    if (
        status_value == "INDETERMINADO"
        and isinstance(dependency, dict)
        and dependency.get("selected_subject_id") is None
    ):
        return "CONDICIONADO"
    if status_value == "INDETERMINADO" and _is_only_missing_withdrawal_basis(entry):
        return "ELEGIVEL"
    return status_value


def _project_commercial_explanation(
    *,
    requested_markets: Sequence[str],
    markets: Sequence[dict[str, Any]],
) -> tuple[
    str,
    bool,
    str,
    list[str],
    list[str],
    list[str],
    list[str],
    list[str],
    list[dict[str, Any]],
]:
    projected_markets: list[dict[str, Any]] = []
    eligible_markets: list[str] = []
    blocked_markets: list[str] = []
    conditioned_markets: list[str] = []
    indeterminate_markets: list[str] = []
    missing_markets: list[str] = []
    for entry in markets:
        projected_status = _commercial_projection_status(entry)
        projected_entry = {**entry, "status": projected_status}
        projected_markets.append(projected_entry)
        market_code = str(entry["market"])
        if projected_status == "ELEGIVEL":
            eligible_markets.append(market_code)
        elif projected_status == "NAO_ELEGIVEL":
            blocked_markets.append(market_code)
        elif projected_status == "CONDICIONADO":
            conditioned_markets.append(market_code)
        elif projected_status == "INDETERMINADO":
            indeterminate_markets.append(market_code)
        elif projected_status == "AUSENTE":
            missing_markets.append(market_code)
    commercial_outlook, can_sell, executive_summary = _commercial_outlook(
        requested_markets=requested_markets,
        eligible_markets=eligible_markets,
        blocked_markets=blocked_markets,
        conditioned_markets=conditioned_markets,
        indeterminate_markets=indeterminate_markets,
        missing_markets=missing_markets,
    )
    return (
        commercial_outlook,
        can_sell,
        executive_summary,
        eligible_markets,
        blocked_markets,
        conditioned_markets,
        indeterminate_markets,
        missing_markets,
        projected_markets,
    )


def _market_display_name(market_code: str) -> str:
    display_names = {
        "exportacao-china": "China",
        "exportacao-estados-unidos": "Estados Unidos",
        "exportacao-uniao-europeia": "União Europeia",
    }
    return display_names.get(market_code, market_code)


def _format_market_names(market_codes: Sequence[str]) -> str:
    names = [_market_display_name(code) for code in market_codes]
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} e {names[1]}"
    return f"{', '.join(names[:-1])} e {names[-1]}"


def _first_rule_corrective_action(entry: dict[str, Any]) -> str | None:
    for requirement in entry.get("requirements", []):
        if not isinstance(requirement, dict):
            continue
        rule_version = requirement.get("rule_version")
        if isinstance(rule_version, dict) and rule_version.get("corrective_action"):
            return str(rule_version["corrective_action"])
    return None


def _market_why(entry: dict[str, Any]) -> list[str]:
    if "animals" in entry:
        animals = entry.get("animals", [])
        if not isinstance(animals, list):
            return [str(entry.get("summary", ""))]
        dependency = entry.get("dependency")
        if (
            entry.get("status") == "CONDICIONADO"
            and isinstance(dependency, dict)
            and dependency.get("selected_subject_id") is None
        ):
            label = str(dependency.get("subject_label", "sujeito"))
            return [f"Mercado condicionado: selecione o {label} exigido para concluir a analise."]
        if entry.get("status") == "ELEGIVEL":
            return ["Todos os animais vigentes apareceram elegiveis neste mercado."]
        unique_summaries: list[str] = []
        for animal in animals:
            if not isinstance(animal, dict):
                continue
            if animal.get("status") == "ELEGIVEL" and entry.get("status") != "ELEGIVEL":
                continue
            summary = str(animal.get("summary", "")).strip()
            if summary and summary not in unique_summaries:
                unique_summaries.append(summary)
        if unique_summaries:
            return unique_summaries
        return [str(entry.get("summary", ""))]

    gaps = entry.get("gaps", [])
    if isinstance(gaps, list) and gaps:
        return [
            str(gap.get("message"))
            for gap in gaps
            if isinstance(gap, dict) and str(gap.get("message", "")).strip()
        ]
    reasons = entry.get("reasons", [])
    if isinstance(reasons, list) and reasons:
        return [
            str(reason.get("message"))
            for reason in reasons
            if isinstance(reason, dict) and str(reason.get("message", "")).strip()
        ]
    return [str(entry.get("summary", ""))]


def _affected_animal_ids(entry: dict[str, Any]) -> list[str]:
    """Quais animais do lote respondem pelo status do mercado.

    Quando o bloqueio vem de um sujeito dependente ainda nao escolhido (ex.:
    estabelecimento), todo animal do lote aparece com o mesmo status por
    reflexo da mesma pendencia -- listar cada um deles sugeriria um problema
    individual que nao existe. A pendencia e do mercado, nao do animal.
    """
    dependency = entry.get("dependency")
    if isinstance(dependency, dict) and dependency.get("selected_subject_id") is None:
        return []
    return [
        *[str(animal_id) for animal_id in entry.get("blocked_animal_ids", [])],
        *[str(animal_id) for animal_id in entry.get("conditioned_animal_ids", [])],
        *[str(animal_id) for animal_id in entry.get("indeterminate_animal_ids", [])],
        *[str(animal_id) for animal_id in entry.get("missing_animal_ids", [])],
    ]


def _market_next_action(entry: dict[str, Any]) -> str | None:
    status_value = str(entry.get("status"))
    if status_value == "ELEGIVEL":
        return None

    dependency = entry.get("dependency")
    if isinstance(dependency, dict) and dependency.get("selected_subject_id") is None:
        label = str(dependency.get("subject_label", "sujeito"))
        return f"Selecionar o {label} exigido e repetir a avaliacao deste mercado."

    if status_value == "AUSENTE":
        return "Publicar e adotar as regras governadas deste mercado antes de comercializar."

    corrective_action = _first_rule_corrective_action(entry)
    if corrective_action is not None:
        return corrective_action

    if status_value == "NAO_ELEGIVEL" and "animals" in entry:
        return "Revisar os animais bloqueados antes de negociar o lote neste mercado."

    if status_value in {"CONDICIONADO", "INDETERMINADO"}:
        return "Completar as pendencias deste mercado e reexecutar a analise comercial."

    return None


def _recommended_next_action(
    *,
    conditioned_markets: Sequence[str],
    blocked_markets: Sequence[str],
    missing_markets: Sequence[str],
    indeterminate_markets: Sequence[str],
    required_subjects: Sequence[dict[str, str]],
) -> str | None:
    if required_subjects:
        subject_labels = sorted({str(item["subject_label"]) for item in required_subjects})
        label = subject_labels[0]
        return f"Selecionar e qualificar o {label} exigido para os mercados condicionados."
    if blocked_markets:
        return "Tratar as nao conformidades dos mercados bloqueados antes de comercializar."
    if missing_markets:
        return "Publicar e adotar as regras governadas dos mercados ainda ausentes."
    if indeterminate_markets or conditioned_markets:
        return "Completar as pendencias e reexecutar a analise comercial."
    return "Pode prosseguir com a comercializacao nos mercados elegiveis."


def _commercial_narrative(
    *,
    subject_type: str,
    eligible_markets: Sequence[str],
    blocked_markets: Sequence[str],
    conditioned_markets: Sequence[str],
    indeterminate_markets: Sequence[str],
    missing_markets: Sequence[str],
) -> str:
    subject_label = "O lote" if subject_type == "lot" else "O animal"
    parts: list[str] = []
    if eligible_markets:
        parts.append(
            f"{subject_label} pode ser comercializado para "
            f"{_format_market_names(eligible_markets)}."
        )
    if blocked_markets:
        parts.append(
            f"{subject_label} nao pode ser comercializado para "
            f"{_format_market_names(blocked_markets)}."
        )
    if conditioned_markets:
        parts.append(
            f"{subject_label} ainda depende de acao para "
            f"{_format_market_names(conditioned_markets)}."
        )
    if indeterminate_markets:
        parts.append(
            f"{subject_label} ainda nao possui base suficiente para concluir "
            f"{_format_market_names(indeterminate_markets)}."
        )
    if missing_markets:
        parts.append(
            f"{subject_label} ainda nao pode ser avaliado em "
            f"{_format_market_names(missing_markets)} "
            "porque faltam regras publicadas."
        )
    return " ".join(parts)


def _explicacao_comercial_de_avaliacao(
    *,
    subject_type: str,
    subject_id: str,
    requested_markets: Sequence[str],
    commercial_outlook: str,
    can_sell_to_any_requested_market: bool,
    executive_summary: str,
    eligible_markets: Sequence[str],
    blocked_markets: Sequence[str],
    conditioned_markets: Sequence[str],
    indeterminate_markets: Sequence[str],
    missing_markets: Sequence[str],
    required_subjects: Sequence[dict[str, str]],
    markets: Sequence[dict[str, Any]],
) -> ExplicacaoComercialResponse:
    return ExplicacaoComercialResponse(
        subject_type=subject_type,
        subject_id=subject_id,
        requested_markets=list(requested_markets),
        commercial_outlook=commercial_outlook,
        can_sell_to_any_requested_market=can_sell_to_any_requested_market,
        executive_summary=executive_summary,
        narrative=_commercial_narrative(
            subject_type=subject_type,
            eligible_markets=eligible_markets,
            blocked_markets=blocked_markets,
            conditioned_markets=conditioned_markets,
            indeterminate_markets=indeterminate_markets,
            missing_markets=missing_markets,
        ),
        recommended_next_action=_recommended_next_action(
            conditioned_markets=conditioned_markets,
            blocked_markets=blocked_markets,
            missing_markets=missing_markets,
            indeterminate_markets=indeterminate_markets,
            required_subjects=required_subjects,
        ),
        markets=[
            ExplicacaoMercadoResponse(
                market=str(entry["market"]),
                status=str(entry["status"]),
                summary=str(entry.get("summary", "")),
                why=_market_why(entry),
                next_action=_market_next_action(entry),
                affected_animal_ids=_affected_animal_ids(entry),
            )
            for entry in markets
        ],
    )


def _commercial_outlook(
    *,
    requested_markets: Sequence[str],
    eligible_markets: Sequence[str],
    blocked_markets: Sequence[str],
    conditioned_markets: Sequence[str],
    indeterminate_markets: Sequence[str],
    missing_markets: Sequence[str],
) -> tuple[str, bool, str]:
    can_sell = bool(eligible_markets)
    requested_count = len(requested_markets)
    eligible_count = len(eligible_markets)
    if requested_count > 0 and eligible_count == requested_count:
        return (
            "TOTALMENTE_COMERCIALIZAVEL",
            True,
            "Todos os mercados solicitados estao elegiveis para comercializacao.",
        )
    if can_sell:
        return (
            "PARCIALMENTE_COMERCIALIZAVEL",
            True,
            "Ha ao menos um mercado solicitado elegivel, "
            "mas o conjunto ainda nao esta integralmente liberado.",
        )
    if conditioned_markets:
        return (
            "DEPENDENTE_DE_ACAO",
            False,
            "Nenhum mercado solicitado esta elegivel ainda; "
            "ha pendencias ou selecoes necessarias antes da comercializacao.",
        )
    if indeterminate_markets or missing_markets:
        return (
            "INCONCLUSIVO",
            False,
            "Nenhum mercado solicitado pode ser promovido "
            "para comercializacao com o conhecimento atual.",
        )
    if blocked_markets:
        return (
            "NAO_COMERCIALIZAVEL",
            False,
            "Os mercados solicitados avaliados estao bloqueados para comercializacao.",
        )
    return (
        "INCONCLUSIVO",
        False,
        "A comercializacao ainda nao pode ser concluida para os mercados solicitados.",
    )


def _lot_market_status(statuses: Sequence[str]) -> str:
    if "NAO_ELEGIVEL" in statuses:
        return "NAO_ELEGIVEL"
    if "AUSENTE" in statuses:
        return "AUSENTE"
    if "INDETERMINADO" in statuses:
        return "INDETERMINADO"
    if "CONDICIONADO" in statuses:
        return "CONDICIONADO"
    return "ELEGIVEL"


def _can_anchor_market_material(executed_requirement: Any) -> bool:
    if executed_requirement is None or executed_requirement.execution is None:
        return False
    dependency = getattr(executed_requirement, "dependency", None)
    return dependency is None


def _executar_avaliacao_orientada_a_mercado(
    *,
    connection: Connection,
    organizacao: OrganizationId,
    animal_id: SharedTypedId,
    instante: datetime,
    selected_subjects: dict[str, SharedTypedId],
    profiles: Sequence[MarketProfile],
) -> tuple[Any, Any, Any, Any]:
    animal_repository = _animal_existente_ou_404(connection, animal_id)
    application_repository, evaluations, decisions, fact_provider = _eligibility_components(
        connection,
        animal_repository,
    )
    policy_repository = TransactionalPolicyRepository(connection=connection)
    rule_repository = TransactionalRuleRepository(connection=connection)
    policy, rule = EligibilityPolicyProvider(
        policy_repository=policy_repository,
        rule_repository=rule_repository,
    ).current(organizacao)
    if policy.published_at is not None and instante < policy.published_at:
        instante = policy.published_at

    try:
        matrix = MarketEligibilityService(
            adoption_reader=TransactionalRuleAdoptionRepository(connection),
            rule_reader=rule_repository,
            policy_reader=policy_repository,
            fact_provider=fact_provider,
            evaluation_repository=evaluations,
            decision_repository=decisions,
            authority_profile_repository=TransactionalDecisionAuthorityProfileRepository(
                connection
            ),
            governance_repository=TransactionalDecisionGovernanceRepository(connection),
            profiles=profiles,
        ).evaluate(
            organization_id=organizacao,
            subject_id=animal_id,
            at_time=instante,
            selected_subjects=selected_subjects,
        )
    except HumanReviewRequired as exc:
        raise _human_review_problem(exc) from exc

    executed_requirement = matrix.first_executed_requirement()
    if not _can_anchor_market_material(executed_requirement):
        try:
            evaluation, decision = PharmacologicalEligibilityService(
                fact_provider=fact_provider,
                policy=policy,
                rule=rule,
                evaluation_repository=evaluations,
                decision_repository=decisions,
                authority_profile_repository=TransactionalDecisionAuthorityProfileRepository(
                    connection
                ),
                governance_repository=TransactionalDecisionGovernanceRepository(connection),
            ).evaluate_animal(organizacao, animal_id, instante)
        except HumanReviewRequired as exc:
            raise _human_review_problem(exc) from exc
    else:
        assert executed_requirement is not None and executed_requirement.execution is not None
        persisted_evaluation = evaluations.get_by_id(
            SharedTypedId(
                entity_type="evaluation",
                value=UUID(executed_requirement.execution.evaluation_id),
            )
        )
        persisted_decision = decisions.get_by_id(
            SharedTypedId(
                entity_type="decision",
                value=UUID(executed_requirement.execution.decision_id),
            )
        )
        if persisted_evaluation is None or persisted_decision is None:
            raise RuntimeError("A matriz registrou uma avaliacao por mercado sem persistencia.")
        if persisted_evaluation.subject_id != animal_id:
            try:
                evaluation, decision = PharmacologicalEligibilityService(
                    fact_provider=fact_provider,
                    policy=policy,
                    rule=rule,
                    evaluation_repository=evaluations,
                    decision_repository=decisions,
                    authority_profile_repository=TransactionalDecisionAuthorityProfileRepository(
                        connection
                    ),
                    governance_repository=TransactionalDecisionGovernanceRepository(connection),
                ).evaluate_animal(organizacao, animal_id, instante)
            except HumanReviewRequired as exc:
                raise _human_review_problem(exc) from exc
        else:
            evaluation = persisted_evaluation
            decision = persisted_decision
            if executed_requirement.governed_rule is None:
                raise RuntimeError("A matriz executou requisito sem regra governada associada.")
            persisted_rule = rule_repository.get_by_id(
                executed_requirement.governed_rule.rule_version_id
            )
            if persisted_rule is None:
                raise RuntimeError("A matriz executou requisito com regra publicada ausente.")
            persisted_policy = policy_repository.get_by_id(persisted_rule.policy_id)
            if persisted_policy is None:
                raise RuntimeError("A matriz executou requisito com policy ausente.")
            policy = persisted_policy
            rule = persisted_rule

    dossier = LivestockDossierTemplate(
        timeline_service=_timeline_service(connection),
        application_repository=application_repository,
        evidence_lookup=TransactionalEvidenceRepository(connection=connection),
        dossier_service=DossierService(
            repository=TransactionalDossierRepository(connection=connection)
        ),
    ).build(decision=decision, evaluation=evaluation, policy=policy, rules=[rule])
    TransactionalDossierRepository(connection=connection).save(dossier)
    return evaluation, decision, dossier, matrix


@router.post(
    "/animals/{animal_id}/eligibility",
    response_model=ElegibilidadeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Executar a elegibilidade farmacológica",
    description=(
        "Coleta os fatos, avalia a política vigente, emite a decisão e materializa "
        "o dossiê. **Escreve**: produz registros permanentes, e por isso é POST."
    ),
    responses=RESPOSTAS_PADRAO,
)
def executar_elegibilidade(
    animal_id: str,
    contexto: Annotated[OrganizationContext, Depends(require_permission(ELIGIBILITY_EXECUTAR))],
    connection: ConnectionDependency,
) -> ElegibilidadeResponse:
    alvo = typed_id_or_problem(animal_id, entity_type="animal", campo="animal_id")
    organizacao = contexto.organization_id

    animal_repository = TransactionalAnimalRepository(connection=connection)
    if animal_repository.get_by_id(alvo) is None:
        raise DomainProblem(
            status_code=status.HTTP_404_NOT_FOUND,
            reason_code="RECURSO_NAO_ENCONTRADO",
            title="Recurso não encontrado",
            detail="Animal não encontrado nesta organização.",
        )

    application_repository, evaluations, decisions, fact_provider = _eligibility_components(
        connection,
        animal_repository,
    )
    # A política e a regra são lidas da versão vigente, e gravadas na primeira
    # vez. Decisão só é reproduzível se a norma sob a qual foi tomada existir como
    # registro — e `evaluations` tem chave estrangeira para `policies`.
    policy, rule = EligibilityPolicyProvider(
        policy_repository=TransactionalPolicyRepository(connection=connection),
        rule_repository=TransactionalRuleRepository(connection=connection),
    ).current(organizacao)
    governed_rule = _governed_rule_reference(connection, organizacao)

    try:
        evaluation, decision = PharmacologicalEligibilityService(
            fact_provider=fact_provider,
            policy=policy,
            rule=rule,
            evaluation_repository=evaluations,
            decision_repository=decisions,
            authority_profile_repository=TransactionalDecisionAuthorityProfileRepository(
                connection
            ),
            governance_repository=TransactionalDecisionGovernanceRepository(connection),
        ).evaluate_animal(organizacao, alvo, datetime.now(UTC))
    except HumanReviewRequired as exc:
        raise _human_review_problem(exc) from exc

    dossier = LivestockDossierTemplate(
        timeline_service=_timeline_service(connection),
        application_repository=application_repository,
        evidence_lookup=TransactionalEvidenceRepository(connection=connection),
        dossier_service=DossierService(
            repository=TransactionalDossierRepository(connection=connection)
        ),
    ).build(
        decision=decision,
        evaluation=evaluation,
        policy=policy,
        rules=[rule],
        governed_rule=governed_rule,
    )
    TransactionalDossierRepository(connection=connection).save(dossier)

    return ElegibilidadeResponse(
        animal_id=str(alvo.value),
        result=decision.result.value,
        outcome=evaluation.outcome.value,
        evaluation_id=str(evaluation.evaluation_id.value),
        knowledge_cutoff=evaluation.fact_snapshot.effective_knowledge_cutoff().isoformat(),
        knowledge_limitations=list(evaluation.fact_snapshot.knowledge_limitations),
        decision_id=str(decision.decision_id.value),
        dossier_id=str(dossier.dossier_id.value),
        reasons=[razao.message for razao in decision.reasons],
        governed_rule=None if governed_rule is None else governed_rule.to_dict(),
    )


@router.get(
    "/decision-proposals/{proposal_id}",
    response_model=DecisionProposalResponse,
    summary="Consultar uma proposta formal de decisao",
    description=(
        "Recupera a proposta formal preservada quando a emissao automatica foi "
        "recusada e informa se ela ainda e a proposta corrente para a mesma evaluation."
    ),
    responses=RESPOSTAS_PADRAO,
)
def obter_proposta_de_decisao(
    proposal_id: str,
    contexto: Annotated[OrganizationContext, Depends(require_permission(DECISION_REVIEW_EXECUTE))],
    connection: ConnectionDependency,
) -> DecisionProposalResponse:
    alvo = typed_id_or_problem(proposal_id, entity_type="decision_proposal", campo="proposal_id")
    governance = TransactionalDecisionGovernanceRepository(connection)
    proposal = governance.get_proposal(alvo)
    if proposal is None or proposal.organization_id != contexto.organization_id:
        raise DomainProblem(
            status_code=status.HTTP_404_NOT_FOUND,
            reason_code="RECURSO_NAO_ENCONTRADO",
            title="Recurso nao encontrado",
            detail="Proposal nao encontrada nesta organizacao.",
        )
    latest = governance.latest_proposal_for_evaluation(
        contexto.organization_id,
        proposal.evaluation_id,
        proposal.purpose,
    )
    review_count = len(governance.list_reviews_by_proposal(proposal.proposal_id))
    return _proposal_response(
        proposal,
        review_count=review_count,
        current_proposal=latest is not None and latest.proposal_id == proposal.proposal_id,
    )


@router.post(
    "/decision-proposals/{proposal_id}/reviews",
    response_model=DecisionReviewExecutionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Executar a revisao humana oficial de uma proposta",
    description=(
        "Registra a conclusao de revisao humana e, quando a proposta continua "
        "corrente e ha aprovacoes suficientes, emite a Decision oficial com Dossier."
    ),
    responses=RESPOSTAS_PADRAO,
)
def revisar_proposta_de_decisao(
    proposal_id: str,
    corpo: DecisionReviewRequest,
    contexto: Annotated[OrganizationContext, Depends(require_permission(DECISION_REVIEW_EXECUTE))],
    connection: ConnectionDependency,
) -> DecisionReviewExecutionResponse:
    alvo = typed_id_or_problem(proposal_id, entity_type="decision_proposal", campo="proposal_id")
    governance = TransactionalDecisionGovernanceRepository(connection)
    proposal = governance.get_proposal(alvo)
    if proposal is None or proposal.organization_id != contexto.organization_id:
        raise DomainProblem(
            status_code=status.HTTP_404_NOT_FOUND,
            reason_code="RECURSO_NAO_ENCONTRADO",
            title="Recurso nao encontrado",
            detail="Proposal nao encontrada nesta organizacao.",
        )

    authority = _resolve_decision_review_authority(
        connection,
        contexto,
        purpose=proposal.purpose,
    )
    governance_service = DecisionGovernanceService(repository=governance)
    review = governance_service.record_review(
        proposal=proposal,
        reviewer_reference=UniversalReference(
            target_id=contexto.actor_id,
            organization_id=contexto.organization_id,
            contract_version=1,
        ),
        reviewer_authority=authority,
        conclusion=corpo.conclusion,
        reasoning=corpo.reasoning,
    )

    if corpo.conclusion is not ReviewConclusion.APROVA:
        return DecisionReviewExecutionResponse(
            proposal_id=str(proposal.proposal_id.value),
            review_id=str(review.review_id.value),
            workflow_status="REVIEW_RECORDED",
        )

    evaluation, policy = _resolve_current_human_emission_material(connection, contexto, proposal)
    reviews = governance.list_reviews_by_proposal(proposal.proposal_id)
    approvals = [item for item in reviews if item.conclusion is ReviewConclusion.APROVA]
    if len(approvals) < max(1, authority.approvals_required):
        return DecisionReviewExecutionResponse(
            proposal_id=str(proposal.proposal_id.value),
            review_id=str(review.review_id.value),
            workflow_status="AGUARDANDO_APROVACOES",
        )

    decision = governance_service.emit_after_approvals(
        evaluation=evaluation,
        proposal=proposal,
        reviews=approvals,
        authority_profile=authority,
    )
    TransactionalDecisionRepository(connection).save(decision)

    rule_repository = TransactionalRuleRepository(connection=connection)
    rules = rule_repository.list_by_policy(contexto.organization_id, policy.policy_id)
    if not rules:
        raise RuntimeError("A policy corrente da proposta nao possui rules persistidas.")

    dossier = LivestockDossierTemplate(
        timeline_service=_timeline_service(connection),
        application_repository=TransactionalTreatmentApplicationRepository(connection=connection),
        evidence_lookup=TransactionalEvidenceRepository(connection=connection),
        dossier_service=DossierService(
            repository=TransactionalDossierRepository(connection=connection)
        ),
    ).build(
        decision=decision,
        evaluation=evaluation,
        policy=policy,
        rules=rules,
        governed_rule=_governed_rule_reference(connection, contexto.organization_id),
        proposal=proposal,
        reviews=reviews,
    )
    TransactionalDossierRepository(connection=connection).save(dossier)

    return DecisionReviewExecutionResponse(
        proposal_id=str(proposal.proposal_id.value),
        review_id=str(review.review_id.value),
        workflow_status="DECISION_EMITTED",
        decision_id=str(decision.decision_id.value),
        dossier_id=str(dossier.dossier_id.value),
    )


class ElegibilidadeLoteResponse(BaseModel):
    lot_id: str
    result: str
    outcome: str
    evaluation_id: str
    knowledge_cutoff: str
    knowledge_limitations: list[str]
    decision_id: str
    reasons: list[str]


@router.post(
    "/lots/{lot_id}/eligibility",
    response_model=ElegibilidadeLoteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Executar a elegibilidade farmacológica do lote",
    description=(
        "Bloqueia o lote inteiro (`rule-carencia-lote`) se qualquer animal "
        "membro estiver em período de carência. Escreve Evaluation/Decision "
        "permanentes, como a elegibilidade por animal. "
        "**Sem dossiê**: `LivestockDossierTemplate` hoje só monta documento para "
        "sujeito do tipo animal; o dossiê de lote fica para quando essa "
        "extensão for decidida à parte."
    ),
    responses=RESPOSTAS_PADRAO,
)
def executar_elegibilidade_lote(
    lot_id: str,
    contexto: Annotated[OrganizationContext, Depends(require_permission(ELIGIBILITY_EXECUTAR))],
    connection: ConnectionDependency,
) -> ElegibilidadeLoteResponse:
    alvo = typed_id_or_problem(lot_id, entity_type="livestock_lot", campo="lot_id")
    organizacao = contexto.organization_id

    lot_repository = TransactionalLivestockLotRepository(connection=connection)
    if lot_repository.get_by_id(alvo) is None:
        raise DomainProblem(
            status_code=status.HTTP_404_NOT_FOUND,
            reason_code="RECURSO_NAO_ENCONTRADO",
            title="Recurso não encontrado",
            detail="Lote não encontrado nesta organização.",
        )

    animal_repository = TransactionalAnimalRepository(connection=connection)
    _application_repository, evaluations, decisions, fact_provider = _eligibility_components(
        connection,
        animal_repository,
    )
    policy_provider = EligibilityPolicyProvider(
        policy_repository=TransactionalPolicyRepository(connection=connection),
        rule_repository=TransactionalRuleRepository(connection=connection),
    )
    policy, animal_rule = policy_provider.current(organizacao)
    lot_rule = policy_provider.current_lot_rule(organizacao, policy)

    try:
        evaluation, decision = PharmacologicalEligibilityService(
            fact_provider=fact_provider,
            policy=policy,
            # `rule` não é usado por evaluate_lot (que consulta lot_rule), mas o
            # campo é obrigatório no serviço; a regra de animal já está em mãos.
            rule=animal_rule,
            evaluation_repository=evaluations,
            decision_repository=decisions,
            authority_profile_repository=TransactionalDecisionAuthorityProfileRepository(
                connection
            ),
            governance_repository=TransactionalDecisionGovernanceRepository(connection),
            lot_rule=lot_rule,
        ).evaluate_lot(organizacao, alvo, datetime.now(UTC))
    except HumanReviewRequired as exc:
        raise _human_review_problem(exc) from exc

    return ElegibilidadeLoteResponse(
        lot_id=str(alvo.value),
        result=decision.result.value,
        outcome=evaluation.outcome.value,
        evaluation_id=str(evaluation.evaluation_id.value),
        knowledge_cutoff=evaluation.fact_snapshot.effective_knowledge_cutoff().isoformat(),
        knowledge_limitations=list(evaluation.fact_snapshot.knowledge_limitations),
        decision_id=str(decision.decision_id.value),
        reasons=[razao.message for razao in decision.reasons],
    )


@router.post(
    "/animals/{animal_id}/eligibility/market-matrix",
    response_model=MatrizMercadoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Executar matriz de elegibilidade por mercado",
    description=(
        "Executa a elegibilidade farmacologica base e compara o resultado com as "
        "regras governadas adotadas para os mercados iniciais."
    ),
    responses=RESPOSTAS_PADRAO,
)
def executar_matriz_de_mercado(
    animal_id: str,
    corpo: MatrizMercadoRequest,
    contexto: Annotated[OrganizationContext, Depends(require_permission(ELIGIBILITY_EXECUTAR))],
    connection: ConnectionDependency,
) -> MatrizMercadoResponse:
    alvo = typed_id_or_problem(animal_id, entity_type="animal", campo="animal_id")
    organizacao = contexto.organization_id
    instante = datetime.now(UTC)
    selected_subjects = (
        {}
        if corpo.slaughterhouse_counterparty_id is None
        else {
            "slaughterhouse": typed_id_or_problem(
                corpo.slaughterhouse_counterparty_id,
                entity_type="external_counterparty",
                campo="slaughterhouse_counterparty_id",
            )
        }
    )

    animal_repository = TransactionalAnimalRepository(connection=connection)
    if animal_repository.get_by_id(alvo) is None:
        raise DomainProblem(
            status_code=status.HTTP_404_NOT_FOUND,
            reason_code="RECURSO_NAO_ENCONTRADO",
            title="Recurso não encontrado",
            detail="Animal não encontrado nesta organização.",
        )

    application_repository, evaluations, decisions, fact_provider = _eligibility_components(
        connection,
        animal_repository,
    )
    policy, rule = EligibilityPolicyProvider(
        policy_repository=TransactionalPolicyRepository(connection=connection),
        rule_repository=TransactionalRuleRepository(connection=connection),
    ).current(organizacao)
    if policy.published_at is not None and instante < policy.published_at:
        instante = policy.published_at

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
            profiles=DEFAULT_MARKET_PROFILES,
        ).evaluate(
            organization_id=organizacao,
            subject_id=alvo,
            at_time=instante,
            selected_subjects=selected_subjects,
        )
    except HumanReviewRequired as exc:
        raise _human_review_problem(exc) from exc

    executed_requirement = matrix.first_executed_requirement()
    if not _can_anchor_market_material(executed_requirement):
        evaluation, decision = PharmacologicalEligibilityService(
            fact_provider=fact_provider,
            policy=policy,
            rule=rule,
            evaluation_repository=evaluations,
            decision_repository=decisions,
            authority_profile_repository=TransactionalDecisionAuthorityProfileRepository(
                connection
            ),
            governance_repository=TransactionalDecisionGovernanceRepository(connection),
        ).evaluate_animal(organizacao, alvo, instante)
    else:
        assert executed_requirement is not None and executed_requirement.execution is not None
        persisted_evaluation = evaluations.get_by_id(
            SharedTypedId(
                entity_type="evaluation",
                value=UUID(executed_requirement.execution.evaluation_id),
            )
        )
        persisted_decision = decisions.get_by_id(
            SharedTypedId(
                entity_type="decision",
                value=UUID(executed_requirement.execution.decision_id),
            )
        )
        if persisted_evaluation is None or persisted_decision is None:
            raise RuntimeError("A matriz registrou uma avaliacao por mercado sem persistencia.")
        if persisted_evaluation.subject_id != alvo:
            evaluation, decision = PharmacologicalEligibilityService(
                fact_provider=fact_provider,
                policy=policy,
                rule=rule,
                evaluation_repository=evaluations,
                decision_repository=decisions,
                authority_profile_repository=TransactionalDecisionAuthorityProfileRepository(
                    connection
                ),
                governance_repository=TransactionalDecisionGovernanceRepository(connection),
            ).evaluate_animal(organizacao, alvo, instante)
        else:
            evaluation = persisted_evaluation
            decision = persisted_decision
            if executed_requirement.governed_rule is None:
                raise RuntimeError("A matriz executou requisito sem regra governada associada.")
            persisted_rule = TransactionalRuleRepository(connection=connection).get_by_id(
                executed_requirement.governed_rule.rule_version_id
            )
            if persisted_rule is None:
                raise RuntimeError("A matriz executou requisito com regra publicada ausente.")
            persisted_policy = TransactionalPolicyRepository(connection=connection).get_by_id(
                persisted_rule.policy_id
            )
            if persisted_policy is None:
                raise RuntimeError("A matriz executou requisito com policy ausente.")
            policy = persisted_policy
            rule = persisted_rule

    dossier = LivestockDossierTemplate(
        timeline_service=_timeline_service(connection),
        application_repository=application_repository,
        evidence_lookup=TransactionalEvidenceRepository(connection=connection),
        dossier_service=DossierService(
            repository=TransactionalDossierRepository(connection=connection)
        ),
    ).build(decision=decision, evaluation=evaluation, policy=policy, rules=[rule])
    TransactionalDossierRepository(connection=connection).save(dossier)

    return MatrizMercadoResponse(
        animal_id=str(alvo.value),
        evaluation_id=str(evaluation.evaluation_id.value),
        knowledge_cutoff=evaluation.fact_snapshot.effective_knowledge_cutoff().isoformat(),
        knowledge_limitations=list(evaluation.fact_snapshot.knowledge_limitations),
        decision_id=str(decision.decision_id.value),
        dossier_id=str(dossier.dossier_id.value),
        markets=matrix.to_dict(),
    )


@router.post(
    "/market-eligibility/evaluations",
    response_model=AvaliacaoMercadosResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Executar elegibilidade orientada a mercados",
    description=(
        "Recebe o animal e os mercados desejados, resolve internamente os perfis "
        "publicados para cada mercado e executa a comparacao comercial sem exigir "
        "que o cliente escolha rules ou policies."
    ),
    responses=RESPOSTAS_PADRAO,
)
def executar_avaliacao_orientada_a_mercados(
    corpo: AvaliacaoMercadosRequest,
    contexto: Annotated[OrganizationContext, Depends(require_permission(ELIGIBILITY_EXECUTAR))],
    connection: ConnectionDependency,
) -> AvaliacaoMercadosResponse:
    alvo = typed_id_or_problem(corpo.animal_id, entity_type="animal", campo="animal_id")
    organizacao = contexto.organization_id
    instante = datetime.now(UTC)
    selected_subjects = _selected_subjects_from_market_request(corpo.slaughterhouse_counterparty_id)
    profiles = _market_profiles_for_codes(corpo.markets)
    evaluation, decision, dossier, matrix = _executar_avaliacao_orientada_a_mercado(
        connection=connection,
        organizacao=organizacao,
        animal_id=alvo,
        instante=instante,
        selected_subjects=selected_subjects,
        profiles=profiles,
    )
    (
        eligible_markets,
        blocked_markets,
        conditioned_markets,
        indeterminate_markets,
        missing_markets,
    ) = _market_codes_by_status(matrix)
    commercial_outlook, can_sell_to_any_requested_market, executive_summary = _commercial_outlook(
        requested_markets=[profile.market.code for profile in profiles],
        eligible_markets=eligible_markets,
        blocked_markets=blocked_markets,
        conditioned_markets=conditioned_markets,
        indeterminate_markets=indeterminate_markets,
        missing_markets=missing_markets,
    )

    return AvaliacaoMercadosResponse(
        animal_id=str(alvo.value),
        requested_markets=[profile.market.code for profile in profiles],
        commercial_outlook=commercial_outlook,
        can_sell_to_any_requested_market=can_sell_to_any_requested_market,
        executive_summary=executive_summary,
        eligible_markets=eligible_markets,
        blocked_markets=blocked_markets,
        conditioned_markets=conditioned_markets,
        indeterminate_markets=indeterminate_markets,
        missing_markets=missing_markets,
        required_subjects=_required_subjects(matrix),
        market_gaps=_market_gaps(matrix),
        evaluation_id=str(evaluation.evaluation_id.value),
        knowledge_cutoff=evaluation.fact_snapshot.effective_knowledge_cutoff().isoformat(),
        knowledge_limitations=list(evaluation.fact_snapshot.knowledge_limitations),
        decision_id=str(decision.decision_id.value),
        dossier_id=str(dossier.dossier_id.value),
        markets=[
            {
                **entry,
                "summary": _market_entry_summary(entry),
            }
            for entry in matrix.to_dict()
        ],
    )


@router.get(
    "/market-eligibility/profiles",
    response_model=list[PerfilMercadoResponse],
    summary="Listar mercados suportados e seus requisitos publicados",
    description=(
        "Publica os mercados suportados pela API e os requisitos esperados para "
        "cada um, incluindo dependencias adicionais como estabelecimento "
        "escolhido quando aplicavel."
    ),
    responses=RESPOSTAS_PADRAO,
)
def listar_perfis_de_mercado(
    contexto: Annotated[OrganizationContext, Depends(require_permission(ELIGIBILITY_EXECUTAR))],
) -> list[PerfilMercadoResponse]:
    _ = contexto
    return [_perfil_mercado_response(profile) for profile in DEFAULT_MARKET_PROFILES]


@router.post(
    "/market-eligibility/commercial-explanations",
    response_model=ExplicacaoComercialResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Gerar explicacao comercial executiva por mercado",
    description=(
        "Executa a analise comercial orientada a mercado e devolve uma leitura "
        "executiva, pronta para dizer para quais mercados o animal ou o lote "
        "podem seguir, quais estao bloqueados e qual a proxima acao recomendada."
    ),
    responses=RESPOSTAS_PADRAO,
)
def gerar_explicacao_comercial(
    corpo: ExplicacaoComercialRequest,
    contexto: Annotated[OrganizationContext, Depends(require_permission(ELIGIBILITY_EXECUTAR))],
    connection: ConnectionDependency,
) -> ExplicacaoComercialResponse:
    if (corpo.animal_id is None) == (corpo.lot_id is None):
        raise DomainProblem(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            reason_code="ENTRADA_INVALIDA",
            title="Entrada invalida",
            detail="Informe exatamente um sujeito: animal_id ou lot_id.",
        )

    if corpo.animal_id is not None:
        avaliacao = executar_avaliacao_orientada_a_mercados(
            AvaliacaoMercadosRequest(
                animal_id=corpo.animal_id,
                markets=corpo.markets,
                slaughterhouse_counterparty_id=corpo.slaughterhouse_counterparty_id,
            ),
            contexto=contexto,
            connection=connection,
        )
        return _explicacao_comercial_de_avaliacao(
            subject_type="animal",
            subject_id=avaliacao.animal_id,
            requested_markets=avaliacao.requested_markets,
            commercial_outlook=avaliacao.commercial_outlook,
            can_sell_to_any_requested_market=avaliacao.can_sell_to_any_requested_market,
            executive_summary=avaliacao.executive_summary,
            eligible_markets=avaliacao.eligible_markets,
            blocked_markets=avaliacao.blocked_markets,
            conditioned_markets=avaliacao.conditioned_markets,
            indeterminate_markets=avaliacao.indeterminate_markets,
            missing_markets=avaliacao.missing_markets,
            required_subjects=avaliacao.required_subjects,
            markets=avaliacao.markets,
        )

    avaliacao_lote = executar_avaliacao_orientada_a_mercados_para_lote(
        AvaliacaoMercadosLoteRequest(
            lot_id=corpo.lot_id or "",
            markets=corpo.markets,
            slaughterhouse_counterparty_id=corpo.slaughterhouse_counterparty_id,
        ),
        contexto=contexto,
        connection=connection,
    )
    (
        commercial_outlook,
        can_sell_to_any_requested_market,
        executive_summary,
        eligible_markets,
        blocked_markets,
        conditioned_markets,
        indeterminate_markets,
        missing_markets,
        markets,
    ) = _project_commercial_explanation(
        requested_markets=avaliacao_lote.requested_markets,
        markets=avaliacao_lote.markets,
    )
    return _explicacao_comercial_de_avaliacao(
        subject_type="lot",
        subject_id=avaliacao_lote.lot_id,
        requested_markets=avaliacao_lote.requested_markets,
        commercial_outlook=commercial_outlook,
        can_sell_to_any_requested_market=can_sell_to_any_requested_market,
        executive_summary=executive_summary,
        eligible_markets=eligible_markets,
        blocked_markets=blocked_markets,
        conditioned_markets=conditioned_markets,
        indeterminate_markets=indeterminate_markets,
        missing_markets=missing_markets,
        required_subjects=avaliacao_lote.required_subjects,
        markets=markets,
    )


@router.post(
    "/market-eligibility/lots/evaluations",
    response_model=AvaliacaoMercadosLoteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Executar elegibilidade orientada a mercados para lote",
    description=(
        "Avalia comercialmente o lote a partir dos animais membros vigentes. "
        "O lote so aparece elegivel para um mercado quando todos os membros "
        "vigentes tambem aparecem elegiveis para esse mercado."
    ),
    responses=RESPOSTAS_PADRAO,
)
def executar_avaliacao_orientada_a_mercados_para_lote(
    corpo: AvaliacaoMercadosLoteRequest,
    contexto: Annotated[OrganizationContext, Depends(require_permission(ELIGIBILITY_EXECUTAR))],
    connection: ConnectionDependency,
) -> AvaliacaoMercadosLoteResponse:
    lot_id = typed_id_or_problem(corpo.lot_id, entity_type="livestock_lot", campo="lot_id")
    organizacao = contexto.organization_id
    instante = datetime.now(UTC)
    lote = TransactionalLivestockLotRepository(connection=connection).get_by_id(lot_id)
    if lote is None or lote.organization_id != organizacao:
        raise DomainProblem(
            status_code=status.HTTP_404_NOT_FOUND,
            reason_code="RECURSO_NAO_ENCONTRADO",
            title="Recurso nao encontrado",
            detail="Lote nao encontrado nesta organizacao.",
        )

    memberships = TransactionalLotMembershipRepository(
        connection=connection
    ).get_memberships_for_lot(
        lot_id,
        at_time=instante,
    )
    if not memberships:
        raise DomainProblem(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            reason_code="ENTRADA_INVALIDA",
            title="Entrada invalida",
            detail="O lote nao possui membros vigentes para avaliacao comercial.",
        )

    selected_subjects = _selected_subjects_from_market_request(corpo.slaughterhouse_counterparty_id)
    profiles = _market_profiles_for_codes(corpo.markets)
    per_animal_results: list[tuple[str, Any]] = []
    for membership in memberships:
        _evaluation, _decision, _dossier, matrix = _executar_avaliacao_orientada_a_mercado(
            connection=connection,
            organizacao=organizacao,
            animal_id=membership.animal_id,
            instante=instante,
            selected_subjects=selected_subjects,
            profiles=profiles,
        )
        per_animal_results.append((str(membership.animal_id.value), matrix))

    markets: list[dict[str, Any]] = []
    eligible_markets: list[str] = []
    blocked_markets: list[str] = []
    conditioned_markets: list[str] = []
    indeterminate_markets: list[str] = []
    missing_markets: list[str] = []
    required_subjects: list[dict[str, str]] = []
    market_gaps: list[dict[str, str]] = []
    seen_required: set[tuple[str, str]] = set()
    seen_gap: set[tuple[str, str]] = set()

    for profile in profiles:
        market_code = profile.market.code
        entries = []
        statuses: list[str] = []
        for animal_id, matrix in per_animal_results:
            entry = next(item for item in matrix.to_dict() if item["market"] == market_code)
            entry_with_animal = {
                "animal_id": animal_id,
                **entry,
                "summary": _market_entry_summary(entry),
            }
            entries.append(entry_with_animal)
            statuses.append(str(entry["status"]))
        market_status = _lot_market_status(statuses)
        if market_status == "ELEGIVEL":
            eligible_markets.append(market_code)
        elif market_status == "NAO_ELEGIVEL":
            blocked_markets.append(market_code)
        elif market_status == "CONDICIONADO":
            conditioned_markets.append(market_code)
        elif market_status == "INDETERMINADO":
            indeterminate_markets.append(market_code)
        elif market_status == "AUSENTE":
            missing_markets.append(market_code)

        for entry in entries:
            dependency = entry.get("dependency")
            if isinstance(dependency, dict) and dependency.get("selected_subject_id") is None:
                key = (market_code, str(dependency.get("subject_key")))
                if key not in seen_required:
                    seen_required.add(key)
                    required_subjects.append(
                        {
                            "market": market_code,
                            "subject_key": str(dependency.get("subject_key")),
                            "subject_label": str(dependency.get("subject_label")),
                        }
                    )
            for gap in entry.get("gaps", []):
                if not isinstance(gap, dict):
                    continue
                code = str(gap.get("code"))
                key = (market_code, code)
                if key in seen_gap:
                    continue
                seen_gap.add(key)
                market_gaps.append(
                    {
                        "market": market_code,
                        "code": code,
                        "message": str(gap.get("message")),
                    }
                )

        markets.append(
            {
                "market": market_code,
                "status": market_status,
                "summary": _lot_market_summary(
                    market_status=market_status,
                    entries=entries,
                ),
                "dependency": next(
                    (
                        entry["dependency"]
                        for entry in entries
                        if isinstance(entry.get("dependency"), dict)
                    ),
                    None,
                ),
                "eligible_animal_ids": [
                    entry["animal_id"] for entry in entries if entry["status"] == "ELEGIVEL"
                ],
                "blocked_animal_ids": [
                    entry["animal_id"] for entry in entries if entry["status"] == "NAO_ELEGIVEL"
                ],
                "conditioned_animal_ids": [
                    entry["animal_id"] for entry in entries if entry["status"] == "CONDICIONADO"
                ],
                "indeterminate_animal_ids": [
                    entry["animal_id"] for entry in entries if entry["status"] == "INDETERMINADO"
                ],
                "missing_animal_ids": [
                    entry["animal_id"] for entry in entries if entry["status"] == "AUSENTE"
                ],
                "animals": entries,
            }
        )

    (
        commercial_outlook,
        can_sell_to_any_requested_market,
        executive_summary,
    ) = _commercial_outlook(
        requested_markets=[profile.market.code for profile in profiles],
        eligible_markets=eligible_markets,
        blocked_markets=blocked_markets,
        conditioned_markets=conditioned_markets,
        indeterminate_markets=indeterminate_markets,
        missing_markets=missing_markets,
    )

    return AvaliacaoMercadosLoteResponse(
        lot_id=str(lot_id.value),
        member_count=len(memberships),
        requested_markets=[profile.market.code for profile in profiles],
        commercial_outlook=commercial_outlook,
        can_sell_to_any_requested_market=can_sell_to_any_requested_market,
        executive_summary=executive_summary,
        eligible_markets=eligible_markets,
        blocked_markets=blocked_markets,
        conditioned_markets=conditioned_markets,
        indeterminate_markets=indeterminate_markets,
        missing_markets=missing_markets,
        required_subjects=required_subjects,
        market_gaps=market_gaps,
        markets=markets,
    )


@router.get(
    "/animals/{animal_id}/timeline",
    response_model=LinhaDoTempoResponse,
    summary="Consultar a linha do tempo de um animal",
    description=(
        "Reconstrói a história a partir dos registros imutáveis. `known_until` "
        "reconstrói o que o Titan **sabia** naquele instante, e não o que "
        "aconteceu até ele."
    ),
    responses=RESPOSTAS_PADRAO,
)
def consultar_linha_do_tempo(
    animal_id: str,
    contexto: Annotated[OrganizationContext, Depends(require_permission(TIMELINE_LER))],
    connection: ConnectionDependency,
    occurred_until: Annotated[datetime | None, Query()] = None,
    known_until: Annotated[datetime | None, Query()] = None,
) -> LinhaDoTempoResponse:
    alvo = typed_id_or_problem(animal_id, entity_type="animal", campo="animal_id")

    try:
        corte = (
            TimelineCutoff(occurred_until=occurred_until, known_until=known_until)
            if (occurred_until or known_until)
            else None
        )
    except ValueError as error:
        # Instante sem timezone nunca é tratado como UTC em silêncio.
        raise DomainProblem(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            reason_code="ENTRADA_INVALIDA",
            title="Entrada inválida",
            detail=str(error),
        ) from error

    entradas = _timeline_service(connection).animal_timeline(contexto.organization_id, alvo, corte)
    return LinhaDoTempoResponse(
        animal_id=str(alvo.value),
        known_until=known_until.isoformat() if known_until else None,
        entry_count=len(entradas),
        entries=_entradas_para_json(entradas),
    )


@router.get(
    "/traceable-items/{item_id}/timeline",
    response_model=LinhaDoTempoItemResponse,
    summary="Consultar a linha do tempo de um item rastreável",
    description=(
        "ADR-0046, Passo 11.3. O item não tem histórico próprio — tudo o que "
        "aparece aqui vem da `TransformationEvent` em que ele participa, hoje "
        "só como saída (a que o criou). Nada é copiado do animal de origem: a "
        "transformação é citada por ambos, não duplicada."
    ),
    responses=RESPOSTAS_PADRAO,
)
def consultar_linha_do_tempo_do_item(
    item_id: str,
    contexto: Annotated[OrganizationContext, Depends(require_permission(TIMELINE_LER))],
    connection: ConnectionDependency,
    occurred_until: Annotated[datetime | None, Query()] = None,
    known_until: Annotated[datetime | None, Query()] = None,
) -> LinhaDoTempoItemResponse:
    alvo = typed_id_or_problem(item_id, entity_type="traceable_item", campo="item_id")

    try:
        corte = (
            TimelineCutoff(occurred_until=occurred_until, known_until=known_until)
            if (occurred_until or known_until)
            else None
        )
    except ValueError as error:
        raise DomainProblem(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            reason_code="ENTRADA_INVALIDA",
            title="Entrada inválida",
            detail=str(error),
        ) from error

    entradas = _timeline_service(connection).item_timeline(contexto.organization_id, alvo, corte)
    return LinhaDoTempoItemResponse(
        item_id=str(alvo.value),
        known_until=known_until.isoformat() if known_until else None,
        entry_count=len(entradas),
        entries=_entradas_para_json(entradas),
    )


_RECALL_RELATION_TYPES = (TRANSFORMATION_INPUT_OF, TRANSFORMATION_OUTPUT_OF)


def _executar_recall_de_transformacao(
    connection: Connection, contexto: OrganizationContext, subject_id: SharedTypedId
) -> RecallResult:
    """Percorre só o grafo de transformação (Passo 7.4 aplicado ao ADR-0046).

    `AMBAS` é necessário porque toda relação projetada aponta do participante
    para o evento (nunca o contrário, ver `transformation_service.py`):
    alcançar "o outro lado" sempre exige combinar saída e entrada no nó do
    evento. `relation_types` mantém a travessia dentro do grafo de
    transformação — sem isso, o recall vazaria para parentesco, movimentação
    e qualquer outro vínculo que a mesma tabela guarde.
    """
    servico = RecallService(relations=TransactionalRelationRepository(connection=connection))
    resultado = servico.execute(
        RecallRequest(
            organization_id=contexto.organization_id,
            subject_reference=UniversalReference(
                target_id=subject_id,
                organization_id=contexto.organization_id,
                contract_version=AGGREGATE_CONTRACT_VERSION,
            ),
            direction=RecallDirection.AMBAS,
            mode=RecallMode.SIMULACAO,
            relation_types=_RECALL_RELATION_TYPES,
        )
    )
    return resultado


def _status_de_no(connection: Connection, entity_type: str, entity_id: SharedTypedId) -> str | None:
    """Estado derivado CURRENT/SUPERSEDED de um nó do recall (ADR-0047, item 10).

    Só `TransformationEvent` e `TraceableItem` têm este conceito — para
    `TraceableItem`, o estado é o do evento que o criou (a "origem" do item, e
    não uma propriedade do item em si). Qualquer outro tipo de nó (animal,
    propriedade) devolve `None`: a correção de `TransformationEvent` não altera
    o que esses sujeitos são.
    """
    if entity_type == "transformation_event":
        return operational_status_now(
            TransactionalTransformationEventRepository(connection=connection), entity_id
        ).value
    if entity_type == "traceable_item":
        item = TransactionalTraceableItemRepository(connection=connection).get_by_id(entity_id)
        if item is None or item.created_by_transformation_id is None:
            return None
        return operational_status_now(
            TransactionalTransformationEventRepository(connection=connection),
            item.created_by_transformation_id,
        ).value
    return None


def _recall_resposta(
    connection: Connection, resultado: RecallResult, subject_id: SharedTypedId
) -> RecallResponse:
    return RecallResponse(
        recall_id=str(resultado.recall_id.value),
        subject_type=subject_id.entity_type,
        subject_id=str(subject_id.value),
        status=resultado.status.value,
        visited_nodes=resultado.visited_nodes,
        caminhos=[
            RecallCaminhoResponse(
                explicacao=caminho.explain(),
                passos=[
                    RecallPassoResponse(
                        relation_type=passo.relation_type,
                        de_tipo=passo.from_reference.target_id.entity_type,
                        de_id=str(passo.from_reference.target_id.value),
                        de_status=_status_de_no(
                            connection,
                            passo.from_reference.target_id.entity_type,
                            passo.from_reference.target_id,
                        ),
                        para_tipo=passo.to_reference.target_id.entity_type,
                        para_id=str(passo.to_reference.target_id.value),
                        para_status=_status_de_no(
                            connection,
                            passo.to_reference.target_id.entity_type,
                            passo.to_reference.target_id,
                        ),
                        direcao=passo.direction.value,
                    )
                    for passo in caminho.steps
                ],
            )
            for caminho in resultado.paths
        ],
        lacunas=[
            RecallLacunaResponse(
                motivo=lacuna.reason.value,
                profundidade=lacuna.depth,
                descricao=lacuna.description,
            )
            for lacuna in resultado.gaps
        ],
    )


@router.get(
    "/traceable-items/{item_id}/recall",
    response_model=RecallResponse,
    summary="Rastrear a origem de um item (item → transformação → animal)",
    description=(
        "ADR-0046, Passo 11.3. Percorre a projeção `UniversalRelation` da "
        "transformação para localizar o animal (e outros itens do mesmo "
        "evento, se houver). `status=inconclusivo` significa que a travessia "
        "parou antes de esgotar o grafo — nunca que a origem é outra coisa."
    ),
    responses=RESPOSTAS_PADRAO,
)
def rastrear_origem_do_item(
    item_id: str,
    contexto: Annotated[OrganizationContext, Depends(require_permission(TRACEABILITY_LER))],
    connection: ConnectionDependency,
) -> RecallResponse:
    alvo = typed_id_or_problem(item_id, entity_type="traceable_item", campo="item_id")
    resultado = _executar_recall_de_transformacao(connection, contexto, alvo)
    return _recall_resposta(connection, resultado, alvo)


@router.get(
    "/animals/{animal_id}/recall",
    response_model=RecallResponse,
    summary="Rastrear o destino de um animal (animal → transformação → itens)",
    description=(
        "ADR-0046, Passo 11.3. Percorre a projeção `UniversalRelation` da "
        "transformação para localizar todos os `TraceableItem` produzidos a "
        "partir deste animal. `status=inconclusivo` significa que a travessia "
        "parou antes de esgotar o grafo — nunca que não há mais itens."
    ),
    responses=RESPOSTAS_PADRAO,
)
def rastrear_destino_do_animal(
    animal_id: str,
    contexto: Annotated[OrganizationContext, Depends(require_permission(TRACEABILITY_LER))],
    connection: ConnectionDependency,
) -> RecallResponse:
    alvo = typed_id_or_problem(animal_id, entity_type="animal", campo="animal_id")
    resultado = _executar_recall_de_transformacao(connection, contexto, alvo)
    return _recall_resposta(connection, resultado, alvo)


def _item_resposta(item: TraceableItem) -> ItemResponse:
    return ItemResponse(
        item_id=str(item.item_id.value),
        item_type=item.item_type,
        label=item.label,
        created_at=item.created_at,
        created_by_transformation_id=(
            str(item.created_by_transformation_id.value)
            if item.created_by_transformation_id is not None
            else None
        ),
    )


def _item_nao_encontrado() -> DomainProblem:
    return DomainProblem(
        status_code=status.HTTP_404_NOT_FOUND,
        reason_code="RECURSO_NAO_ENCONTRADO",
        title="Recurso não encontrado",
        detail="Item rastreável não encontrado nesta organização.",
    )


def _participante_do_item(
    evento: TransformationEvent, item_id: SharedTypedId
) -> TransformationParticipant | None:
    for participante in (*evento.inputs, *evento.outputs):
        if participante.subject_reference.target_id == item_id:
            return participante
    return None


def _evidencia_resposta(
    referencia: UniversalReference, lookup: TransactionalEvidenceRepository
) -> EvidenciaDossierResponse:
    encontrada = lookup.get_by_id(referencia.target_id)
    if encontrada is None:
        return EvidenciaDossierResponse(
            id=str(referencia.target_id.value), content_status="NAO_ACOMPANHA", content=None
        )
    return EvidenciaDossierResponse(
        id=str(referencia.target_id.value),
        content_status="COPIADO",
        content=evidence_content(encontrada),
    )


@router.get(
    "/traceable-items/{item_id}",
    response_model=ItemResponse,
    summary="Detalhar um item rastreável",
    description=(
        "ADR-0046, Passo 11.5. Identidade mínima do item: tipo, rótulo e a "
        "transformação que o criou. Para a história completa, ver `/timeline`; "
        "para a origem, `/recall`; para tudo junto, `/dossier`."
    ),
    responses=RESPOSTAS_PADRAO,
)
def detalhar_item(
    item_id: str,
    contexto: Annotated[OrganizationContext, Depends(require_permission(TIMELINE_LER))],
    connection: ConnectionDependency,
) -> ItemResponse:
    alvo = typed_id_or_problem(item_id, entity_type="traceable_item", campo="item_id")
    item = TransactionalTraceableItemRepository(connection=connection).get_by_id(alvo)
    if item is None or item.organization_id != contexto.organization_id:
        raise _item_nao_encontrado()
    return _item_resposta(item)


@router.get(
    "/traceable-items/{item_id}/dossier",
    response_model=ItemDossierResponse,
    summary="Montar o dossiê de rastreabilidade de um item",
    description=(
        "ADR-0046, Passo 11.5. Reúne num só documento: a transformação que "
        "criou o item, a relação quantitativa declarada, a linha do tempo, as "
        "origens alcançadas por recall (com cobertura/lacunas) e as evidências "
        "citadas pela transformação. **Não é o Dossier do Core** — aquele exige "
        "uma `Decision`, e nenhuma regra ainda avalia `TraceableItem`; este é "
        "um documento de leitura próprio da vertical, sem gravação nenhuma. "
        "Por isso usa `TIMELINE_LER`, e não `DOSSIER_LER`: não é o documento de "
        "prova reservado ao auditor, é a mesma informação que `/timeline` e "
        "`/recall` já expõem ao operador, só reunida num só lugar."
    ),
    responses=RESPOSTAS_PADRAO,
)
def montar_dossie_do_item(
    item_id: str,
    contexto: Annotated[OrganizationContext, Depends(require_permission(TIMELINE_LER))],
    connection: ConnectionDependency,
) -> ItemDossierResponse:
    alvo = typed_id_or_problem(item_id, entity_type="traceable_item", campo="item_id")
    item = TransactionalTraceableItemRepository(connection=connection).get_by_id(alvo)
    if item is None or item.organization_id != contexto.organization_id:
        raise _item_nao_encontrado()

    evento = (
        None
        if item.created_by_transformation_id is None
        else TransactionalTransformationEventRepository(connection=connection).get_by_id(
            item.created_by_transformation_id
        )
    )
    if evento is None or evento.organization_id != contexto.organization_id:
        raise DomainProblem(
            status_code=status.HTTP_404_NOT_FOUND,
            reason_code="RECURSO_NAO_ENCONTRADO",
            title="Recurso não encontrado",
            detail="TransformationEvent que criou o item não foi encontrado.",
        )

    participante = _participante_do_item(evento, alvo)
    entradas_timeline = _timeline_service(connection).item_timeline(contexto.organization_id, alvo)
    recall = _executar_recall_de_transformacao(connection, contexto, alvo)
    evidencia_lookup = TransactionalEvidenceRepository(connection=connection)

    event_repository = TransactionalTransformationEventRepository(connection=connection)
    estado_evento = operational_status_now(event_repository, evento.event_id)
    correcao = event_repository.get_correction_of(evento.event_id)

    return ItemDossierResponse(
        item=_item_resposta(item),
        transformation=TransformacaoResumoResponse(
            transformation_id=str(evento.event_id.value),
            process_type=evento.process_type.value,
            occurred_at=evento.occurred_at,
            facility_id=str(evento.facility_reference.target_id.value),
            balance=_balanco_resposta(evento.balance),
            status=estado_evento.value,
            corrected_by_transformation_id=(
                str(correcao.event_id.value) if correcao is not None else None
            ),
        ),
        quantitative=(
            None
            if participante is None
            else QuantidadeResponse(
                quantity=(
                    str(participante.quantity) if participante.quantity is not None else None
                ),
                unit=participante.unit,
                measurement_basis=participante.measurement_basis,
            )
        ),
        timeline=LinhaDoTempoItemResponse(
            item_id=str(alvo.value),
            known_until=None,
            entry_count=len(entradas_timeline),
            entries=_entradas_para_json(entradas_timeline),
        ),
        origins=_recall_resposta(connection, recall, alvo),
        evidences=[
            _evidencia_resposta(referencia, evidencia_lookup)
            for referencia in evento.evidence_references
        ],
    )


@router.get(
    "/dossiers",
    summary="Listar dossiês de um sujeito",
    description=(
        "Exige `subject_id`. Sem ele a consulta devolveria toda a prova da "
        "organização de uma vez, que não é pergunta que alguém faça — e é varredura "
        "cara sobre a tabela mais sensível do sistema."
    ),
    responses=RESPOSTAS_PADRAO,
)
def listar_dossies(
    subject_id: str,
    contexto: Annotated[OrganizationContext, Depends(require_permission(DOSSIER_LER))],
    connection: ConnectionDependency,
    paginacao: PaginacaoDependency,
) -> dict[str, Any]:
    alvo = typed_id_or_problem(subject_id, entity_type="animal", campo="subject_id")
    encontrados = TransactionalDossierRepository(connection=connection).list_by_subject(
        contexto.organization_id,
        alvo,
        limit=paginacao.limite_de_sondagem,
        offset=paginacao.offset,
    )
    # O resumo traz o suficiente para escolher qual dossiê abrir; o documento
    # inteiro vem na rota de detalhe, porque é grande e nem sempre necessário.
    pagina = montar_pagina(
        [
            {
                "dossier_id": str(dossie.dossier_id.value),
                "purpose": dossie.purpose,
                "decision_id": str(dossie.decision_id.value),
                "evaluation_id": str(dossie.evaluation_id.value),
                "generated_at": dossie.generated_at.isoformat(),
                "dossier_hash": dossie.dossier_hash,
                "document_version": dossie.document_version,
            }
            for dossie in encontrados
        ],
        paginacao,
    )
    return {
        "subject_id": str(alvo.value),
        **pagina,
    }


@router.get(
    "/dossiers/{dossier_id}",
    summary="Obter o dossiê de uma decisão",
    description=(
        "Devolve o documento canônico completo, com o hash que permite verificá-lo "
        "sem depender do Titan."
    ),
    responses=RESPOSTAS_PADRAO,
)
def obter_dossie(
    dossier_id: str,
    contexto: Annotated[OrganizationContext, Depends(require_permission(DOSSIER_LER))],
    connection: ConnectionDependency,
) -> dict[str, Any]:
    alvo = typed_id_or_problem(dossier_id, entity_type="dossier", campo="dossier_id")
    dossier = TransactionalDossierRepository(connection=connection).get_by_id(alvo)

    # O RLS já esconde o dossiê de outra organização; a conferência explícita é a
    # segunda camada, e não repousa apenas no banco.
    if dossier is None or dossier.organization_id != contexto.organization_id:
        raise DomainProblem(
            status_code=status.HTTP_404_NOT_FOUND,
            reason_code="RECURSO_NAO_ENCONTRADO",
            title="Recurso não encontrado",
            detail="Dossiê não encontrado nesta organização.",
        )

    return dossier.to_dict()
