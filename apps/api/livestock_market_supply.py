"""HTTP adapter shell for Market Supply aggregate assessments.

The router is included only behind ``TITAN_MARKET_SUPPLY_AGGREGATE_API_ENABLED``.
It intentionally does not implement a shortcut aggregate path: every releasable
result must still come from the audited Market Supply application pipeline.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from apps.api.livestock_dependencies import require_permission
from packages.core_domain import OrganizationContext
from packages.livestock_application.authorization import MARKET_SUPPLY_AGGREGATE_ASSESS
from packages.livestock_application.market_supply_response import MARKET_SUPPLY_NO_STORE_HEADERS

IDEMPOTENCY_HEADER = "Idempotency-Key"
require_market_supply_aggregate_assess = require_permission(MARKET_SUPPLY_AGGREGATE_ASSESS)

router = APIRouter(prefix="/v1/livestock", tags=["livestock"])


class MarketSupplyCommercialWindowRequest(BaseModel):
    from_: str = Field(alias="from", min_length=1)
    until: str = Field(min_length=1)


class MarketSupplyCandidateCriteriaRequest(BaseModel):
    subject_type: str = "animal"
    required_tags: list[str] = Field(default_factory=list)


class MarketSupplyAggregateAssessmentRequest(BaseModel):
    policy_id: UUID
    policy_version: int = Field(ge=1)
    purpose: str = Field(min_length=1)
    quantity: int = Field(ge=1)
    commercial_window: MarketSupplyCommercialWindowRequest
    reference_time: str = Field(min_length=1)
    knowledge_cutoff: str = Field(min_length=1)
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
    _: MarketSupplyAggregateAssessmentRequest,
    __: Annotated[OrganizationContext, Depends(require_market_supply_aggregate_assess)],
    ___: Annotated[str, Header(alias=IDEMPOTENCY_HEADER, min_length=1)],
) -> JSONResponse:
    """Fail closed until the audited orchestration is wired into the API.

    Returning a public aggregate from here would violate ADR-0071 unless the
    handler has already persisted the corresponding audit record. The endpoint
    shell exists only for feature-flagged contract closure.
    """

    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        headers=dict(MARKET_SUPPLY_NO_STORE_HEADERS),
        content={
            "type": "urn:titan:problema:market-supply-pipeline-nao-habilitado",
            "title": "Market Supply não habilitado",
            "status": status.HTTP_503_SERVICE_UNAVAILABLE,
            "detail": "A rota está protegida até a composição auditável ser habilitada.",
            "instance": request.url.path,
            "reason_code": "MARKET_SUPPLY_PIPELINE_NAO_HABILITADO",
        },
        media_type="application/problem+json",
    )
