"""HTTP endpoint for Market Optionality AI Explanation (Passo AI Explanation API).

Este router é incluído somente quando `TITAN_MARKET_OPTIONALITY_AI_EXPLANATION_API_ENABLED=true`.
Permite ao produtor ou operador consultar a explicação não decisional do status
de optionalidade de mercado de um animal próprio.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from apps.api.livestock_dependencies import (
    ConnectionDependency,
    require_permission,
    typed_id_or_problem,
)
from apps.api.problem import DomainProblem
from packages.core_domain import OrganizationContext
from packages.core_infrastructure.persistence.decision import TransactionalDecisionRepository
from packages.core_infrastructure.persistence.evaluation import TransactionalEvaluationRepository
from packages.livestock_application.authorization import MARKET_OPTION_EXPLAIN
from packages.livestock_application.market_optionality import (
    AnimalMarketOptionExplanationCommand,
    AnimalMarketOptionExplanationOrchestrator,
    MarketOptionExplanationPipelineService,
)
from packages.livestock_infrastructure.ai_explanation_provider import (
    GeminiMarketOptionExplanationTextProvider,
)
from packages.livestock_infrastructure.persistence.ai_explanation_audit_repository import (
    TransactionalAIExplanationAuditRepository,
)
from packages.livestock_infrastructure.persistence.animal_repository import (
    TransactionalAnimalRepository,
)
from packages.shared_kernel import TypedId

require_market_option_explain = require_permission(MARKET_OPTION_EXPLAIN)

router = APIRouter(prefix="/v1/livestock", tags=["livestock"])


def _nao_encontrado(o_que: str) -> DomainProblem:
    return DomainProblem(
        status_code=status.HTTP_404_NOT_FOUND,
        reason_code="RECURSO_NAO_ENCONTRADO",
        title="Recurso não encontrado",
        detail=f"{o_que} não encontrado nesta organização.",
    )


def _build_orchestrator(
    connection: ConnectionDependency,
    model_name: str,
) -> AnimalMarketOptionExplanationOrchestrator:
    decision_repo = TransactionalDecisionRepository(connection)
    evaluation_repo = TransactionalEvaluationRepository(connection)
    audit_repo = TransactionalAIExplanationAuditRepository(connection)

    provider = GeminiMarketOptionExplanationTextProvider.from_environment(model_name=model_name)

    pipeline = MarketOptionExplanationPipelineService(
        text_provider=provider,
        audit_repository=audit_repo,
    )
    return AnimalMarketOptionExplanationOrchestrator(
        decision_repository=decision_repo,
        evaluation_repository=evaluation_repo,
        pipeline_service=pipeline,
    )


class AnimalMarketOptionExplanationRequest(BaseModel):
    policy_id: UUID
    policy_version: int = Field(ge=1)
    market_purpose: str = Field(min_length=1)
    reference_time: datetime
    knowledge_cutoff: datetime


class AnimalMarketOptionExplanationResponseModel(BaseModel):
    subject_id: str
    market_purpose: str
    policy_id: str
    policy_version: int
    reference_time: datetime
    knowledge_cutoff: datetime
    canonical_state: str
    reversibility: str
    release_disposition: str
    explanation_text: str | None
    canonical_fallback: dict[str, Any]
    audit_id: str | None


@router.post(
    "/animals/{animal_id}/market-optionality/explanation",
    response_model=AnimalMarketOptionExplanationResponseModel,
    summary="Explicar optionalidade de mercado de um animal com IA",
    responses={
        200: {"description": "Explicação liberada ou fallback canônico estruturado"},
        401: {"description": "Acesso não autenticado"},
        403: {"description": "Sem permissão na organização do animal"},
        404: {"description": "Animal não encontrado nesta organização"},
        422: {"description": "Entrada inválida"},
    },
)
def explain_animal_market_optionality(
    animal_id: str,
    body: AnimalMarketOptionExplanationRequest,
    contexto: Annotated[OrganizationContext, Depends(require_market_option_explain)],
    connection: ConnectionDependency,
    request_http: Request,
) -> JSONResponse:
    alvo = typed_id_or_problem(animal_id, entity_type="animal", campo="animal_id")
    animal_repo = TransactionalAnimalRepository(connection=connection)
    encontrado = animal_repo.get_by_id(alvo)
    if encontrado is None or encontrado.organization_id != contexto.organization_id:
        raise _nao_encontrado("Animal")

    ref_time = body.reference_time
    if ref_time.tzinfo is None or ref_time.utcoffset() != UTC.utcoffset(ref_time):
        raise DomainProblem(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            reason_code="DATA_INVALIDA",
            title="Data inválida",
            detail="reference_time deve estar em UTC.",
        )
    cutoff = body.knowledge_cutoff
    if cutoff.tzinfo is None or cutoff.utcoffset() != UTC.utcoffset(cutoff):
        raise DomainProblem(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            reason_code="DATA_INVALIDA",
            title="Data inválida",
            detail="knowledge_cutoff deve estar em UTC.",
        )
    if cutoff < ref_time:
        raise DomainProblem(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            reason_code="DATA_INVALIDA",
            title="Data inválida",
            detail="knowledge_cutoff não pode ser anterior a reference_time.",
        )

    model_name = os.environ.get("TITAN_AI_EXPLANATION_MODEL", "models/gemini-3.7-flash")
    orchestrator = _build_orchestrator(connection, model_name)

    idempotency_key = request_http.headers.get("Idempotency-Key")

    command = AnimalMarketOptionExplanationCommand(
        organization_id=contexto.organization_id,
        animal_id=alvo,
        policy_id=TypedId("policy", body.policy_id),
        policy_version=body.policy_version,
        market_purpose=body.market_purpose,
        reference_time=ref_time,
        knowledge_cutoff=cutoff,
        idempotency_reference=idempotency_key,
        model_name=model_name,
    )

    result = orchestrator.explain_for_animal(command)

    content: dict[str, Any] = {
        "subject_id": str(result.subject_id.value),
        "market_purpose": result.market_purpose,
        "policy_id": str(result.policy_id.value),
        "policy_version": result.policy_version,
        "reference_time": result.reference_time.isoformat(),
        "knowledge_cutoff": result.knowledge_cutoff.isoformat(),
        "canonical_state": result.canonical_state.value,
        "reversibility": result.reversibility.value,
        "release_disposition": result.release_disposition.value,
        "explanation_text": result.explanation_text,
        "canonical_fallback": dict(result.canonical_fallback),
        "audit_id": None if result.audit_id is None else str(result.audit_id.value),
    }

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=content,
        headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
    )
