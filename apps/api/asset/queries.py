"""Queries HTTP read-only da vertical Asset — A5."""

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel

from apps.api.asset.dependencies import (
    ConnectionDependency,
    require_contract_read,
    require_dashboard_read,
    require_vehicle_read,
    require_work_order_read,
    typed_id_or_problem,
)
from apps.api.problem import RESPOSTAS_PADRAO, DomainProblem
from packages.asset_application.contract_sla_summary import (
    ContractSLASummary,
    ContractSLASummaryService,
    ContractSLAWorkOrderLine,
    SLIContractSummaryNaoEncontrado,
)
from packages.asset_application.fleet_view import (
    FleetView,
    FleetViewLine,
    FleetViewService,
)
from packages.asset_application.vehicle_query import (
    VehicleDetailNaoEncontrado,
    VehicleQueryService,
)
from packages.asset_application.work_order_query import (
    WorkOrderDetailNaoEncontrado,
    WorkOrderQueryService,
)
from packages.asset_application.workshop_dashboard import (
    WorkshopDashboard,
    WorkshopDashboardLine,
    WorkshopDashboardService,
)
from packages.asset_domain.vehicle import MeterCorrection, MeterReading, Vehicle
from packages.asset_domain.work_order import (
    MaterialDemand,
    RemovedComponentDisposition,
    WorkOrder,
    WorkTask,
)
from packages.asset_infrastructure.persistence.contract_sla_summary_repository import (
    TransactionalContractSLASummaryRepository,
)
from packages.asset_infrastructure.persistence.fleet_view_repository import (
    TransactionalFleetViewRepository,
)
from packages.asset_infrastructure.persistence.vehicle_repository import (
    TransactionalVehicleRepository,
)
from packages.asset_infrastructure.persistence.work_order_repository import (
    TransactionalWorkOrderRepository,
)
from packages.asset_infrastructure.persistence.workshop_dashboard_repository import (
    TransactionalWorkshopDashboardRepository,
)
from packages.core_domain import OrganizationContext
from packages.shared_kernel import TypedId

router = APIRouter(prefix="/v1/asset", tags=["asset"])


class WorkshopDashboardLineResponse(BaseModel):
    work_order_id: str
    vehicle_ref: str
    site_ref: str
    workshop_ref: str | None
    state: str
    priority_score: int
    priority_breakdown: dict[str, int]
    priority_evaluation_ref: str | None
    blockers: list[str]
    next_action: str


class WorkshopDashboardResponse(BaseModel):
    site_ref: str
    workshop_ref: str | None
    lines: list[WorkshopDashboardLineResponse]


class FleetViewLineResponse(BaseModel):
    vehicle_id: str
    site_ref: str | None
    lifecycle_state: str
    operational_state: str
    open_work_order_refs: list[str]
    signals: list[str]


class FleetViewResponse(BaseModel):
    site_ref: str | None
    counts_by_state: dict[str, int]
    lines: list[FleetViewLineResponse]


class ContractSLAWorkOrderLineResponse(BaseModel):
    work_order_id: str
    vehicle_ref: str
    state: str
    priority_score: int | None
    signals: list[str]


class ContractSLASummaryResponse(BaseModel):
    contract_ref: str
    contract_version_no: int | None
    covered_vehicle_count: int
    open_work_order_count: int
    waiting_material_count: int
    waiting_authorization_count: int
    sla_risk_count: int
    response_sla_duration_seconds: int | None
    repair_sla_duration_seconds: int | None
    lines: list[ContractSLAWorkOrderLineResponse]


class ContractContextResponse(BaseModel):
    contract_ref: str
    contract_version_no: int
    resolved_at: datetime


class FailureRecordResponse(BaseModel):
    mode: str
    reported_at: datetime
    affected_position: str | None


class WorkTaskResponse(BaseModel):
    task_id: str
    description: str
    mandatory: bool
    state: str
    labor_entries: list[str]


class MaterialDemandResponse(BaseModel):
    part_ref: str
    qty: str
    task_id: str


class RemovedComponentResponse(BaseModel):
    part_ref: str
    disposition: str
    serial: str | None


class PriorityScoreResponse(BaseModel):
    score: int
    breakdown: dict[str, int]
    evaluation_ref: str | None


class PostMaintenanceValidationResponse(BaseModel):
    validated_at: datetime
    validator_ref: str
    result: str
    notes: str | None


class WorkOrderDetailResponse(BaseModel):
    work_order_id: str
    vehicle_ref: str
    site_ref: str
    workshop_ref: str | None
    state: str
    pre_wait_authorization_state: str | None
    contract_context: ContractContextResponse
    failure: FailureRecordResponse
    tasks: list[WorkTaskResponse]
    material_demands: list[MaterialDemandResponse]
    material_reservations: list[str]
    priority: PriorityScoreResponse | None
    diagnosis: str | None
    root_cause: str | None
    resolution: str | None
    removed_components: list[RemovedComponentResponse]
    validation: PostMaintenanceValidationResponse | None
    version: int
    created_at: datetime


class VehicleIdentifiersResponse(BaseModel):
    serial_number: str
    chassis: str | None
    fleet_number: str | None


class MeterReadingResponse(BaseModel):
    reading_id: str
    kind: str
    value: str
    observed_at: datetime
    recorded_at: datetime
    source: str


class MeterCorrectionResponse(BaseModel):
    correction_id: str
    original_reading_id: str
    corrected_value: str
    reason: str
    corrected_at: datetime


class VehicleDetailResponse(BaseModel):
    vehicle_id: str
    model_ref: str
    identifiers: VehicleIdentifiersResponse
    ownership: str
    variant_ref: str | None
    site_ref: str | None
    current_baseline_ref: str | None
    baseline_valid_from: datetime | None
    lifecycle_state: str
    meter_readings: list[MeterReadingResponse]
    meter_corrections: list[MeterCorrectionResponse]
    version: int
    created_at: datetime


def get_workshop_dashboard_service(
    connection: ConnectionDependency,
) -> WorkshopDashboardService:
    return WorkshopDashboardService(
        repository=TransactionalWorkshopDashboardRepository(connection=connection)
    )


def get_fleet_view_service(connection: ConnectionDependency) -> FleetViewService:
    return FleetViewService(repository=TransactionalFleetViewRepository(connection=connection))


def get_vehicle_query_service(connection: ConnectionDependency) -> VehicleQueryService:
    return VehicleQueryService(repository=TransactionalVehicleRepository(connection=connection))


def get_contract_sla_summary_service(
    connection: ConnectionDependency,
) -> ContractSLASummaryService:
    return ContractSLASummaryService(
        repository=TransactionalContractSLASummaryRepository(connection=connection)
    )


def get_work_order_query_service(connection: ConnectionDependency) -> WorkOrderQueryService:
    return WorkOrderQueryService(repository=TransactionalWorkOrderRepository(connection=connection))


def _typed_optional(raw: str | None, *, entity_type: str, campo: str) -> TypedId | None:
    if raw is None:
        return None
    return typed_id_or_problem(raw, entity_type=entity_type, campo=campo)


def _utc_optional(raw: datetime | None, *, campo: str) -> datetime | None:
    if raw is None:
        return None
    if raw.tzinfo is None or raw.utcoffset() != UTC.utcoffset(raw):
        raise DomainProblem(
            status_code=422,
            reason_code="DATA_INVALIDA",
            title="Data inválida",
            detail=f"{campo} deve estar em UTC.",
        )
    return raw


def _mapping_to_dict(value: Mapping[str, int]) -> dict[str, int]:
    return {key: item for key, item in value.items()}


def _dashboard_line(line: WorkshopDashboardLine) -> WorkshopDashboardLineResponse:
    return WorkshopDashboardLineResponse(
        work_order_id=str(line.work_order_id.value),
        vehicle_ref=str(line.vehicle_ref.value),
        site_ref=str(line.site_ref.value),
        workshop_ref=None if line.workshop_ref is None else str(line.workshop_ref.value),
        state=line.state.value,
        priority_score=line.priority_score,
        priority_breakdown=_mapping_to_dict(line.priority_breakdown),
        priority_evaluation_ref=(
            None
            if line.priority_evaluation_ref is None
            else str(line.priority_evaluation_ref.value)
        ),
        blockers=list(line.blockers),
        next_action=line.next_action,
    )


def _dashboard(response: WorkshopDashboard) -> WorkshopDashboardResponse:
    return WorkshopDashboardResponse(
        site_ref=str(response.site_ref.value),
        workshop_ref=None if response.workshop_ref is None else str(response.workshop_ref.value),
        lines=[_dashboard_line(line) for line in response.lines],
    )


def _fleet_line(line: FleetViewLine) -> FleetViewLineResponse:
    return FleetViewLineResponse(
        vehicle_id=str(line.vehicle_id.value),
        site_ref=None if line.site_ref is None else str(line.site_ref.value),
        lifecycle_state=line.lifecycle_state.value,
        operational_state=line.operational_state.value,
        open_work_order_refs=[str(ref.value) for ref in line.open_work_order_refs],
        signals=list(line.signals),
    )


def _fleet_view(response: FleetView) -> FleetViewResponse:
    return FleetViewResponse(
        site_ref=None if response.site_ref is None else str(response.site_ref.value),
        counts_by_state={state.value: count for state, count in response.counts_by_state.items()},
        lines=[_fleet_line(line) for line in response.lines],
    )


def _meter_reading(reading: MeterReading) -> MeterReadingResponse:
    return MeterReadingResponse(
        reading_id=str(reading.reading_id.value),
        kind=reading.kind.value,
        value=str(reading.value),
        observed_at=reading.observed_at,
        recorded_at=reading.recorded_at,
        source=reading.source,
    )


def _meter_correction(correction: MeterCorrection) -> MeterCorrectionResponse:
    return MeterCorrectionResponse(
        correction_id=str(correction.correction_id.value),
        original_reading_id=str(correction.original_reading_id.value),
        corrected_value=str(correction.corrected_value),
        reason=correction.reason,
        corrected_at=correction.corrected_at,
    )


def _vehicle_detail(vehicle: Vehicle) -> VehicleDetailResponse:
    return VehicleDetailResponse(
        vehicle_id=str(vehicle.vehicle_id.value),
        model_ref=str(vehicle.model_ref.value),
        identifiers=VehicleIdentifiersResponse(
            serial_number=vehicle.identifiers.serial_number,
            chassis=vehicle.identifiers.chassis,
            fleet_number=vehicle.identifiers.fleet_number,
        ),
        ownership=vehicle.ownership.value,
        variant_ref=None if vehicle.variant_ref is None else str(vehicle.variant_ref.value),
        site_ref=None if vehicle.site_ref is None else str(vehicle.site_ref.value),
        current_baseline_ref=(
            None
            if vehicle.current_baseline_ref is None
            else str(vehicle.current_baseline_ref.value)
        ),
        baseline_valid_from=vehicle.baseline_valid_from,
        lifecycle_state=vehicle.lifecycle_state.value,
        meter_readings=[_meter_reading(reading) for reading in vehicle.meter_readings],
        meter_corrections=[
            _meter_correction(correction) for correction in vehicle.meter_corrections
        ],
        version=vehicle.version,
        created_at=vehicle.created_at,
    )


def _contract_sla_line(line: ContractSLAWorkOrderLine) -> ContractSLAWorkOrderLineResponse:
    return ContractSLAWorkOrderLineResponse(
        work_order_id=str(line.work_order_id.value),
        vehicle_ref=str(line.vehicle_ref.value),
        state=line.state.value,
        priority_score=line.priority_score,
        signals=[signal.value for signal in line.signals],
    )


def _contract_sla_summary(response: ContractSLASummary) -> ContractSLASummaryResponse:
    return ContractSLASummaryResponse(
        contract_ref=str(response.contract_ref.value),
        contract_version_no=response.contract_version_no,
        covered_vehicle_count=response.covered_vehicle_count,
        open_work_order_count=response.open_work_order_count,
        waiting_material_count=response.waiting_material_count,
        waiting_authorization_count=response.waiting_authorization_count,
        sla_risk_count=response.sla_risk_count,
        response_sla_duration_seconds=response.response_sla_duration_seconds,
        repair_sla_duration_seconds=response.repair_sla_duration_seconds,
        lines=[_contract_sla_line(line) for line in response.lines],
    )


def _work_task(task: WorkTask) -> WorkTaskResponse:
    return WorkTaskResponse(
        task_id=str(task.task_id.value),
        description=task.description,
        mandatory=task.mandatory,
        state=task.state.value,
        labor_entries=list(task.labor_entries),
    )


def _material_demand(demand: MaterialDemand) -> MaterialDemandResponse:
    return MaterialDemandResponse(
        part_ref=str(demand.part_ref.value),
        qty=str(demand.qty),
        task_id=str(demand.task_id.value),
    )


def _removed_component(component: RemovedComponentDisposition) -> RemovedComponentResponse:
    return RemovedComponentResponse(
        part_ref=str(component.part_ref.value),
        disposition=component.disposition,
        serial=component.serial,
    )


def _work_order_detail(work_order: WorkOrder) -> WorkOrderDetailResponse:
    priority = work_order.priority
    validation = work_order.validation
    return WorkOrderDetailResponse(
        work_order_id=str(work_order.work_order_id.value),
        vehicle_ref=str(work_order.vehicle_ref.value),
        site_ref=str(work_order.site_ref.value),
        workshop_ref=None
        if work_order.workshop_ref is None
        else str(work_order.workshop_ref.value),
        state=work_order.state.value,
        pre_wait_authorization_state=(
            None
            if work_order.pre_wait_authorization_state is None
            else work_order.pre_wait_authorization_state.value
        ),
        contract_context=ContractContextResponse(
            contract_ref=str(work_order.contract_context.contract_ref.value),
            contract_version_no=work_order.contract_context.contract_version_no,
            resolved_at=work_order.contract_context.resolved_at,
        ),
        failure=FailureRecordResponse(
            mode=work_order.failure.mode,
            reported_at=work_order.failure.reported_at,
            affected_position=work_order.failure.affected_position,
        ),
        tasks=[_work_task(task) for task in work_order.tasks],
        material_demands=[_material_demand(demand) for demand in work_order.material_demands],
        material_reservations=[str(ref.value) for ref in work_order.material_reservations],
        priority=(
            None
            if priority is None
            else PriorityScoreResponse(
                score=priority.score,
                breakdown=dict(priority.breakdown),
                evaluation_ref=(
                    None if priority.evaluation_ref is None else str(priority.evaluation_ref.value)
                ),
            )
        ),
        diagnosis=work_order.diagnosis,
        root_cause=work_order.root_cause,
        resolution=work_order.resolution,
        removed_components=[
            _removed_component(component) for component in work_order.removed_components
        ],
        validation=(
            None
            if validation is None
            else PostMaintenanceValidationResponse(
                validated_at=validation.validated_at,
                validator_ref=str(validation.validator_ref.value),
                result=validation.result.value,
                notes=validation.notes,
            )
        ),
        version=work_order.version,
        created_at=work_order.created_at,
    )


def _contract_not_found() -> DomainProblem:
    return DomainProblem(
        status_code=status.HTTP_404_NOT_FOUND,
        reason_code="RECURSO_NAO_ENCONTRADO",
        title="Recurso não encontrado",
        detail="Contrato SLI não encontrado nesta organização.",
    )


def _work_order_not_found() -> DomainProblem:
    return DomainProblem(
        status_code=status.HTTP_404_NOT_FOUND,
        reason_code="RECURSO_NAO_ENCONTRADO",
        title="Recurso não encontrado",
        detail="Work Order não encontrada nesta organização.",
    )


def _vehicle_not_found() -> DomainProblem:
    return DomainProblem(
        status_code=status.HTTP_404_NOT_FOUND,
        reason_code="RECURSO_NAO_ENCONTRADO",
        title="Recurso não encontrado",
        detail="Vehicle não encontrado nesta organização.",
    )


@router.get(
    "/workshop-dashboard",
    response_model=WorkshopDashboardResponse,
    summary="Consultar o dashboard operacional da oficina",
    description=(
        "Lista Work Orders abertas de um site, opcionalmente filtradas por oficina, "
        "ordenadas pela prioridade explicável e com os bloqueios operacionais já "
        "derivados pelo read model. A projection não é fonte de verdade."
    ),
    responses=RESPOSTAS_PADRAO,
)
def consultar_workshop_dashboard(
    site_id: str,
    contexto: Annotated[OrganizationContext, Depends(require_dashboard_read)],
    service: Annotated[WorkshopDashboardService, Depends(get_workshop_dashboard_service)],
    workshop_id: str | None = None,
) -> Any:
    site_ref = typed_id_or_problem(site_id, entity_type="customer_site", campo="site_id")
    workshop_ref = _typed_optional(workshop_id, entity_type="workshop", campo="workshop_id")
    _ = contexto
    return _dashboard(service.get_dashboard(site_ref=site_ref, workshop_ref=workshop_ref))


@router.get(
    "/fleet-view",
    response_model=FleetViewResponse,
    summary="Consultar a visão operacional da frota",
    description=(
        "Lista veículos da frota, opcionalmente filtrados por site, com estado "
        "operacional derivado do ciclo de vida do veículo e das Work Orders abertas. "
        "A projection é leitura derivada, não fonte de verdade."
    ),
    responses=RESPOSTAS_PADRAO,
)
def consultar_fleet_view(
    contexto: Annotated[OrganizationContext, Depends(require_vehicle_read)],
    service: Annotated[FleetViewService, Depends(get_fleet_view_service)],
    site_id: str | None = None,
) -> Any:
    site_ref = _typed_optional(site_id, entity_type="customer_site", campo="site_id")
    _ = contexto
    return _fleet_view(service.get_fleet_view(site_ref=site_ref))


@router.get(
    "/vehicles/{vehicle_id}",
    response_model=VehicleDetailResponse,
    summary="Consultar detalhe de um veículo",
    description=(
        "Abre o detalhe de um veículo com identificadores, estado de ciclo de vida, "
        "site, baseline vigente e histórico de leituras/correções de medidor."
    ),
    responses=RESPOSTAS_PADRAO | {404: {"description": "Vehicle não encontrado"}},
)
def consultar_vehicle(
    vehicle_id: str,
    contexto: Annotated[OrganizationContext, Depends(require_vehicle_read)],
    service: Annotated[VehicleQueryService, Depends(get_vehicle_query_service)],
) -> Any:
    vehicle_ref = typed_id_or_problem(vehicle_id, entity_type="vehicle", campo="vehicle_id")
    _ = contexto
    try:
        return _vehicle_detail(service.get_vehicle(vehicle_ref))
    except VehicleDetailNaoEncontrado as exc:
        raise _vehicle_not_found() from exc


@router.get(
    "/contract-sla-summary",
    response_model=ContractSLASummaryResponse,
    summary="Consultar o resumo de SLA de um contrato SLI",
    description=(
        "Agrega frota coberta, Work Orders abertas e sinais operacionais de SLA "
        "sob um contrato. A projection é leitura derivada e não calcula violação "
        "contratual real sem relógios de SLA suficientes."
    ),
    responses=RESPOSTAS_PADRAO | {404: {"description": "Contrato não encontrado"}},
)
def consultar_contract_sla_summary(
    contract_id: str,
    contexto: Annotated[OrganizationContext, Depends(require_contract_read)],
    service: Annotated[ContractSLASummaryService, Depends(get_contract_sla_summary_service)],
    as_of: datetime | None = None,
) -> Any:
    contract_ref = typed_id_or_problem(contract_id, entity_type="sli_contract", campo="contract_id")
    as_of_utc = _utc_optional(as_of, campo="as_of")
    _ = contexto
    try:
        return _contract_sla_summary(
            service.get_contract_sla_summary(contract_ref=contract_ref, as_of=as_of_utc)
        )
    except SLIContractSummaryNaoEncontrado as exc:
        raise _contract_not_found() from exc


@router.get(
    "/work-orders/{work_order_id}",
    response_model=WorkOrderDetailResponse,
    summary="Consultar detalhe de uma Work Order",
    description=(
        "Abre o detalhe de uma Work Order com tarefas, demandas e reservas de "
        "material, contexto contratual congelado, prioridade explicável e dados "
        "de validação quando existirem."
    ),
    responses=RESPOSTAS_PADRAO | {404: {"description": "Work Order não encontrada"}},
)
def consultar_work_order(
    work_order_id: str,
    contexto: Annotated[OrganizationContext, Depends(require_work_order_read)],
    service: Annotated[WorkOrderQueryService, Depends(get_work_order_query_service)],
) -> Any:
    work_order_ref = typed_id_or_problem(
        work_order_id, entity_type="work_order", campo="work_order_id"
    )
    _ = contexto
    try:
        return _work_order_detail(service.get_work_order(work_order_ref))
    except WorkOrderDetailNaoEncontrado as exc:
        raise _work_order_not_found() from exc
