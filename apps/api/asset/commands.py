"""Comandos HTTP da vertical Asset/Sustainment — A5."""

import hashlib
import json
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, status
from pydantic import BaseModel, Field

from apps.api.asset.dependencies import ConnectionDependency, require_work_order_open
from apps.api.asset.queries import (
    WorkOrderDetailResponse,
    _work_order_detail,
    get_contract_context_query_service,
)
from apps.api.problem import RESPOSTAS_PADRAO, DomainProblem
from packages.asset_application.contract_context_query import (
    ContractContextAmbiguo,
    ContractContextNaoEncontrado,
    ContractContextQueryService,
)
from packages.asset_application.event_recorder import AssetEventRecorder, AssetOperationContext
from packages.asset_application.inventory_service import InventoryService
from packages.asset_application.vehicle_service import VehicleNaoEncontrado, VehicleService
from packages.asset_application.work_order_service import (
    SLIContractNaoEncontradoParaWorkOrder,
    WorkOrderService,
)
from packages.asset_domain.work_order import FailureRecord
from packages.asset_infrastructure.persistence.inventory_repository import (
    TransactionalStockPositionRepository,
    TransactionalStockReservationRepository,
    TransactionalStockTransferRepository,
)
from packages.asset_infrastructure.persistence.sustainment_contract_repository import (
    TransactionalSLIContractRepository,
)
from packages.asset_infrastructure.persistence.vehicle_repository import (
    TransactionalVehicleRepository,
)
from packages.asset_infrastructure.persistence.work_order_repository import (
    TransactionalWorkOrderRepository,
)
from packages.core_application import (
    IdempotencyConflict,
    IdempotencyRequest,
    IdempotencyResultUnknown,
    IdempotencyService,
)
from packages.core_domain import CanonicalPayload, OrganizationContext
from packages.core_infrastructure.persistence.events import DomainEventRepository
from packages.core_infrastructure.persistence.idempotency import IdempotencyRepository
from packages.shared_kernel import CanonicalSerializer, SystemClock, TypedId, UniversalReference
from packages.shared_kernel.serialization import CanonicalValue
from packages.shared_kernel.temporal import require_utc

IDEMPOTENCY_HEADER = "Idempotency-Key"
OPEN_WORK_ORDER_PURPOSE = "SUSTAINMENT_WO_OPEN"
OPEN_WORK_ORDER_OPERATION = "asset.work_order.open"

router = APIRouter(prefix="/v1/asset", tags=["asset"])


class OpenWorkOrderRequest(BaseModel):
    vehicle_id: str = Field(description="Vehicle para o qual a WorkOrder será aberta.")
    at_instant: datetime = Field(description="Instante UTC de resolução do contrato aplicável.")
    failure_mode: str = Field(min_length=1, max_length=200)
    failure_reported_at: datetime
    failure_affected_position: str | None = Field(default=None, max_length=100)


def get_open_work_order_service(connection: ConnectionDependency) -> WorkOrderService:
    event_log = DomainEventRepository(connection=connection)
    recorder = AssetEventRecorder(event_log=event_log, clock=SystemClock())
    vehicle_repository = TransactionalVehicleRepository(connection=connection)
    return WorkOrderService(
        repository=TransactionalWorkOrderRepository(connection=connection),
        sli_contract_repository=TransactionalSLIContractRepository(connection=connection),
        vehicle_service=VehicleService(repository=vehicle_repository, recorder=recorder),
        inventory_service=InventoryService(
            stock_position_repository=TransactionalStockPositionRepository(connection=connection),
            stock_reservation_repository=TransactionalStockReservationRepository(
                connection=connection
            ),
            stock_transfer_repository=TransactionalStockTransferRepository(connection=connection),
            recorder=recorder,
        ),
        recorder=recorder,
    )


def get_idempotency_service(connection: ConnectionDependency) -> IdempotencyService:
    return IdempotencyService(IdempotencyRepository(connection))


@router.post(
    "/work-orders",
    response_model=WorkOrderDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Abrir uma WorkOrder",
    responses=RESPOSTAS_PADRAO,
)
def abrir_work_order(
    body: OpenWorkOrderRequest,
    contexto: Annotated[OrganizationContext, Depends(require_work_order_open)],
    idempotency_key: Annotated[str, Header(alias=IDEMPOTENCY_HEADER, min_length=1)],
    service: Annotated[WorkOrderService, Depends(get_open_work_order_service)],
    contract_context_service: Annotated[
        ContractContextQueryService, Depends(get_contract_context_query_service)
    ],
    idempotency_service: Annotated[IdempotencyService, Depends(get_idempotency_service)],
) -> WorkOrderDetailResponse:
    vehicle_id = _typed_id_or_problem(body.vehicle_id, entity_type="vehicle", campo="vehicle_id")
    _require_utc_or_problem(body.at_instant, field_name="at_instant")
    _require_utc_or_problem(body.failure_reported_at, field_name="failure_reported_at")

    request = _idempotency_request(
        body=body,
        contexto=contexto,
        idempotency_key=idempotency_key,
        requested_at=datetime.now(UTC),
    )
    operation_context = AssetOperationContext.from_organization_context(
        contexto,
        source_id=TypedId.new("api_request"),
    )

    def _handler() -> CanonicalPayload:
        try:
            resolved_context = contract_context_service.get_context_for_vehicle(
                vehicle_id=vehicle_id,
                instant=body.at_instant,
            )
            if resolved_context.vehicle.site_ref is None:
                raise ValueError("OpenWorkOrder exige Vehicle vinculado a CustomerSite (I-SEC-2).")
            work_order = service.open_work_order(
                operation_context,
                vehicle_ref=vehicle_id,
                site_ref=resolved_context.vehicle.site_ref,
                contract_ref=resolved_context.contract.contract_id,
                failure=FailureRecord(
                    mode=body.failure_mode,
                    reported_at=body.failure_reported_at,
                    affected_position=body.failure_affected_position,
                ),
                at_instant=body.at_instant,
                occurred_at=datetime.now(UTC),
            )
        except (VehicleNaoEncontrado, ContractContextNaoEncontrado) as exc:
            raise _not_found(str(exc)) from exc
        except (ContractContextAmbiguo, ValueError) as exc:
            raise _domain_conflict(str(exc)) from exc
        except SLIContractNaoEncontradoParaWorkOrder as exc:
            raise _not_found(str(exc)) from exc
        response = _work_order_detail(work_order)
        return CanonicalPayload(
            schema="asset.open_work_order.response",
            version=1,
            value=response.model_dump(mode="json"),
        )

    try:
        execution = idempotency_service.execute(request, _handler)
    except ValueError as exc:
        raise DomainProblem(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            reason_code="IDEMPOTENCY_KEY_INVALIDA",
            title="Idempotency-Key inválida",
            detail=str(exc),
        ) from exc
    except IdempotencyConflict as exc:
        raise DomainProblem(
            status_code=status.HTTP_409_CONFLICT,
            reason_code="IDEMPOTENCY_KEY_COM_INTENCAO_DIVERGENTE",
            title="Conflito de idempotência",
            detail=str(exc),
        ) from exc
    except IdempotencyResultUnknown as exc:
        raise DomainProblem(
            status_code=status.HTTP_409_CONFLICT,
            reason_code="RESULTADO_IDEMPOTENTE_DESCONHECIDO",
            title="Resultado idempotente desconhecido",
            detail=str(exc),
        ) from exc

    return WorkOrderDetailResponse.model_validate(
        _canonical_response_data(execution.result_canonical_bytes)
    )


def _typed_id_or_problem(value: str, *, entity_type: str, campo: str) -> TypedId:
    try:
        return TypedId.parse(entity_type, value)
    except ValueError as exc:
        raise DomainProblem(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            reason_code="IDENTIFICADOR_INVALIDO",
            title="Identificador inválido",
            detail=f"O campo {campo} deve ser um UUID válido.",
        ) from exc


def _require_utc_or_problem(value: datetime, *, field_name: str) -> None:
    try:
        require_utc(value, field_name=field_name)
    except ValueError as exc:
        raise DomainProblem(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            reason_code="DATA_INVALIDA",
            title="Data inválida",
            detail=f"O campo {field_name} deve estar em UTC.",
        ) from exc


def _idempotency_request(
    *,
    body: OpenWorkOrderRequest,
    contexto: OrganizationContext,
    idempotency_key: str,
    requested_at: datetime,
) -> IdempotencyRequest:
    return IdempotencyRequest(
        key=idempotency_key,
        organization_id=contexto.organization_id,
        principal_reference=UniversalReference(
            target_id=contexto.user_id,
            organization_id=contexto.organization_id,
            contract_version=1,
        ),
        purpose=OPEN_WORK_ORDER_PURPOSE,
        operation=OPEN_WORK_ORDER_OPERATION,
        intent_digest=_intent_digest(body),
        requested_at=requested_at,
    )


def _intent_digest(body: OpenWorkOrderRequest) -> bytes:
    value: dict[str, CanonicalValue] = {
        "vehicle_id": body.vehicle_id,
        "at_instant": body.at_instant,
        "failure_mode": body.failure_mode,
        "failure_reported_at": body.failure_reported_at,
        "failure_affected_position": body.failure_affected_position,
    }
    return hashlib.sha256(CanonicalSerializer().serialize(value)).digest()


def _not_found(detail: str) -> DomainProblem:
    return DomainProblem(
        status_code=status.HTTP_404_NOT_FOUND,
        reason_code="RECURSO_NAO_ENCONTRADO",
        title="Recurso não encontrado",
        detail=detail,
    )


def _domain_conflict(detail: str) -> DomainProblem:
    return DomainProblem(
        status_code=status.HTTP_409_CONFLICT,
        reason_code="CONFLITO_DE_DOMINIO",
        title="Operação recusada pelo domínio",
        detail=detail,
    )


def _canonical_response_data(canonical_bytes: bytes) -> dict[str, object]:
    payload = json.loads(canonical_bytes.decode("utf-8"))
    data = _decode_canonical_payload(payload).get("data")
    if not isinstance(data, dict):
        raise RuntimeError("Resposta canônica de OpenWorkOrder inválida.")
    return data


def _decode_canonical_payload(payload: object) -> dict[str, Any]:
    if not isinstance(payload, list) or len(payload) != 2 or payload[0] != "titan-json-v1":
        raise RuntimeError("Payload canônico inválido.")
    value = _decode_canonical_value(payload[1])
    if not isinstance(value, dict):
        raise RuntimeError("Envelope canônico inválido.")
    return value


def _decode_canonical_value(value: object) -> Any:
    if not isinstance(value, list) or not value:
        raise RuntimeError("Valor canônico inválido.")
    tag = value[0]
    if tag == "null":
        if len(value) != 1:
            raise RuntimeError("Null canônico inválido.")
        return None
    if len(value) != 2:
        raise RuntimeError("Valor canônico inválido.")
    raw = value[1]
    if tag == "map":
        if not isinstance(raw, list):
            raise RuntimeError("Mapa canônico inválido.")
        decoded: dict[str, Any] = {}
        for pair in raw:
            if not isinstance(pair, list) or len(pair) != 2 or not isinstance(pair[0], str):
                raise RuntimeError("Entrada de mapa canônico inválida.")
            decoded[pair[0]] = _decode_canonical_value(pair[1])
        return decoded
    if tag == "list":
        if not isinstance(raw, list):
            raise RuntimeError("Lista canônica inválida.")
        return [_decode_canonical_value(item) for item in raw]
    if tag in {"string", "datetime", "decimal"}:
        return raw
    if tag == "integer":
        return int(raw)
    if tag == "boolean":
        return raw == "true"
    raise RuntimeError(f"Tipo canônico não suportado para resposta HTTP: {tag}")
