"""HTTP adapter shell for Market Supply aggregate assessments.

The router is included only behind ``TITAN_MARKET_SUPPLY_AGGREGATE_API_ENABLED``.
It intentionally does not implement a shortcut aggregate path: every releasable
result must still come from the audited Market Supply application pipeline.
"""

import os
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from apps.api.livestock_dependencies import require_permission
from apps.api.problem import DomainProblem
from packages.core_domain import OrganizationContext
from packages.livestock_application.authorization import MARKET_SUPPLY_AGGREGATE_ASSESS
from packages.livestock_application.market_supply_population import CandidatePopulationCriteria
from packages.livestock_application.market_supply_privacy import load_aggregation_privacy_profile
from packages.livestock_application.market_supply_request import CommercialDemandContext
from packages.livestock_application.market_supply_response import MARKET_SUPPLY_NO_STORE_HEADERS
from packages.shared_kernel import TypedId
from packages.shared_kernel.temporal import require_utc

IDEMPOTENCY_HEADER = "Idempotency-Key"
require_market_supply_aggregate_assess = require_permission(MARKET_SUPPLY_AGGREGATE_ASSESS)

router = APIRouter(prefix="/v1/livestock", tags=["livestock"])


class MarketSupplyCommercialWindowRequest(BaseModel):
    from_: datetime = Field(alias="from")
    until: datetime


class MarketSupplyCandidateCriteriaRequest(BaseModel):
    subject_type: str = "animal"
    required_tags: list[str] = Field(default_factory=list)


class MarketSupplyAggregateAssessmentRequest(BaseModel):
    policy_id: UUID
    policy_version: int = Field(ge=1)
    purpose: str = Field(min_length=1)
    quantity: int = Field(ge=1)
    commercial_window: MarketSupplyCommercialWindowRequest
    reference_time: datetime
    knowledge_cutoff: datetime
    candidate_criteria: MarketSupplyCandidateCriteriaRequest


@router.post(
    "/market-supply/aggregate-assessments",
    summary="Solicitar avaliação agregada de Market Supply",
    responses={
        200: {"description": "Resultado agregado liberado ou resposta uniforme não liberada"},
        401: {"description": "Token ausente, inválido ou expirado"},
        403: {"description": "Sem vínculo com a organização, ou sem a permissão exigida"},
        503: {"description": "Pipeline auditável ainda não habilitado"},
        422: {"description": "Entrada inválida"},
    },
)
def assess_market_supply_aggregate(
    request: Request,
    body: MarketSupplyAggregateAssessmentRequest,
    context: Annotated[OrganizationContext, Depends(require_market_supply_aggregate_assess)],
    ___: Annotated[str, Header(alias=IDEMPOTENCY_HEADER, min_length=1)],
) -> JSONResponse:
    """Fail closed until the audited orchestration is wired into the API.

    Returning a public aggregate from here would violate ADR-0071 unless the
    handler has already persisted the corresponding audit record. The endpoint
    shell exists only for feature-flagged contract closure.
    """

    try:
        _build_request_contexts(body=body, context=context)
    except DomainProblem:
        raise
    except ValueError as error:
        raise DomainProblem(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            reason_code="MARKET_SUPPLY_REQUEST_INVALIDA",
            title="Requisicao de Market Supply invalida",
            detail=str(error),
        ) from error
    try:
        load_aggregation_privacy_profile(os.environ)
    except ValueError:
        return _not_enabled_response(
            request=request,
            reason_code="MARKET_SUPPLY_PRIVACY_PROFILE_NAO_CONFIGURADO",
            detail="O privacy profile de Market Supply não está configurado explicitamente.",
        )

    return _not_enabled_response(
        request=request,
        reason_code="MARKET_SUPPLY_PIPELINE_NAO_HABILITADO",
        detail="A rota está protegida até a composição auditável ser habilitada.",
    )


def _build_request_contexts(
    *,
    body: MarketSupplyAggregateAssessmentRequest,
    context: OrganizationContext,
) -> tuple[CommercialDemandContext, CandidatePopulationCriteria]:
    for field_name in (
        "commercial_window.from_",
        "commercial_window.until",
        "reference_time",
        "knowledge_cutoff",
    ):
        value = _field_value(body, field_name)
        try:
            require_utc(value, field_name=field_name)
        except ValueError as error:
            raise DomainProblem(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                reason_code="TEMPO_NAO_UTC",
                title="Tempo inválido",
                detail=f"O campo {field_name} deve possuir timezone UTC.",
            ) from error
    policy_id = TypedId("policy", body.policy_id)
    demand = CommercialDemandContext(
        buyer_organization_id=context.organization_id,
        purpose=body.purpose,
        policy_id=policy_id,
        policy_version=body.policy_version,
        requested_quantity=body.quantity,
        commercial_window_from=body.commercial_window.from_,
        commercial_window_until=body.commercial_window.until,
    )
    criteria = CandidatePopulationCriteria(
        organization_id=context.organization_id,
        purpose=body.purpose,
        policy_id=policy_id,
        policy_version=body.policy_version,
        reference_time=body.reference_time,
        knowledge_cutoff=body.knowledge_cutoff,
        commercial_window_start=body.commercial_window.from_,
        commercial_window_end=body.commercial_window.until,
        subject_type=body.candidate_criteria.subject_type,
        required_tags=tuple(body.candidate_criteria.required_tags),
    )
    return demand, criteria


def _field_value(body: MarketSupplyAggregateAssessmentRequest, field_name: str) -> datetime:
    if field_name == "commercial_window.from_":
        return body.commercial_window.from_
    if field_name == "commercial_window.until":
        return body.commercial_window.until
    if field_name == "reference_time":
        return body.reference_time
    if field_name == "knowledge_cutoff":
        return body.knowledge_cutoff
    raise ValueError(f"Campo temporal desconhecido: {field_name}")


def _not_enabled_response(
    *,
    request: Request,
    reason_code: str,
    detail: str,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        headers=dict(MARKET_SUPPLY_NO_STORE_HEADERS),
        content={
            "type": f"urn:titan:problema:{reason_code.lower().replace('_', '-')}",
            "title": "Market Supply não habilitado",
            "status": status.HTTP_503_SERVICE_UNAVAILABLE,
            "detail": detail,
            "instance": request.url.path,
            "reason_code": reason_code,
        },
        media_type="application/problem+json",
    )
