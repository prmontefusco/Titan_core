"""Queries HTTP read-only da vertical Asset — A5."""

from collections.abc import Mapping
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from apps.api.asset.dependencies import (
    ConnectionDependency,
    require_dashboard_read,
    require_vehicle_read,
    typed_id_or_problem,
)
from apps.api.problem import RESPOSTAS_PADRAO
from packages.asset_application.fleet_view import (
    FleetView,
    FleetViewLine,
    FleetViewService,
)
from packages.asset_application.workshop_dashboard import (
    WorkshopDashboard,
    WorkshopDashboardLine,
    WorkshopDashboardService,
)
from packages.asset_infrastructure.persistence.fleet_view_repository import (
    TransactionalFleetViewRepository,
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


def get_workshop_dashboard_service(
    connection: ConnectionDependency,
) -> WorkshopDashboardService:
    return WorkshopDashboardService(
        repository=TransactionalWorkshopDashboardRepository(connection=connection)
    )


def get_fleet_view_service(connection: ConnectionDependency) -> FleetViewService:
    return FleetViewService(repository=TransactionalFleetViewRepository(connection=connection))


def _typed_optional(raw: str | None, *, entity_type: str, campo: str) -> TypedId | None:
    if raw is None:
        return None
    return typed_id_or_problem(raw, entity_type=entity_type, campo=campo)


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
