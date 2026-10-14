"""HTTP release gate for Commercial Passport.

The Commercial Passport API is deliberately feature-flagged and fail-closed
until the productive evaluation/issuance orchestration is wired. This module
declares the contract and guards the boundary without fabricating passport data
from request payloads.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from os import environ
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, Header, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from apps.api.livestock_dependencies import (
    ConnectionDependency,
    get_engine,
    require_permission,
    typed_id_or_problem,
)
from apps.api.problem import DomainProblem
from packages.core_application import (
    IdempotencyConflict,
    IdempotencyRequest,
    IdempotencyResultUnknown,
    IdempotencyService,
)
from packages.core_domain import CanonicalPayload, OrganizationContext
from packages.core_infrastructure.persistence.idempotency import IdempotencyRepository
from packages.core_infrastructure.persistence.organizations import set_local_organization_context
from packages.livestock_application.authorization import DOSSIER_LER, PROPERTY_LER
from packages.livestock_application.commercial_passport import (
    CommercialOpportunity,
    CommercialOpportunityKind,
    CommercialPassport,
    CommercialPassportContext,
    PropertyCommercialPassportIssuancePort,
    PropertyCommercialPassportProjectionPort,
    commercial_passport_projection,
)
from packages.livestock_application.market_supply_response import MARKET_SUPPLY_NO_STORE_HEADERS
from packages.livestock_infrastructure.persistence.commercial_passport import (
    TransactionalPropertyCommercialPassportIssuancePipeline,
    TransactionalPropertyCommercialPassportReadinessPipeline,
)
from packages.shared_kernel import TypedId, UniversalReference
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
    """Compose the opt-in dynamic pipeline for the HTTP app.

    This keeps the public route default-off even when the API route itself is
    feature-flagged on. Configuration selects the commercial opportunity; the
    adapter still reads only canonical persisted material from the active
    request transaction.
    """

    if environ.get("TITAN_COMMERCIAL_PASSPORT_PIPELINE_ENABLED", "").casefold() != "true":
        return None
    opportunity = _configured_commercial_opportunity()
    if opportunity is None:
        return None
    return _ConfiguredCommercialPassportProjectionPipeline(opportunity=opportunity)


def get_commercial_passport_issuance_pipeline(
    connection: ConnectionDependency,
) -> PropertyCommercialPassportIssuancePort | None:
    if environ.get("TITAN_COMMERCIAL_PASSPORT_ISSUANCE_ENABLED", "").casefold() != "true":
        return None
    if environ.get("TITAN_COMMERCIAL_PASSPORT_ISSUANCE_PROFILE", "").strip() != (
        "INTERNAL_SYNTHETIC"
    ):
        return None
    opportunity = _configured_commercial_opportunity()
    if opportunity is None:
        return None
    return TransactionalPropertyCommercialPassportIssuancePipeline(
        connection=connection,
        opportunity=opportunity,
    )


def get_commercial_passport_idempotency_service(
    connection: ConnectionDependency,
) -> IdempotencyService:
    return IdempotencyService(IdempotencyRepository(connection))


@dataclass(frozen=True, slots=True)
class _ConfiguredCommercialPassportProjectionPipeline(PropertyCommercialPassportProjectionPort):
    opportunity: CommercialOpportunity

    def build_property_passport(
        self,
        *,
        context: CommercialPassportContext,
    ) -> CommercialPassport:
        with get_engine().connect() as connection, connection.begin():
            set_local_organization_context(connection, context.organization_id)
            return TransactionalPropertyCommercialPassportReadinessPipeline(
                connection=connection,
                opportunity=self.opportunity,
            ).build_property_passport(context=context)


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
        raise _commercial_passport_problem(
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
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1)],
    idempotency_service: Annotated[
        IdempotencyService,
        Depends(get_commercial_passport_idempotency_service),
    ],
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
        raise _commercial_passport_problem(
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

    intent = CanonicalPayload(
        schema="titan.livestock.commercial_passport.issue_intent",
        version=1,
        value={
            "property_id": str(property_ref.value),
            "reference_time": body.reference_time,
            "knowledge_cutoff": body.knowledge_cutoff,
            "audience": body.audience,
        },
    )
    try:
        idempotency_request = IdempotencyRequest(
            key=idempotency_key,
            organization_id=context.organization_id,
            principal_reference=UniversalReference(
                target_id=context.user_id,
                organization_id=context.organization_id,
                contract_version=1,
            ),
            purpose="COMMERCIAL_PASSPORT_ISSUE",
            operation="livestock.commercial_passport.issue",
            intent_digest=hashlib.sha256(intent.canonical_bytes).digest(),
            requested_at=datetime.now(UTC),
        )
    except ValueError as error:
        raise _commercial_passport_problem(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            reason_code="IDEMPOTENCY_KEY_INVALIDA",
            title="Chave de idempotência inválida",
            detail=str(error),
        ) from error

    def _issue() -> CanonicalPayload:
        issued_at = datetime.now(UTC)
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
        return CanonicalPayload(
            schema="titan.livestock.commercial_passport.issue_result",
            version=1,
            value={
                "property_id": str(property_ref.value),
                "dossier_id": str(issuance.dossier.dossier_id.value),
                "dossier_hash": issuance.dossier.dossier_hash,
                "verification_bundle_id": str(
                    issuance.verification_bundle.manifest.bundle_id.value
                ),
                "verification_manifest_digest": (
                    issuance.verification_bundle.manifest.manifest_digest
                ),
                "issued_at": issued_at,
                "audience": body.audience,
            },
        )

    try:
        execution = idempotency_service.execute(idempotency_request, _issue)
        content = _canonical_result_data(execution.result_canonical_bytes)
    except ValueError as error:
        raise _commercial_passport_problem(
            status_code=status.HTTP_409_CONFLICT,
            reason_code="COMMERCIAL_PASSPORT_MATERIAL_AUTORITATIVO_INVALIDO",
            title="Material autoritativo indisponível para emissão",
            detail=str(error),
        ) from error
    except IdempotencyConflict as error:
        raise _commercial_passport_problem(
            status_code=status.HTTP_409_CONFLICT,
            reason_code="IDEMPOTENCY_KEY_COM_INTENCAO_DIVERGENTE",
            title="Conflito de idempotência",
            detail=str(error),
        ) from error
    except IdempotencyResultUnknown as error:
        raise _commercial_passport_problem(
            status_code=status.HTTP_409_CONFLICT,
            reason_code="RESULTADO_IDEMPOTENTE_DESCONHECIDO",
            title="Resultado idempotente indisponível",
            detail=str(error),
        ) from error

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        headers=dict(MARKET_SUPPLY_NO_STORE_HEADERS),
        content=content,
    )


def _canonical_result_data(canonical_bytes: bytes) -> dict[str, Any]:
    envelope = json.loads(canonical_bytes.decode("utf-8"))
    decoded = _decode_canonical_value(envelope[1])
    if not isinstance(decoded, dict) or not isinstance(decoded.get("data"), dict):
        raise RuntimeError("Resultado canônico da emissão é inválido.")
    return cast(dict[str, Any], decoded["data"])


def _decode_canonical_value(value: object) -> Any:
    if not isinstance(value, list) or len(value) != 2:
        raise RuntimeError("Valor canônico inválido.")
    tag, raw = value
    if tag == "map":
        return {key: _decode_canonical_value(item) for key, item in raw}
    if tag == "list":
        return [_decode_canonical_value(item) for item in raw]
    if tag in {"string", "datetime"}:
        return raw
    if tag == "integer":
        return int(raw)
    if tag == "boolean":
        return raw == "true"
    if tag == "null":
        return None
    raise RuntimeError(f"Tipo canônico não suportado: {tag}")


def _validate_temporal_coordinates(reference_time: datetime, knowledge_cutoff: datetime) -> None:
    for field_name, value in (
        ("reference_time", reference_time),
        ("knowledge_cutoff", knowledge_cutoff),
    ):
        try:
            require_utc(value, field_name=field_name)
        except ValueError as error:
            raise _commercial_passport_problem(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                reason_code="TEMPO_NAO_UTC",
                title="Tempo inválido",
                detail=f"O campo {field_name} deve possuir timezone UTC.",
            ) from error
    if knowledge_cutoff < reference_time:
        raise _commercial_passport_problem(
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


def _commercial_passport_problem(
    *,
    status_code: int,
    reason_code: str,
    title: str,
    detail: str,
) -> DomainProblem:
    return DomainProblem(
        status_code=status_code,
        reason_code=reason_code,
        title=title,
        detail=detail,
        headers=dict(MARKET_SUPPLY_NO_STORE_HEADERS),
    )


def _configured_commercial_opportunity() -> CommercialOpportunity | None:
    code = environ.get("TITAN_COMMERCIAL_PASSPORT_OPPORTUNITY_CODE", "").strip()
    name = environ.get("TITAN_COMMERCIAL_PASSPORT_OPPORTUNITY_NAME", "").strip()
    purpose = environ.get("TITAN_COMMERCIAL_PASSPORT_PURPOSE", "").strip()
    policy_id = environ.get("TITAN_COMMERCIAL_PASSPORT_POLICY_ID", "").strip()
    policy_version = environ.get("TITAN_COMMERCIAL_PASSPORT_POLICY_VERSION", "").strip()
    kind = environ.get("TITAN_COMMERCIAL_PASSPORT_OPPORTUNITY_KIND", "MARKET").strip()
    if not all((code, name, purpose, policy_id, policy_version)):
        return None
    try:
        version = int(policy_version)
        opportunity_kind = CommercialOpportunityKind(kind)
        policy_ref = TypedId.parse("policy", policy_id)
        return CommercialOpportunity(
            code=code,
            kind=opportunity_kind,
            name=name,
            purpose=purpose,
            policy_id=policy_ref,
            policy_version=version,
        )
    except ValueError:
        return None
