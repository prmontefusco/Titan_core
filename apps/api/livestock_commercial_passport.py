"""HTTP release gate for Commercial Passport.

The Commercial Passport API is deliberately feature-flagged and fail-closed
until the productive evaluation/issuance orchestration is wired. This module
declares the contract and guards the boundary without fabricating passport data
from request payloads.
"""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from apps.api.livestock_dependencies import require_permission, typed_id_or_problem
from apps.api.problem import DomainProblem
from packages.core_domain import OrganizationContext
from packages.livestock_application.authorization import DOSSIER_LER, PROPERTY_LER
from packages.livestock_application.commercial_passport import (
    CommercialPassportContext,
    PropertyCommercialPassportIssuancePort,
    PropertyCommercialPassportProjectionPort,
    commercial_passport_projection,
)
from packages.livestock_application.market_supply_response import MARKET_SUPPLY_NO_STORE_HEADERS
from packages.shared_kernel.temporal import require_utc

require_commercial_passport_read = require_permission(PROPERTY_LER)
require_commercial_passport_issue = require_permission(DOSSIER_LER)

router = APIRouter(prefix="/v1/livestock", tags=["livestock"])


class CommercialPassportIssueRequest(BaseModel):
    reference_time: datetime
    knowledge_cutoff: datetime
    audience: str = "internal"


def get_commercial_passport_projection_pipeline() -> (
    PropertyCommercialPassportProjectionPort | None
):
    return None


def get_commercial_passport_issuance_pipeline() -> PropertyCommercialPassportIssuancePort | None:
    return None


@router.get(
    "/properties/{property_id}/commercial-passport",
    summary="Consultar Commercial Passport dinâmico de uma propriedade",
    responses={
        200: {"description": "Commercial Passport dinâmico"},
        401: {"description": "Acesso não autenticado"},
        403: {"description": "Sem permissão na organização"},
        422: {"description": "Entrada inválida"},
        503: {"description": "Pipeline produtiva ainda não habilitada"},
    },
)
def get_property_commercial_passport(
    property_id: str,
    reference_time: datetime,
    knowledge_cutoff: datetime,
    context: Annotated[OrganizationContext, Depends(require_commercial_passport_read)],
    projection_pipeline: Annotated[
        PropertyCommercialPassportProjectionPort | None,
        Depends(get_commercial_passport_projection_pipeline),
    ],
) -> JSONResponse:
    property_ref = typed_id_or_problem(
        property_id,
        entity_type="rural_property",
        campo="property_id",
    )
    _validate_temporal_coordinates(reference_time, knowledge_cutoff)
    if projection_pipeline is None:
        return _not_enabled_response(
            reason_code="COMMERCIAL_PASSPORT_PIPELINE_NAO_HABILITADO",
            detail="A projection produtiva do Commercial Passport ainda não está habilitada.",
        )

    try:
        passport = projection_pipeline.build_property_passport(
            context=CommercialPassportContext(
                organization_id=context.organization_id,
                property_id=property_ref,
                reference_time=reference_time,
                knowledge_cutoff=knowledge_cutoff,
                evaluated_at=datetime.now(UTC),
            ),
        )
    except ValueError as error:
        raise DomainProblem(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            reason_code="COMMERCIAL_PASSPORT_REQUEST_INVALIDA",
            title="Requisição de Commercial Passport inválida",
            detail=str(error),
        ) from error

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        headers=dict(MARKET_SUPPLY_NO_STORE_HEADERS),
        content=commercial_passport_projection(passport),
    )


@router.post(
    "/properties/{property_id}/commercial-passport/issue",
    summary="Emitir snapshot formal do Commercial Passport de uma propriedade",
    responses={
        200: {"description": "Dossier/VerificationBundle emitido"},
        401: {"description": "Acesso não autenticado"},
        403: {"description": "Sem permissão na organização"},
        422: {"description": "Entrada inválida"},
        503: {"description": "Pipeline produtiva ainda não habilitada"},
    },
)
def issue_property_commercial_passport(
    property_id: str,
    body: CommercialPassportIssueRequest,
    context: Annotated[OrganizationContext, Depends(require_commercial_passport_issue)],
    issuance_pipeline: Annotated[
        PropertyCommercialPassportIssuancePort | None,
        Depends(get_commercial_passport_issuance_pipeline),
    ],
) -> JSONResponse:
    property_ref = typed_id_or_problem(
        property_id,
        entity_type="rural_property",
        campo="property_id",
    )
    if not body.audience.strip():
        raise DomainProblem(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            reason_code="COMMERCIAL_PASSPORT_REQUEST_INVALIDA",
            title="Requisição de Commercial Passport inválida",
            detail="audience deve ser texto não vazio.",
        )
    _validate_temporal_coordinates(body.reference_time, body.knowledge_cutoff)
    if issuance_pipeline is None:
        return _not_enabled_response(
            reason_code="COMMERCIAL_PASSPORT_ISSUANCE_NAO_HABILITADA",
            detail="A emissão formal do Commercial Passport ainda não está habilitada.",
        )

    issued_at = datetime.now(UTC)
    try:
        issuance = issuance_pipeline.issue_property_passport(
            context=CommercialPassportContext(
                organization_id=context.organization_id,
                property_id=property_ref,
                reference_time=body.reference_time,
                knowledge_cutoff=body.knowledge_cutoff,
                evaluated_at=issued_at,
            ),
            audience=body.audience,
            issued_at=issued_at,
        )
    except ValueError as error:
        raise DomainProblem(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            reason_code="COMMERCIAL_PASSPORT_REQUEST_INVALIDA",
            title="Requisição de Commercial Passport inválida",
            detail=str(error),
        ) from error

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        headers=dict(MARKET_SUPPLY_NO_STORE_HEADERS),
        content={
            "property_id": str(property_ref.value),
            "dossier_id": str(issuance.dossier.dossier_id.value),
            "dossier_hash": issuance.dossier.dossier_hash,
            "verification_bundle_id": str(issuance.verification_bundle.manifest.bundle_id.value),
            "verification_manifest_digest": (issuance.verification_bundle.manifest.manifest_digest),
            "issued_at": issued_at.isoformat(),
            "audience": body.audience,
        },
    )


def _validate_temporal_coordinates(reference_time: datetime, knowledge_cutoff: datetime) -> None:
    for field_name, value in (
        ("reference_time", reference_time),
        ("knowledge_cutoff", knowledge_cutoff),
    ):
        try:
            require_utc(value, field_name=field_name)
        except ValueError as error:
            raise DomainProblem(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                reason_code="TEMPO_NAO_UTC",
                title="Tempo inválido",
                detail=f"O campo {field_name} deve possuir timezone UTC.",
            ) from error
    if knowledge_cutoff < reference_time:
        raise DomainProblem(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            reason_code="COMMERCIAL_PASSPORT_REQUEST_INVALIDA",
            title="Requisição de Commercial Passport inválida",
            detail="knowledge_cutoff não pode ser anterior a reference_time.",
        )


def _not_enabled_response(*, reason_code: str, detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        headers=dict(MARKET_SUPPLY_NO_STORE_HEADERS),
        content={
            "type": f"urn:titan:problema:{reason_code.lower().replace('_', '-')}",
            "title": "Commercial Passport não habilitado",
            "status": status.HTTP_503_SERVICE_UNAVAILABLE,
            "detail": detail,
            "reason_code": reason_code,
        },
        media_type="application/problem+json",
    )
