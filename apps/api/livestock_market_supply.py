"""HTTP adapter shell for Market Supply aggregate assessments.

The router is included only behind ``TITAN_MARKET_SUPPLY_AGGREGATE_API_ENABLED``.
It intentionally does not implement a shortcut aggregate path: every releasable
result must still come from the audited Market Supply application pipeline.
"""

import json
import os
from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import Connection

from apps.api.livestock_dependencies import ConnectionDependency, require_permission
from apps.api.problem import DomainProblem
from packages.core_application import IdempotencyService
from packages.core_domain import OrganizationContext
from packages.core_infrastructure.persistence.authorization_grant import (
    TransactionalAuthorizationGrantRepository,
)
from packages.core_infrastructure.persistence.decision import TransactionalDecisionRepository
from packages.core_infrastructure.persistence.evaluation import TransactionalEvaluationRepository
from packages.core_infrastructure.persistence.idempotency import IdempotencyRepository
from packages.livestock_application.authorization import MARKET_SUPPLY_AGGREGATE_ASSESS
from packages.livestock_application.market_readiness import MarketReadinessService
from packages.livestock_application.market_supply import (
    MarketSupplyAggregateAssessmentCommand,
    MarketSupplyAggregateAssessmentOrchestrator,
    MarketSupplyAggregatePayloadBuilder,
    MarketSupplyReadinessCompositionService,
)
from packages.livestock_application.market_supply_population import (
    AuthorizedCandidatePopulationCompositionService,
    CandidatePopulationCriteria,
)
from packages.livestock_application.market_supply_privacy import (
    AggregationGeographicPrecision,
    load_aggregation_privacy_profile,
)
from packages.livestock_application.market_supply_request import (
    CommercialDemandContext,
    MarketSupplyIdempotencyGate,
)
from packages.livestock_application.market_supply_response import MARKET_SUPPLY_NO_STORE_HEADERS
from packages.livestock_application.market_supply_workflow import (
    MarketSupplyAggregateGateWorkflow,
    MarketSupplyIdempotentAggregateGateWorkflow,
)
from packages.livestock_infrastructure.persistence import (
    TransactionalMarketSupplyOwnerScopedQueryAuditRepository,
    TransactionalMarketSupplyOwnerScopedSubjectReader,
)
from packages.shared_kernel import TypedId, UniversalReference
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
    idempotency_key: Annotated[str, Header(alias=IDEMPOTENCY_HEADER, min_length=1)],
    connection: ConnectionDependency,
) -> JSONResponse:
    """Fail closed until the audited orchestration is wired into the API.

    Returning a public aggregate from here would violate ADR-0071 unless the
    handler has already persisted the corresponding audit record. The endpoint
    shell exists only for feature-flagged contract closure.
    """

    try:
        requested_at = datetime.now(UTC)
        demand, criteria = _build_request_contexts(body=body, context=context)
        identity = demand.to_request_identity(
            candidate_criteria_digest=criteria.digest(),
            reference_time=body.reference_time,
            knowledge_cutoff=body.knowledge_cutoff,
            idempotency_key=idempotency_key,
        )
        identity.to_idempotency_request(
            principal_reference=_principal_reference(context),
            requested_at=requested_at,
        )
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
        privacy_profile = load_aggregation_privacy_profile(os.environ)
    except ValueError:
        return _not_enabled_response(
            request=request,
            reason_code="MARKET_SUPPLY_PRIVACY_PROFILE_NAO_CONFIGURADO",
            detail="O privacy profile de Market Supply não está configurado explicitamente.",
        )

    if os.environ.get("TITAN_MARKET_SUPPLY_AGGREGATE_PIPELINE_ENABLED", "").casefold() != "true":
        return _not_enabled_response(
            request=request,
            reason_code="MARKET_SUPPLY_PIPELINE_NAO_HABILITADO",
            detail="A rota está protegida até a composição auditável ser habilitada.",
        )

    try:
        _, execution = _build_orchestrator(connection).execute_idempotent_single_owner(
            command=MarketSupplyAggregateAssessmentCommand(
                buyer_organization_id=context.organization_id,
                base_criteria=criteria,
                requested_quantity=demand.requested_quantity,
                privacy_profile=privacy_profile,
                geographic_precision=AggregationGeographicPrecision.REGION,
                filter_count=1 + len(body.candidate_criteria.required_tags),
                requested_at=requested_at,
                audit_id=TypedId.new("market_supply_query_audit"),
                correlation_id=TypedId.new("correlation"),
                idempotency_reference=identity.idempotency_key,
                semantic_request_digest=identity.semantic_digest(),
            ),
            identity=identity,
            principal_reference=_principal_reference(context),
        )
    except ValueError as error:
        return _not_enabled_response(
            request=request,
            reason_code="MARKET_SUPPLY_PIPELINE_NAO_HABILITADO",
            detail=str(error),
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        headers=dict(MARKET_SUPPLY_NO_STORE_HEADERS),
        content=_canonical_response_data(execution.result_canonical_bytes),
    )


def _build_orchestrator(connection: Connection) -> MarketSupplyAggregateAssessmentOrchestrator:
    grant_repository = TransactionalAuthorizationGrantRepository(connection)
    audit_repository = TransactionalMarketSupplyOwnerScopedQueryAuditRepository(connection)
    gate_workflow = MarketSupplyAggregateGateWorkflow(
        audit_repository=audit_repository,
        grant_reader=grant_repository,
    )
    return MarketSupplyAggregateAssessmentOrchestrator(
        population_composer=AuthorizedCandidatePopulationCompositionService(
            grant_reader=grant_repository,
            subject_reader=TransactionalMarketSupplyOwnerScopedSubjectReader(connection),
        ),
        readiness_composer=MarketSupplyReadinessCompositionService(
            decision_reader=TransactionalDecisionRepository(connection),
            evaluation_reader=TransactionalEvaluationRepository(connection),
            readiness_service=MarketReadinessService(),
        ),
        payload_builder=MarketSupplyAggregatePayloadBuilder(),
        gate_workflow=gate_workflow,
        idempotent_gate_workflow=MarketSupplyIdempotentAggregateGateWorkflow(
            workflow=gate_workflow,
            idempotency_gate=MarketSupplyIdempotencyGate(
                IdempotencyService(IdempotencyRepository(connection)),
            ),
        ),
    )


def _canonical_response_data(canonical_bytes: bytes) -> dict[str, object]:
    payload = json.loads(canonical_bytes.decode("utf-8"))
    data = _decode_canonical_payload(payload).get("data")
    if not isinstance(data, dict):
        raise RuntimeError("Market Supply canonical response invalida.")
    return data


def _decode_canonical_payload(payload: object) -> dict[str, Any]:
    if not isinstance(payload, list) or len(payload) != 2 or payload[0] != "titan-json-v1":
        raise RuntimeError("Market Supply canonical payload invalido.")
    value = _decode_canonical_value(payload[1])
    if not isinstance(value, dict):
        raise RuntimeError("Market Supply canonical envelope invalido.")
    return value


def _decode_canonical_value(value: object) -> Any:
    if not isinstance(value, list) or len(value) != 2:
        raise RuntimeError("Valor canonico invalido.")
    tag, raw = value
    if tag == "map":
        if not isinstance(raw, list):
            raise RuntimeError("Mapa canonico invalido.")
        decoded: dict[str, Any] = {}
        for pair in raw:
            if not isinstance(pair, list) or len(pair) != 2 or not isinstance(pair[0], str):
                raise RuntimeError("Entrada de mapa canonico invalida.")
            decoded[pair[0]] = _decode_canonical_value(pair[1])
        return decoded
    if tag == "list":
        if not isinstance(raw, list):
            raise RuntimeError("Lista canonica invalida.")
        return [_decode_canonical_value(item) for item in raw]
    if tag == "string":
        return raw
    if tag == "integer":
        return int(raw)
    if tag == "boolean":
        return raw == "true"
    if tag == "null":
        return None
    raise RuntimeError(f"Tipo canonico nao suportado para resposta HTTP: {tag}")


def _principal_reference(context: OrganizationContext) -> UniversalReference:
    return UniversalReference(
        target_id=context.user_id,
        organization_id=context.organization_id,
        contract_version=1,
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
