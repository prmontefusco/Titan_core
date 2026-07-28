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

from apps.api.livestock_dependencies import (
    ConnectionDependency,
    require_permission,
    typed_id_or_problem,
)
from apps.api.pagination import PaginacaoDependency, montar_pagina
from apps.api.problem import RESPOSTAS_PADRAO, DomainProblem
from packages.core_application.dossier_service import DossierService
from packages.core_application.recall_service import RecallService
from packages.core_domain import OrganizationContext
from packages.core_domain.recall import (
    RecallDirection,
    RecallMode,
    RecallRequest,
    RecallResult,
)
from packages.core_infrastructure.persistence.decision import TransactionalDecisionRepository
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
)
from packages.livestock_application.timeline_service import (
    LivestockTimelineService,
    TimelineCutoff,
    TimelineEntry,
)
from packages.livestock_application.transformation_service import (
    TRANSFORMATION_INPUT_OF,
    TRANSFORMATION_OUTPUT_OF,
)
from packages.livestock_application.withdrawal_service import WithdrawalCalculator
from packages.livestock_infrastructure.persistence.animal_repository import (
    TransactionalAnimalRepository,
)
from packages.livestock_infrastructure.persistence.establishment_qualification_repository import (
    TransactionalEstablishmentQualificationRepository,
)
from packages.livestock_infrastructure.persistence.external_counterparty_repository import (
    TransactionalExternalCounterpartyRepository,
)
from packages.livestock_infrastructure.persistence.imported_fact_repository import (
    TransactionalImportedLivestockFactRepository,
)
from packages.livestock_infrastructure.persistence.lot_repository import (
    TransactionalLivestockLotRepository,
    TransactionalLotMembershipRepository,
)
from packages.livestock_infrastructure.persistence.medication_repository import (
    TransactionalMedicationBatchRepository,
    TransactionalMedicationRepository,
)
from packages.livestock_infrastructure.persistence.movement_repository import (
    TransactionalAnimalMovementRepository,
)
from packages.livestock_infrastructure.persistence.property_repository import (
    TransactionalRuralPropertyRepository,
)
from packages.livestock_infrastructure.persistence.sanitary_campaign_repository import (
    TransactionalSanitaryCampaignRepository,
)
from packages.livestock_infrastructure.persistence.treatment_repository import (
    TransactionalTreatmentApplicationRepository,
)
from packages.shared_kernel import OrganizationId, UniversalReference
from packages.shared_kernel import TypedId as SharedTypedId

router = APIRouter(prefix="/v1/livestock", tags=["livestock"])


class ElegibilidadeResponse(BaseModel):
    animal_id: str
    result: str
    outcome: str
    evaluation_id: str
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
    decision_id: str
    dossier_id: str
    markets: list[dict[str, Any]]


class LinhaDoTempoItemResponse(BaseModel):
    item_id: str
    known_until: str | None
    entry_count: int
    entries: list[dict[str, Any]]


class RecallPassoResponse(BaseModel):
    relation_type: str
    de_tipo: str
    de_id: str
    para_tipo: str
    para_id: str
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
    fact_provider = LivestockFactProvider(
        property_repository=TransactionalRuralPropertyRepository(connection=connection),
        animal_repository=animal_repository,
        external_counterparty_repository=TransactionalExternalCounterpartyRepository(
            connection=connection
        ),
        establishment_qualification_repository=TransactionalEstablishmentQualificationRepository(
            connection=connection
        ),
        imported_fact_repository=TransactionalImportedLivestockFactRepository(
            connection=connection
        ),
        withdrawal_calculator=WithdrawalCalculator(
            application_repository=application_repository,
            batch_repository=batch_repository,
            medication_repository=TransactionalMedicationRepository(connection=connection),
        ),
        sanitary_campaign_repository=TransactionalSanitaryCampaignRepository(connection=connection),
        treatment_application_repository=application_repository,
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

    evaluation, decision = PharmacologicalEligibilityService(
        fact_provider=fact_provider,
        policy=policy,
        rule=rule,
        evaluation_repository=evaluations,
        decision_repository=decisions,
    ).evaluate_animal(organizacao, alvo, datetime.now(UTC))

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
        decision_id=str(decision.decision_id.value),
        dossier_id=str(dossier.dossier_id.value),
        reasons=[razao.message for razao in decision.reasons],
        governed_rule=None if governed_rule is None else governed_rule.to_dict(),
    )


class ElegibilidadeLoteResponse(BaseModel):
    lot_id: str
    result: str
    outcome: str
    evaluation_id: str
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

    evaluation, decision = PharmacologicalEligibilityService(
        fact_provider=fact_provider,
        policy=policy,
        # `rule` não é usado por evaluate_lot (que consulta lot_rule), mas o
        # campo é obrigatório no serviço; a regra de animal já está em mãos.
        rule=animal_rule,
        evaluation_repository=evaluations,
        decision_repository=decisions,
        lot_rule=lot_rule,
    ).evaluate_lot(organizacao, alvo, datetime.now(UTC))

    return ElegibilidadeLoteResponse(
        lot_id=str(alvo.value),
        result=decision.result.value,
        outcome=evaluation.outcome.value,
        evaluation_id=str(evaluation.evaluation_id.value),
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

    matrix = MarketEligibilityService(
        adoption_reader=TransactionalRuleAdoptionRepository(connection),
        rule_reader=TransactionalRuleRepository(connection=connection),
        policy_reader=TransactionalPolicyRepository(connection=connection),
        fact_provider=fact_provider,
        evaluation_repository=evaluations,
        decision_repository=decisions,
        profiles=DEFAULT_MARKET_PROFILES,
    ).evaluate(
        organization_id=organizacao,
        subject_id=alvo,
        at_time=instante,
        selected_subjects=selected_subjects,
    )

    executed_requirement = matrix.first_executed_requirement()
    if executed_requirement is None or executed_requirement.execution is None:
        evaluation, decision = PharmacologicalEligibilityService(
            fact_provider=fact_provider,
            policy=policy,
            rule=rule,
            evaluation_repository=evaluations,
            decision_repository=decisions,
        ).evaluate_animal(organizacao, alvo, instante)
    else:
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
        decision_id=str(decision.decision_id.value),
        dossier_id=str(dossier.dossier_id.value),
        markets=matrix.to_dict(),
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


def _recall_resposta(resultado: RecallResult, subject_id: SharedTypedId) -> RecallResponse:
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
                        para_tipo=passo.to_reference.target_id.entity_type,
                        para_id=str(passo.to_reference.target_id.value),
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
    return _recall_resposta(resultado, alvo)


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
    return _recall_resposta(resultado, alvo)


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
