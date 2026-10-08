"""Comandos HTTP da vertical Asset/Sustainment — A5."""

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError

from apps.api.asset.dependencies import (
    ConnectionDependency,
    require_applicability_assert,
    require_applicability_withdraw,
    require_inventory_adjust,
    require_inventory_open_position,
    require_part_add_revision,
    require_part_edit_interchange,
    require_part_register,
    require_part_supersede,
    require_site_register,
    require_vehicle_correct_meter,
    require_vehicle_record_meter,
    require_vehicle_transition,
    require_work_order_add_task,
    require_work_order_cancel,
    require_work_order_close,
    require_work_order_demand_material,
    require_work_order_execute,
    require_work_order_open,
    require_work_order_record_removal,
    require_work_order_reserve_material,
    require_work_order_tech_complete,
    require_work_order_transition,
    require_work_order_validate,
)
from apps.api.asset.queries import (
    VehicleDetailResponse,
    WorkOrderDetailResponse,
    _vehicle_detail,
    _work_order_detail,
    get_contract_context_query_service,
)
from apps.api.problem import RESPOSTAS_PADRAO, DomainProblem
from packages.asset_application.applicability_service import (
    ApplicabilityNaoEncontrada,
    ApplicabilityService,
    AssercaoOriginalNaoEncontrada,
)
from packages.asset_application.contract_context_query import (
    ContractContextAmbiguo,
    ContractContextNaoEncontrado,
    ContractContextQueryService,
)
from packages.asset_application.customer_site_service import CustomerSiteService
from packages.asset_application.entitlement_service import (
    EntitlementOutcome,
    EntitlementResolution,
)
from packages.asset_application.event_recorder import AssetEventRecorder, AssetOperationContext
from packages.asset_application.interchangeability_group_service import (
    InterchangeabilityGroupNaoEncontrado,
    InterchangeabilityGroupService,
)
from packages.asset_application.inventory_service import (
    InventoryService,
    StockPositionNaoEncontrada,
)
from packages.asset_application.part_service import PartNaoEncontrado, PartService
from packages.asset_application.vehicle_service import VehicleNaoEncontrado, VehicleService
from packages.asset_application.work_order_service import (
    SLIContractNaoEncontradoParaWorkOrder,
    WorkOrderNaoEncontrada,
    WorkOrderService,
)
from packages.asset_domain.applicability import Applicability, ApplicabilityTarget
from packages.asset_domain.customer_site import CustomerSite, CustomerSiteKind, SiteContact
from packages.asset_domain.events import SUSTAINMENT_ENTITLEMENT_RESOLVED
from packages.asset_domain.inventory import (
    StockOwnership,
    StockPosition,
    StockPurpose,
    StockQuantities,
)
from packages.asset_domain.part import InterchangeabilityGroup, Part, PartIdentity
from packages.asset_domain.vehicle import MeterKind, VehicleLifecycleState
from packages.asset_domain.work_order import FailureRecord
from packages.asset_infrastructure.persistence.applicability_repository import (
    TransactionalApplicabilityRepository,
)
from packages.asset_infrastructure.persistence.customer_site_repository import (
    TransactionalCustomerSiteRepository,
)
from packages.asset_infrastructure.persistence.inventory_repository import (
    TransactionalStockPositionRepository,
    TransactionalStockReservationRepository,
    TransactionalStockTransferRepository,
)
from packages.asset_infrastructure.persistence.part_repository import (
    TransactionalInterchangeabilityGroupRepository,
    TransactionalPartRepository,
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
    OptimisticConcurrencyConflict,
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
ADD_WORK_ORDER_TASK_PURPOSE = "SUSTAINMENT_WO_ADD_TASK"
ADD_WORK_ORDER_TASK_OPERATION = "asset.work_order.add_task"
DEMAND_MATERIAL_PURPOSE = "SUSTAINMENT_WO_DEMAND_MATERIAL"
DEMAND_MATERIAL_OPERATION = "asset.work_order.demand_material"
RESERVE_WORK_ORDER_MATERIAL_PURPOSE = "SUSTAINMENT_WO_RESERVE_MATERIAL"
RESERVE_WORK_ORDER_MATERIAL_OPERATION = "asset.work_order.reserve_material"
MARK_WORK_ORDER_PLANNED_PURPOSE = "SUSTAINMENT_WO_MARK_PLANNED"
MARK_WORK_ORDER_PLANNED_OPERATION = "asset.work_order.mark_planned"
MARK_WORK_ORDER_READY_PURPOSE = "SUSTAINMENT_WO_MARK_READY"
MARK_WORK_ORDER_READY_OPERATION = "asset.work_order.mark_ready"
SCHEDULE_WORK_ORDER_PURPOSE = "SUSTAINMENT_WO_SCHEDULE"
SCHEDULE_WORK_ORDER_OPERATION = "asset.work_order.schedule"
MARK_WORK_ORDER_WAITING_TECHNICIAN_PURPOSE = "SUSTAINMENT_WO_MARK_WAITING_TECHNICIAN"
MARK_WORK_ORDER_WAITING_TECHNICIAN_OPERATION = "asset.work_order.mark_waiting_technician"
START_WORK_ORDER_PROGRESS_PURPOSE = "SUSTAINMENT_WO_START_PROGRESS"
START_WORK_ORDER_PROGRESS_OPERATION = "asset.work_order.start_progress"
INTERRUPT_WORK_ORDER_PURPOSE = "SUSTAINMENT_WO_INTERRUPT"
INTERRUPT_WORK_ORDER_OPERATION = "asset.work_order.interrupt"
RESUME_WORK_ORDER_PURPOSE = "SUSTAINMENT_WO_RESUME"
RESUME_WORK_ORDER_OPERATION = "asset.work_order.resume"
START_WORK_ORDER_TASK_PURPOSE = "SUSTAINMENT_WO_EXECUTE_TASK_START"
START_WORK_ORDER_TASK_OPERATION = "asset.work_order.task.start"
COMPLETE_WORK_ORDER_TASK_PURPOSE = "SUSTAINMENT_WO_EXECUTE_TASK_COMPLETE"
COMPLETE_WORK_ORDER_TASK_OPERATION = "asset.work_order.task.complete"
COMPLETE_WORK_ORDER_TECHNICALLY_PURPOSE = "SUSTAINMENT_WO_TECH_COMPLETE"
COMPLETE_WORK_ORDER_TECHNICALLY_OPERATION = "asset.work_order.complete_technically"
SEND_WORK_ORDER_TO_VALIDATION_PURPOSE = "SUSTAINMENT_WO_SEND_TO_VALIDATION"
SEND_WORK_ORDER_TO_VALIDATION_OPERATION = "asset.work_order.send_to_validation"
FAIL_WORK_ORDER_VALIDATION_PURPOSE = "SUSTAINMENT_WO_VALIDATE_FAIL"
FAIL_WORK_ORDER_VALIDATION_OPERATION = "asset.work_order.validation.fail"
CLOSE_WORK_ORDER_PURPOSE = "SUSTAINMENT_WO_CLOSE"
CLOSE_WORK_ORDER_OPERATION = "asset.work_order.close"
CANCEL_WORK_ORDER_PURPOSE = "SUSTAINMENT_WO_CANCEL"
CANCEL_WORK_ORDER_OPERATION = "asset.work_order.cancel"
RECORD_REMOVED_COMPONENT_PURPOSE = "SUSTAINMENT_WO_RECORD_REMOVAL"
RECORD_REMOVED_COMPONENT_OPERATION = "asset.work_order.component.record_removed"
TRANSITION_VEHICLE_LIFECYCLE_PURPOSE = "ASSET_VEHICLE_TRANSITION"
TRANSITION_VEHICLE_LIFECYCLE_OPERATION = "asset.vehicle.transition_lifecycle"
RECORD_VEHICLE_METER_PURPOSE = "ASSET_VEHICLE_RECORD_METER"
RECORD_VEHICLE_METER_OPERATION = "asset.vehicle.record_meter"
CORRECT_VEHICLE_METER_PURPOSE = "ASSET_VEHICLE_CORRECT_METER"
CORRECT_VEHICLE_METER_OPERATION = "asset.vehicle.correct_meter"
REGISTER_CUSTOMER_SITE_PURPOSE = "ASSET_SITE_REGISTER"
REGISTER_CUSTOMER_SITE_OPERATION = "asset.customer_site.register"
REGISTER_PART_PURPOSE = "ASSET_PART_REGISTER"
REGISTER_PART_OPERATION = "asset.part.register"
ADD_PART_REVISION_PURPOSE = "ASSET_PART_ADD_REVISION"
ADD_PART_REVISION_OPERATION = "asset.part.add_revision"
SUPERSEDE_PART_REVISION_PURPOSE = "ASSET_PART_SUPERSEDE_REVISION"
SUPERSEDE_PART_REVISION_OPERATION = "asset.part.supersede_revision"
CHANGE_INTERCHANGEABILITY_GROUP_PURPOSE = "ASSET_PART_CHANGE_INTERCHANGEABILITY_GROUP"
CHANGE_INTERCHANGEABILITY_GROUP_OPERATION = "asset.part.change_interchangeability_group"
ASSERT_PART_APPLICABILITY_PURPOSE = "ASSET_APPLICABILITY_ASSERT"
ASSERT_PART_APPLICABILITY_OPERATION = "asset.applicability.assert"
WITHDRAW_PART_APPLICABILITY_PURPOSE = "ASSET_APPLICABILITY_WITHDRAW"
WITHDRAW_PART_APPLICABILITY_OPERATION = "asset.applicability.withdraw"
OPEN_STOCK_POSITION_PURPOSE = "ASSET_INVENTORY_OPEN_POSITION"
OPEN_STOCK_POSITION_OPERATION = "asset.inventory.open_position"
ADJUST_STOCK_PURPOSE = "ASSET_INVENTORY_ADJUST"
ADJUST_STOCK_OPERATION = "asset.inventory.adjust"

router = APIRouter(prefix="/v1/asset", tags=["asset"])


class OpenWorkOrderRequest(BaseModel):
    vehicle_id: str = Field(description="Vehicle para o qual a WorkOrder será aberta.")
    at_instant: datetime = Field(description="Instante UTC de resolução do contrato aplicável.")
    failure_mode: str = Field(min_length=1, max_length=200)
    failure_reported_at: datetime
    failure_affected_position: str | None = Field(default=None, max_length=100)


class AddWorkOrderTaskRequest(BaseModel):
    expected_version: int = Field(ge=1)
    description: str = Field(min_length=1, max_length=500)
    mandatory: bool


class DemandMaterialRequest(BaseModel):
    expected_version: int = Field(ge=1)
    part_id: str = Field(description="Part demandado pela tarefa da WorkOrder.")
    qty: Decimal = Field(gt=Decimal("0"))
    task_id: str = Field(description="Tarefa da WorkOrder que demanda o material.")


class ReserveWorkOrderMaterialRequest(BaseModel):
    expected_version: int = Field(ge=1)
    stock_position_id: str
    part_id: str
    qty: Decimal = Field(gt=Decimal("0"))
    priority: int = Field(ge=0)
    entitlement_event_id: str = Field(
        description="Evento persistido asset.sustainment.entitlement_resolved."
    )


class MarkWorkOrderPlannedRequest(BaseModel):
    expected_version: int = Field(ge=1)


class MarkWorkOrderReadyRequest(BaseModel):
    expected_version: int = Field(ge=1)


class ScheduleWorkOrderRequest(BaseModel):
    expected_version: int = Field(ge=1)
    technician_and_workshop_allocated: bool


class MarkWorkOrderWaitingTechnicianRequest(BaseModel):
    expected_version: int = Field(ge=1)


class StartWorkOrderProgressRequest(BaseModel):
    expected_version: int = Field(ge=1)
    vehicle_in_maintenance: bool


class InterruptWorkOrderRequest(BaseModel):
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=500)


class ResumeWorkOrderRequest(BaseModel):
    expected_version: int = Field(ge=1)


class StartWorkOrderTaskRequest(BaseModel):
    expected_version: int = Field(ge=1)
    task_id: str = Field(description="Tarefa da WorkOrder que será iniciada.")


class CompleteWorkOrderTaskRequest(BaseModel):
    expected_version: int = Field(ge=1)
    task_id: str = Field(description="Tarefa da WorkOrder que será concluída.")
    labor_entry: str | None = Field(default=None, min_length=1, max_length=500)


class RecordRemovedComponentRequest(BaseModel):
    expected_version: int = Field(ge=1)
    part_id: str = Field(description="Part removida durante a execução da WorkOrder.")
    disposition: str = Field(min_length=1, max_length=200)
    serial: str | None = Field(default=None, min_length=1, max_length=200)


class CompleteWorkOrderTechnicallyRequest(BaseModel):
    expected_version: int = Field(ge=1)
    diagnosis: str = Field(min_length=1, max_length=1000)
    root_cause: str = Field(min_length=1, max_length=1000)
    resolution: str = Field(min_length=1, max_length=1000)


class SendWorkOrderToValidationRequest(BaseModel):
    expected_version: int = Field(ge=1)


class FailWorkOrderValidationRequest(BaseModel):
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=500)
    notes: str | None = Field(default=None, min_length=1, max_length=1000)


class CloseWorkOrderRequest(BaseModel):
    expected_version: int = Field(ge=1)
    notes: str | None = Field(default=None, min_length=1, max_length=1000)


class CancelWorkOrderRequest(BaseModel):
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=500)


class TransitionVehicleLifecycleRequest(BaseModel):
    expected_version: int = Field(ge=1)
    new_state: VehicleLifecycleState
    reason: str | None = Field(default=None, min_length=1, max_length=500)


class RecordVehicleMeterReadingRequest(BaseModel):
    expected_version: int = Field(ge=1)
    kind: MeterKind
    value: Decimal = Field(ge=Decimal("0"))
    observed_at: datetime
    source: str = Field(min_length=1, max_length=100)


class CorrectVehicleMeterReadingRequest(BaseModel):
    expected_version: int = Field(ge=1)
    corrected_value: Decimal = Field(ge=Decimal("0"))
    reason: str = Field(min_length=1, max_length=500)


class SiteContactRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    role: str | None = Field(default=None, min_length=1, max_length=100)
    email: str | None = Field(default=None, min_length=1, max_length=200)
    phone: str | None = Field(default=None, min_length=1, max_length=50)


class RegisterCustomerSiteRequest(BaseModel):
    customer_id: str
    code: str = Field(min_length=1, max_length=100)
    display_name: str = Field(min_length=1, max_length=200)
    kind: CustomerSiteKind = CustomerSiteKind.OM
    contacts: list[SiteContactRequest] = Field(default_factory=list)


class SiteContactResponse(BaseModel):
    name: str
    role: str | None
    email: str | None
    phone: str | None


class CustomerSiteResponse(BaseModel):
    site_id: str
    customer_ref: str
    code: str
    display_name: str
    kind: str
    contacts: list[SiteContactResponse]
    version: int


class RegisterPartRequest(BaseModel):
    part_number: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=500)
    manufacturer: str = Field(min_length=1, max_length=200)
    manufacturer_pn: str | None = Field(default=None, min_length=1, max_length=100)
    nsn: str | None = Field(default=None, min_length=1, max_length=50)
    external_classifications: list[str] = Field(default_factory=list)


class PartRevisionResponse(BaseModel):
    revision_id: str
    revision_code: str
    lifecycle_state: str
    spec_ref: str | None
    drawing_ref: str | None
    materials: list[str]


class PartResponse(BaseModel):
    part_id: str
    part_number: str
    description: str
    manufacturer: str
    manufacturer_pn: str | None
    nsn: str | None
    external_classifications: list[str]
    revisions: list[PartRevisionResponse]
    version: int
    created_at: datetime


class AddPartRevisionRequest(BaseModel):
    expected_version: int = Field(ge=1)
    revision_code: str = Field(min_length=1, max_length=50)
    spec_id: str | None = None
    drawing_id: str | None = None
    materials: list[str] = Field(default_factory=list)


class SupersedePartRevisionRequest(BaseModel):
    expected_version: int = Field(ge=1)
    predecessor_revision_id: str
    successor_revision_id: str
    reason: str = Field(min_length=1, max_length=500)


class InterchangeabilityChange(StrEnum):
    ADDED = "ADDED"
    REMOVED = "REMOVED"


class ChangeInterchangeabilityGroupRequest(BaseModel):
    expected_version: int = Field(ge=0)
    revision_id: str
    change: InterchangeabilityChange


class InterchangeabilityGroupResponse(BaseModel):
    group_id: str
    member_part_revisions: list[str]
    version: int


class AssertPartApplicabilityRequest(BaseModel):
    part_id: str
    part_revision_id: str
    model_id: str
    variant_id: str | None = None
    serial_from: str | None = Field(default=None, max_length=100)
    serial_to: str | None = Field(default=None, max_length=100)
    valid_from: datetime
    valid_until: datetime | None = None
    evidence_id: str


class ApplicabilityResponse(BaseModel):
    applicability_id: str
    part_ref: str
    part_revision_ref: str
    model_ref: str
    variant_ref: str | None
    serial_from: str | None
    serial_to: str | None
    valid_from: datetime
    valid_until: datetime | None
    evidence_ref: str
    asserted_at: datetime
    asserted_by: str
    state: str
    version: int


class WithdrawPartApplicabilityRequest(BaseModel):
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=500)


class OpenStockPositionRequest(BaseModel):
    part_id: str
    location_id: str
    purpose: StockPurpose
    ownership: StockOwnership
    on_hand: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    in_transit: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    quarantine: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    inspection: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    damaged: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    lot: str | None = Field(default=None, min_length=1, max_length=100)
    serial: str | None = Field(default=None, min_length=1, max_length=100)


StockQuantityBucket = Literal["on_hand", "in_transit", "quarantine", "inspection", "damaged"]


class AdjustStockRequest(BaseModel):
    expected_version: int = Field(ge=1)
    delta_by_status: dict[StockQuantityBucket, Decimal] = Field(min_length=1)
    reason: str = Field(min_length=1, max_length=500)


class StockPositionResponse(BaseModel):
    stock_position_id: str
    part_ref: str
    location_ref: str
    purpose: str
    ownership: str
    on_hand: Decimal
    in_transit: Decimal
    quarantine: Decimal
    inspection: Decimal
    damaged: Decimal
    available: Decimal
    lot: str | None
    serial: str | None
    version: int


def get_open_work_order_service(connection: ConnectionDependency) -> WorkOrderService:
    event_log = DomainEventRepository(connection=connection)
    recorder = AssetEventRecorder(event_log=event_log, clock=SystemClock())
    vehicle_repository = TransactionalVehicleRepository(connection=connection)
    return WorkOrderService(
        repository=TransactionalWorkOrderRepository(connection=connection),
        sli_contract_repository=TransactionalSLIContractRepository(connection=connection),
        part_repository=TransactionalPartRepository(connection=connection),
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


def get_domain_event_repository(connection: ConnectionDependency) -> DomainEventRepository:
    return DomainEventRepository(connection=connection)


def get_vehicle_service(connection: ConnectionDependency) -> VehicleService:
    event_log = DomainEventRepository(connection=connection)
    return VehicleService(
        repository=TransactionalVehicleRepository(connection=connection),
        recorder=AssetEventRecorder(event_log=event_log, clock=SystemClock()),
    )


def get_inventory_service(connection: ConnectionDependency) -> InventoryService:
    event_log = DomainEventRepository(connection=connection)
    return InventoryService(
        stock_position_repository=TransactionalStockPositionRepository(connection=connection),
        stock_reservation_repository=TransactionalStockReservationRepository(connection=connection),
        stock_transfer_repository=TransactionalStockTransferRepository(connection=connection),
        recorder=AssetEventRecorder(event_log=event_log, clock=SystemClock()),
    )


def get_customer_site_service(connection: ConnectionDependency) -> CustomerSiteService:
    event_log = DomainEventRepository(connection=connection)
    return CustomerSiteService(
        repository=TransactionalCustomerSiteRepository(connection=connection),
        recorder=AssetEventRecorder(event_log=event_log, clock=SystemClock()),
    )


def get_part_service(connection: ConnectionDependency) -> PartService:
    event_log = DomainEventRepository(connection=connection)
    return PartService(
        repository=TransactionalPartRepository(connection=connection),
        recorder=AssetEventRecorder(event_log=event_log, clock=SystemClock()),
    )


def get_interchangeability_group_service(
    connection: ConnectionDependency,
) -> InterchangeabilityGroupService:
    event_log = DomainEventRepository(connection=connection)
    return InterchangeabilityGroupService(
        repository=TransactionalInterchangeabilityGroupRepository(connection=connection),
        recorder=AssetEventRecorder(event_log=event_log, clock=SystemClock()),
    )


def get_applicability_service(connection: ConnectionDependency) -> ApplicabilityService:
    event_log = DomainEventRepository(connection=connection)
    return ApplicabilityService(
        repository=TransactionalApplicabilityRepository(connection=connection),
        recorder=AssetEventRecorder(event_log=event_log, clock=SystemClock()),
        event_reader=event_log,
    )


def _customer_site_response(site: CustomerSite) -> CustomerSiteResponse:
    return CustomerSiteResponse(
        site_id=str(site.site_id.value),
        customer_ref=str(site.customer_ref.value),
        code=site.code,
        display_name=site.display_name,
        kind=site.kind.value,
        contacts=[
            SiteContactResponse(
                name=contact.name,
                role=contact.role,
                email=contact.email,
                phone=contact.phone,
            )
            for contact in site.contacts
        ],
        version=site.version,
    )


def _part_response(part: Part) -> PartResponse:
    return PartResponse(
        part_id=str(part.part_id.value),
        part_number=part.identity.part_number,
        description=part.identity.description,
        manufacturer=part.identity.manufacturer,
        manufacturer_pn=part.identity.manufacturer_pn,
        nsn=part.identity.nsn,
        external_classifications=list(part.identity.external_classifications),
        revisions=[
            PartRevisionResponse(
                revision_id=str(revision.revision_id.value),
                revision_code=revision.revision_code,
                lifecycle_state=revision.lifecycle_state.value,
                spec_ref=None if revision.spec_ref is None else str(revision.spec_ref.value),
                drawing_ref=(
                    None if revision.drawing_ref is None else str(revision.drawing_ref.value)
                ),
                materials=list(revision.materials),
            )
            for revision in part.revisions
        ],
        version=part.version,
        created_at=part.created_at,
    )


def _interchangeability_group_response(
    group: InterchangeabilityGroup,
) -> InterchangeabilityGroupResponse:
    return InterchangeabilityGroupResponse(
        group_id=str(group.group_id.value),
        member_part_revisions=[str(member.value) for member in group.member_part_revisions],
        version=group.version,
    )


def _applicability_response(applicability: Applicability) -> ApplicabilityResponse:
    target = applicability.target
    return ApplicabilityResponse(
        applicability_id=str(applicability.applicability_id.value),
        part_ref=str(applicability.part_ref.value),
        part_revision_ref=str(applicability.part_revision_ref.value),
        model_ref=str(target.model_ref.value),
        variant_ref=None if target.variant_ref is None else str(target.variant_ref.value),
        serial_from=target.serial_from,
        serial_to=target.serial_to,
        valid_from=target.valid_from,
        valid_until=target.valid_until,
        evidence_ref=str(applicability.evidence_ref.value),
        asserted_at=applicability.asserted_at,
        asserted_by=str(applicability.asserted_by.value),
        state=applicability.state.value,
        version=applicability.version,
    )


def _stock_position_response(position: StockPosition) -> StockPositionResponse:
    quantities = position.quantities
    return StockPositionResponse(
        stock_position_id=str(position.stock_position_id.value),
        part_ref=str(position.part_ref.value),
        location_ref=str(position.location_ref.value),
        purpose=position.purpose.value,
        ownership=position.ownership.value,
        on_hand=quantities.on_hand,
        in_transit=quantities.in_transit,
        quarantine=quantities.quarantine,
        inspection=quantities.inspection,
        damaged=quantities.damaged,
        available=position.available,
        lot=position.lot,
        serial=position.serial,
        version=position.version,
    )


def _entitlement_resolution_from_event(
    event_log: DomainEventRepository,
    entitlement_event_id: TypedId,
) -> EntitlementResolution:
    event = event_log.get_by_id(entitlement_event_id)
    if event is None or event.event_type != SUSTAINMENT_ENTITLEMENT_RESOLVED:
        raise KeyError(f"Entitlement resolvido '{entitlement_event_id.value}' não encontrado.")
    try:
        data = _canonical_response_data(event.payload_canonical_bytes)
        instant_value = data["instant"]
        if not isinstance(instant_value, str):
            raise ValueError("instant inválido")
        instant = datetime.fromisoformat(instant_value.replace("Z", "+00:00"))
        require_utc(instant, field_name="instant")
        breakdown = data["breakdown"]
        if not isinstance(breakdown, str) or not breakdown.strip():
            raise ValueError("breakdown inválido")
        return EntitlementResolution(
            vehicle_ref=TypedId.parse("vehicle", str(data["vehicle_ref"])),
            subject_ref=TypedId.parse("part", str(data["subject_ref"])),
            instant=instant,
            decision_ref=TypedId.parse("decision", str(data["decision_ref"])),
            outcome=EntitlementOutcome(str(data["outcome"])),
            breakdown=breakdown,
        )
    except (KeyError, TypeError, ValueError, RuntimeError) as exc:
        raise ValueError("Evento de entitlement persistido possui payload inválido.") from exc


@router.post(
    "/parts",
    response_model=PartResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar Part",
    responses=RESPOSTAS_PADRAO,
)
def cadastrar_part(
    body: RegisterPartRequest,
    contexto: Annotated[OrganizationContext, Depends(require_part_register)],
    idempotency_key: Annotated[str, Header(alias=IDEMPOTENCY_HEADER, min_length=1)],
    service: Annotated[PartService, Depends(get_part_service)],
    idempotency_service: Annotated[IdempotencyService, Depends(get_idempotency_service)],
) -> PartResponse:
    request = _idempotency_request(
        body=body,
        contexto=contexto,
        idempotency_key=idempotency_key,
        operation=REGISTER_PART_OPERATION,
        purpose=REGISTER_PART_PURPOSE,
        requested_at=datetime.now(UTC),
    )
    operation_context = AssetOperationContext.from_organization_context(
        contexto, source_id=TypedId.new("api_request")
    )

    def _handler() -> CanonicalPayload:
        try:
            part = service.register_part(
                operation_context,
                identity=PartIdentity(
                    part_number=body.part_number,
                    description=body.description,
                    manufacturer=body.manufacturer,
                    manufacturer_pn=body.manufacturer_pn,
                    nsn=body.nsn,
                    external_classifications=tuple(body.external_classifications),
                ),
                occurred_at=datetime.now(UTC),
            )
        except IntegrityError as exc:
            raise _domain_conflict(
                "Já existe Part com este part_number nesta Organization."
            ) from exc
        except ValueError as exc:
            raise _domain_conflict(str(exc)) from exc
        response = _part_response(part)
        return CanonicalPayload(
            schema="asset.register_part.response",
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
    return PartResponse.model_validate(_canonical_response_data(execution.result_canonical_bytes))


@router.post(
    "/parts/{part_id}/revisions",
    response_model=PartResponse,
    status_code=status.HTTP_200_OK,
    summary="Adicionar revisão a Part",
    responses=RESPOSTAS_PADRAO,
)
def adicionar_revisao_part(
    part_id: str,
    body: AddPartRevisionRequest,
    contexto: Annotated[OrganizationContext, Depends(require_part_add_revision)],
    idempotency_key: Annotated[str, Header(alias=IDEMPOTENCY_HEADER, min_length=1)],
    service: Annotated[PartService, Depends(get_part_service)],
    idempotency_service: Annotated[IdempotencyService, Depends(get_idempotency_service)],
) -> PartResponse:
    parsed_part_id = _typed_id_or_problem(part_id, entity_type="part", campo="part_id")
    spec_ref = (
        None
        if body.spec_id is None
        else _typed_id_or_problem(body.spec_id, entity_type="spec", campo="spec_id")
    )
    drawing_ref = (
        None
        if body.drawing_id is None
        else _typed_id_or_problem(body.drawing_id, entity_type="drawing", campo="drawing_id")
    )
    request = _idempotency_request(
        body=body,
        contexto=contexto,
        idempotency_key=idempotency_key,
        operation=ADD_PART_REVISION_OPERATION,
        purpose=ADD_PART_REVISION_PURPOSE,
        requested_at=datetime.now(UTC),
        extra_intent={"part_id": part_id},
    )
    operation_context = AssetOperationContext.from_organization_context(
        contexto, source_id=TypedId.new("api_request")
    )

    def _handler() -> CanonicalPayload:
        try:
            part = service.add_part_revision(
                operation_context,
                parsed_part_id,
                revision_code=body.revision_code,
                spec_ref=spec_ref,
                drawing_ref=drawing_ref,
                materials=tuple(body.materials),
                expected_version=body.expected_version,
                occurred_at=datetime.now(UTC),
            )
        except PartNaoEncontrado as exc:
            raise _not_found(str(exc)) from exc
        except OptimisticConcurrencyConflict as exc:
            raise DomainProblem(
                status_code=409,
                reason_code=OptimisticConcurrencyConflict.code,
                title="Versão de agregado conflitante",
                detail="A versão informada não corresponde à versão atual da Part.",
            ) from exc
        except ValueError as exc:
            raise _domain_conflict(str(exc)) from exc
        response = _part_response(part)
        return CanonicalPayload(
            schema="asset.add_part_revision.response",
            version=1,
            value=response.model_dump(mode="json"),
        )

    try:
        execution = idempotency_service.execute(request, _handler)
    except ValueError as exc:
        raise DomainProblem(
            status_code=422,
            reason_code="IDEMPOTENCY_KEY_INVALIDA",
            title="Idempotency-Key inválida",
            detail=str(exc),
        ) from exc
    except IdempotencyConflict as exc:
        raise DomainProblem(
            status_code=409,
            reason_code="IDEMPOTENCY_KEY_COM_INTENCAO_DIVERGENTE",
            title="Conflito de idempotência",
            detail=str(exc),
        ) from exc
    except IdempotencyResultUnknown as exc:
        raise DomainProblem(
            status_code=409,
            reason_code="RESULTADO_IDEMPOTENTE_DESCONHECIDO",
            title="Resultado idempotente desconhecido",
            detail=str(exc),
        ) from exc
    return PartResponse.model_validate(_canonical_response_data(execution.result_canonical_bytes))


@router.post(
    "/parts/{part_id}/revisions/supersede",
    response_model=PartResponse,
    status_code=status.HTTP_200_OK,
    summary="Superseder revisão de Part",
    responses=RESPOSTAS_PADRAO,
)
def superseder_revisao_part(
    part_id: str,
    body: SupersedePartRevisionRequest,
    contexto: Annotated[OrganizationContext, Depends(require_part_supersede)],
    idempotency_key: Annotated[str, Header(alias=IDEMPOTENCY_HEADER, min_length=1)],
    service: Annotated[PartService, Depends(get_part_service)],
    idempotency_service: Annotated[IdempotencyService, Depends(get_idempotency_service)],
) -> PartResponse:
    parsed_part_id = _typed_id_or_problem(part_id, entity_type="part", campo="part_id")
    predecessor_id = _typed_id_or_problem(
        body.predecessor_revision_id,
        entity_type="part_revision",
        campo="predecessor_revision_id",
    )
    successor_id = _typed_id_or_problem(
        body.successor_revision_id,
        entity_type="part_revision",
        campo="successor_revision_id",
    )
    request = _idempotency_request(
        body=body,
        contexto=contexto,
        idempotency_key=idempotency_key,
        operation=SUPERSEDE_PART_REVISION_OPERATION,
        purpose=SUPERSEDE_PART_REVISION_PURPOSE,
        requested_at=datetime.now(UTC),
        extra_intent={"part_id": part_id},
    )
    operation_context = AssetOperationContext.from_organization_context(
        contexto, source_id=TypedId.new("api_request")
    )

    def _handler() -> CanonicalPayload:
        try:
            part = service.supersede_part_revision(
                operation_context,
                parsed_part_id,
                predecessor_revision_id=predecessor_id,
                successor_revision_id=successor_id,
                reason=body.reason,
                expected_version=body.expected_version,
                occurred_at=datetime.now(UTC),
            )
        except PartNaoEncontrado as exc:
            raise _not_found(str(exc)) from exc
        except OptimisticConcurrencyConflict as exc:
            raise DomainProblem(
                status_code=409,
                reason_code=OptimisticConcurrencyConflict.code,
                title="Versão de agregado conflitante",
                detail="A versão informada não corresponde à versão atual da Part.",
            ) from exc
        except (KeyError, ValueError) as exc:
            raise _domain_conflict(str(exc)) from exc
        response = _part_response(part)
        return CanonicalPayload(
            schema="asset.supersede_part_revision.response",
            version=1,
            value=response.model_dump(mode="json"),
        )

    try:
        execution = idempotency_service.execute(request, _handler)
    except ValueError as exc:
        raise DomainProblem(
            status_code=422,
            reason_code="IDEMPOTENCY_KEY_INVALIDA",
            title="Idempotency-Key inválida",
            detail=str(exc),
        ) from exc
    except IdempotencyConflict as exc:
        raise DomainProblem(
            status_code=409,
            reason_code="IDEMPOTENCY_KEY_COM_INTENCAO_DIVERGENTE",
            title="Conflito de idempotência",
            detail=str(exc),
        ) from exc
    except IdempotencyResultUnknown as exc:
        raise DomainProblem(
            status_code=409,
            reason_code="RESULTADO_IDEMPOTENTE_DESCONHECIDO",
            title="Resultado idempotente desconhecido",
            detail=str(exc),
        ) from exc
    return PartResponse.model_validate(_canonical_response_data(execution.result_canonical_bytes))


@router.post(
    "/interchangeability-groups/{group_id}/members/change",
    response_model=InterchangeabilityGroupResponse,
    status_code=status.HTTP_200_OK,
    summary="Alterar membro de grupo de intercambiabilidade",
    responses=RESPOSTAS_PADRAO,
)
def alterar_grupo_intercambiabilidade(
    group_id: str,
    body: ChangeInterchangeabilityGroupRequest,
    contexto: Annotated[OrganizationContext, Depends(require_part_edit_interchange)],
    idempotency_key: Annotated[str, Header(alias=IDEMPOTENCY_HEADER, min_length=1)],
    service: Annotated[
        InterchangeabilityGroupService, Depends(get_interchangeability_group_service)
    ],
    idempotency_service: Annotated[IdempotencyService, Depends(get_idempotency_service)],
) -> InterchangeabilityGroupResponse:
    parsed_group_id = _typed_id_or_problem(
        group_id, entity_type="interchangeability_group", campo="group_id"
    )
    revision_ref = _typed_id_or_problem(
        body.revision_id, entity_type="part_revision", campo="revision_id"
    )
    request = _idempotency_request(
        body=body,
        contexto=contexto,
        idempotency_key=idempotency_key,
        operation=CHANGE_INTERCHANGEABILITY_GROUP_OPERATION,
        purpose=CHANGE_INTERCHANGEABILITY_GROUP_PURPOSE,
        requested_at=datetime.now(UTC),
        extra_intent={"group_id": group_id},
    )
    operation_context = AssetOperationContext.from_organization_context(
        contexto, source_id=TypedId.new("api_request")
    )

    def _handler() -> CanonicalPayload:
        try:
            if body.change is InterchangeabilityChange.ADDED:
                group = service.add_member(
                    operation_context,
                    parsed_group_id,
                    revision_ref=revision_ref,
                    expected_version=body.expected_version,
                    occurred_at=datetime.now(UTC),
                )
            else:
                group = service.remove_member(
                    operation_context,
                    parsed_group_id,
                    revision_ref=revision_ref,
                    expected_version=body.expected_version,
                    occurred_at=datetime.now(UTC),
                )
        except InterchangeabilityGroupNaoEncontrado as exc:
            raise _not_found(str(exc)) from exc
        except OptimisticConcurrencyConflict as exc:
            raise DomainProblem(
                status_code=409,
                reason_code=OptimisticConcurrencyConflict.code,
                title="Versão de agregado conflitante",
                detail=(
                    "A versão informada não corresponde à versão atual do grupo de "
                    "intercambiabilidade."
                ),
            ) from exc
        except (KeyError, ValueError) as exc:
            raise _domain_conflict(str(exc)) from exc
        response = _interchangeability_group_response(group)
        return CanonicalPayload(
            schema="asset.change_interchangeability_group.response",
            version=1,
            value=response.model_dump(mode="json"),
        )

    try:
        execution = idempotency_service.execute(request, _handler)
    except ValueError as exc:
        raise DomainProblem(
            status_code=422,
            reason_code="IDEMPOTENCY_KEY_INVALIDA",
            title="Idempotency-Key inválida",
            detail=str(exc),
        ) from exc
    except IdempotencyConflict as exc:
        raise DomainProblem(
            status_code=409,
            reason_code="IDEMPOTENCY_KEY_COM_INTENCAO_DIVERGENTE",
            title="Conflito de idempotência",
            detail=str(exc),
        ) from exc
    except IdempotencyResultUnknown as exc:
        raise DomainProblem(
            status_code=409,
            reason_code="RESULTADO_IDEMPOTENTE_DESCONHECIDO",
            title="Resultado idempotente desconhecido",
            detail=str(exc),
        ) from exc
    return InterchangeabilityGroupResponse.model_validate(
        _canonical_response_data(execution.result_canonical_bytes)
    )


@router.post(
    "/part-applicability/assertions",
    response_model=ApplicabilityResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Afirmar aplicabilidade de revisão de Part",
    responses=RESPOSTAS_PADRAO,
)
def afirmar_aplicabilidade_part(
    body: AssertPartApplicabilityRequest,
    contexto: Annotated[OrganizationContext, Depends(require_applicability_assert)],
    idempotency_key: Annotated[str, Header(alias=IDEMPOTENCY_HEADER, min_length=1)],
    service: Annotated[ApplicabilityService, Depends(get_applicability_service)],
    idempotency_service: Annotated[IdempotencyService, Depends(get_idempotency_service)],
) -> ApplicabilityResponse:
    part_ref = _typed_id_or_problem(body.part_id, entity_type="part", campo="part_id")
    revision_ref = _typed_id_or_problem(
        body.part_revision_id, entity_type="part_revision", campo="part_revision_id"
    )
    model_ref = _typed_id_or_problem(body.model_id, entity_type="vehicle_model", campo="model_id")
    variant_ref = (
        None
        if body.variant_id is None
        else _typed_id_or_problem(
            body.variant_id, entity_type="vehicle_variant", campo="variant_id"
        )
    )
    evidence_ref = _typed_id_or_problem(
        body.evidence_id, entity_type="evidence", campo="evidence_id"
    )
    asserted_at = datetime.now(UTC)
    request = _idempotency_request(
        body=body,
        contexto=contexto,
        idempotency_key=idempotency_key,
        operation=ASSERT_PART_APPLICABILITY_OPERATION,
        purpose=ASSERT_PART_APPLICABILITY_PURPOSE,
        requested_at=asserted_at,
    )
    operation_context = AssetOperationContext.from_organization_context(
        contexto, source_id=TypedId.new("api_request")
    )

    def _handler() -> CanonicalPayload:
        try:
            applicability = service.assert_applicability(
                operation_context,
                part_ref=part_ref,
                part_revision_ref=revision_ref,
                target=ApplicabilityTarget(
                    model_ref=model_ref,
                    variant_ref=variant_ref,
                    serial_from=body.serial_from,
                    serial_to=body.serial_to,
                    valid_from=body.valid_from,
                    valid_until=body.valid_until,
                ),
                evidence_ref=evidence_ref,
                asserted_at=asserted_at,
                asserted_by=contexto.actor_id,
            )
        except ValueError as exc:
            raise _domain_conflict(str(exc)) from exc
        response = _applicability_response(applicability)
        return CanonicalPayload(
            schema="asset.assert_part_applicability.response",
            version=1,
            value=response.model_dump(mode="json"),
        )

    try:
        execution = idempotency_service.execute(request, _handler)
    except IntegrityError as exc:
        raise _domain_conflict("Part ou revisão não existe na Organization informada.") from exc
    except ValueError as exc:
        raise DomainProblem(
            status_code=422,
            reason_code="IDEMPOTENCY_KEY_INVALIDA",
            title="Idempotency-Key inválida",
            detail=str(exc),
        ) from exc
    except IdempotencyConflict as exc:
        raise DomainProblem(
            status_code=409,
            reason_code="IDEMPOTENCY_KEY_COM_INTENCAO_DIVERGENTE",
            title="Conflito de idempotência",
            detail=str(exc),
        ) from exc
    except IdempotencyResultUnknown as exc:
        raise DomainProblem(
            status_code=409,
            reason_code="RESULTADO_IDEMPOTENTE_DESCONHECIDO",
            title="Resultado idempotente desconhecido",
            detail=str(exc),
        ) from exc
    return ApplicabilityResponse.model_validate(
        _canonical_response_data(execution.result_canonical_bytes)
    )


@router.post(
    "/part-applicability/{applicability_id}/withdraw",
    response_model=ApplicabilityResponse,
    status_code=status.HTTP_200_OK,
    summary="Retirar aplicabilidade de Part",
    responses=RESPOSTAS_PADRAO,
)
def retirar_aplicabilidade_part(
    applicability_id: str,
    body: WithdrawPartApplicabilityRequest,
    contexto: Annotated[OrganizationContext, Depends(require_applicability_withdraw)],
    idempotency_key: Annotated[str, Header(alias=IDEMPOTENCY_HEADER, min_length=1)],
    service: Annotated[ApplicabilityService, Depends(get_applicability_service)],
    idempotency_service: Annotated[IdempotencyService, Depends(get_idempotency_service)],
) -> ApplicabilityResponse:
    parsed_id = _typed_id_or_problem(
        applicability_id, entity_type="applicability", campo="applicability_id"
    )
    withdrawn_at = datetime.now(UTC)
    request = _idempotency_request(
        body=body,
        contexto=contexto,
        idempotency_key=idempotency_key,
        operation=WITHDRAW_PART_APPLICABILITY_OPERATION,
        purpose=WITHDRAW_PART_APPLICABILITY_PURPOSE,
        requested_at=withdrawn_at,
        extra_intent={"applicability_id": applicability_id},
    )
    operation_context = AssetOperationContext.from_organization_context(
        contexto, source_id=TypedId.new("api_request")
    )

    def _handler() -> CanonicalPayload:
        try:
            applicability = service.withdraw_applicability(
                operation_context,
                parsed_id,
                reason=body.reason,
                withdrawn_at=withdrawn_at,
                expected_version=body.expected_version,
            )
        except ApplicabilityNaoEncontrada as exc:
            raise _not_found(str(exc)) from exc
        except AssercaoOriginalNaoEncontrada as exc:
            raise DomainProblem(
                status_code=409,
                reason_code="ASSERCAO_ORIGINAL_NAO_ENCONTRADA",
                title="Histórico de aplicabilidade incompleto",
                detail=str(exc),
            ) from exc
        except OptimisticConcurrencyConflict as exc:
            raise DomainProblem(
                status_code=409,
                reason_code=OptimisticConcurrencyConflict.code,
                title="Versão de agregado conflitante",
                detail="A versão informada não corresponde à versão atual da Applicability.",
            ) from exc
        except ValueError as exc:
            raise _domain_conflict(str(exc)) from exc
        response = _applicability_response(applicability)
        return CanonicalPayload(
            schema="asset.withdraw_part_applicability.response",
            version=1,
            value=response.model_dump(mode="json"),
        )

    try:
        execution = idempotency_service.execute(request, _handler)
    except ValueError as exc:
        raise DomainProblem(
            status_code=422,
            reason_code="IDEMPOTENCY_KEY_INVALIDA",
            title="Idempotency-Key inválida",
            detail=str(exc),
        ) from exc
    except IdempotencyConflict as exc:
        raise DomainProblem(
            status_code=409,
            reason_code="IDEMPOTENCY_KEY_COM_INTENCAO_DIVERGENTE",
            title="Conflito de idempotência",
            detail=str(exc),
        ) from exc
    except IdempotencyResultUnknown as exc:
        raise DomainProblem(
            status_code=409,
            reason_code="RESULTADO_IDEMPOTENTE_DESCONHECIDO",
            title="Resultado idempotente desconhecido",
            detail=str(exc),
        ) from exc
    return ApplicabilityResponse.model_validate(
        _canonical_response_data(execution.result_canonical_bytes)
    )


@router.post(
    "/stock-positions",
    response_model=StockPositionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Abrir posição de estoque",
    responses=RESPOSTAS_PADRAO,
)
def abrir_posicao_estoque(
    body: OpenStockPositionRequest,
    contexto: Annotated[OrganizationContext, Depends(require_inventory_open_position)],
    idempotency_key: Annotated[str, Header(alias=IDEMPOTENCY_HEADER, min_length=1)],
    service: Annotated[InventoryService, Depends(get_inventory_service)],
    idempotency_service: Annotated[IdempotencyService, Depends(get_idempotency_service)],
) -> StockPositionResponse:
    part_ref = _typed_id_or_problem(body.part_id, entity_type="part", campo="part_id")
    location_ref = _typed_id_or_problem(
        body.location_id, entity_type="stock_location", campo="location_id"
    )
    occurred_at = datetime.now(UTC)
    request = _idempotency_request(
        body=body,
        contexto=contexto,
        idempotency_key=idempotency_key,
        operation=OPEN_STOCK_POSITION_OPERATION,
        purpose=OPEN_STOCK_POSITION_PURPOSE,
        requested_at=occurred_at,
    )
    operation_context = AssetOperationContext.from_organization_context(
        contexto, source_id=TypedId.new("api_request")
    )

    def _handler() -> CanonicalPayload:
        try:
            position = service.open_stock_position(
                operation_context,
                part_ref=part_ref,
                location_ref=location_ref,
                purpose=body.purpose,
                ownership=body.ownership,
                quantities=StockQuantities(
                    on_hand=body.on_hand,
                    in_transit=body.in_transit,
                    quarantine=body.quarantine,
                    inspection=body.inspection,
                    damaged=body.damaged,
                ),
                lot=body.lot,
                serial=body.serial,
                occurred_at=occurred_at,
            )
        except ValueError as exc:
            raise _domain_conflict(str(exc)) from exc
        response = _stock_position_response(position)
        return CanonicalPayload(
            schema="asset.open_stock_position.response",
            version=1,
            value=response.model_dump(mode="json"),
        )

    try:
        execution = idempotency_service.execute(request, _handler)
    except IntegrityError as exc:
        raise _domain_conflict(
            "Já existe uma StockPosition para Part, StockLocation e purpose, "
            "ou uma das referências informadas não existe."
        ) from exc
    except ValueError as exc:
        raise DomainProblem(
            status_code=422,
            reason_code="IDEMPOTENCY_KEY_INVALIDA",
            title="Idempotency-Key inválida",
            detail=str(exc),
        ) from exc
    except IdempotencyConflict as exc:
        raise DomainProblem(
            status_code=409,
            reason_code="IDEMPOTENCY_KEY_COM_INTENCAO_DIVERGENTE",
            title="Conflito de idempotência",
            detail=str(exc),
        ) from exc
    except IdempotencyResultUnknown as exc:
        raise DomainProblem(
            status_code=409,
            reason_code="RESULTADO_IDEMPOTENTE_DESCONHECIDO",
            title="Resultado idempotente desconhecido",
            detail=str(exc),
        ) from exc
    return StockPositionResponse.model_validate(
        _canonical_response_data(execution.result_canonical_bytes)
    )


@router.post(
    "/stock-positions/{stock_position_id}/adjustments",
    response_model=StockPositionResponse,
    status_code=status.HTTP_200_OK,
    summary="Ajustar quantidades de uma posição de estoque",
    responses=RESPOSTAS_PADRAO,
)
def ajustar_posicao_estoque(
    stock_position_id: str,
    body: AdjustStockRequest,
    contexto: Annotated[OrganizationContext, Depends(require_inventory_adjust)],
    idempotency_key: Annotated[str, Header(alias=IDEMPOTENCY_HEADER, min_length=1)],
    service: Annotated[InventoryService, Depends(get_inventory_service)],
    idempotency_service: Annotated[IdempotencyService, Depends(get_idempotency_service)],
) -> StockPositionResponse:
    parsed_position_id = _typed_id_or_problem(
        stock_position_id,
        entity_type="stock_position",
        campo="stock_position_id",
    )
    occurred_at = datetime.now(UTC)
    request = _idempotency_request(
        body=body,
        contexto=contexto,
        idempotency_key=idempotency_key,
        operation=ADJUST_STOCK_OPERATION,
        purpose=ADJUST_STOCK_PURPOSE,
        requested_at=occurred_at,
        extra_intent={"stock_position_id": stock_position_id},
    )
    operation_context = AssetOperationContext.from_organization_context(
        contexto, source_id=TypedId.new("api_request")
    )

    def _handler() -> CanonicalPayload:
        try:
            deltas = {str(bucket): delta for bucket, delta in body.delta_by_status.items()}
            position = service.adjust_stock(
                operation_context,
                parsed_position_id,
                deltas=deltas,
                reason=body.reason,
                actor_ref=contexto.actor_id,
                occurred_at=occurred_at,
                expected_version=body.expected_version,
            )
        except StockPositionNaoEncontrada as exc:
            raise _not_found(str(exc)) from exc
        except OptimisticConcurrencyConflict as exc:
            raise _version_conflict() from exc
        except ValueError as exc:
            raise _domain_conflict(str(exc)) from exc
        response = _stock_position_response(position)
        return CanonicalPayload(
            schema="asset.adjust_stock.response",
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
    return StockPositionResponse.model_validate(
        _canonical_response_data(execution.result_canonical_bytes)
    )


@router.post(
    "/customer-sites",
    response_model=CustomerSiteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar CustomerSite",
    responses=RESPOSTAS_PADRAO,
)
def cadastrar_customer_site(
    body: RegisterCustomerSiteRequest,
    contexto: Annotated[OrganizationContext, Depends(require_site_register)],
    idempotency_key: Annotated[str, Header(alias=IDEMPOTENCY_HEADER, min_length=1)],
    service: Annotated[CustomerSiteService, Depends(get_customer_site_service)],
    idempotency_service: Annotated[IdempotencyService, Depends(get_idempotency_service)],
) -> CustomerSiteResponse:
    customer_ref = _typed_id_or_problem(
        body.customer_id, entity_type="customer", campo="customer_id"
    )
    request = _idempotency_request(
        body=body,
        contexto=contexto,
        idempotency_key=idempotency_key,
        operation=REGISTER_CUSTOMER_SITE_OPERATION,
        purpose=REGISTER_CUSTOMER_SITE_PURPOSE,
        requested_at=datetime.now(UTC),
    )
    operation_context = AssetOperationContext.from_organization_context(
        contexto,
        source_id=TypedId.new("api_request"),
    )

    def _handler() -> CanonicalPayload:
        try:
            site = service.register_site(
                operation_context,
                customer_ref=customer_ref,
                code=body.code,
                display_name=body.display_name,
                kind=body.kind,
                contacts=tuple(
                    SiteContact(
                        name=contact.name,
                        role=contact.role,
                        email=contact.email,
                        phone=contact.phone,
                    )
                    for contact in body.contacts
                ),
                occurred_at=datetime.now(UTC),
            )
        except IntegrityError as exc:
            raise _domain_conflict(
                "Já existe CustomerSite com este code nesta Organization."
            ) from exc
        except ValueError as exc:
            raise _domain_conflict(str(exc)) from exc
        response = _customer_site_response(site)
        return CanonicalPayload(
            schema="asset.register_customer_site.response",
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

    return CustomerSiteResponse.model_validate(
        _canonical_response_data(execution.result_canonical_bytes)
    )


@router.post(
    "/vehicles/{vehicle_id}/meter-readings",
    response_model=VehicleDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Registrar leitura de medidor de um Vehicle",
    responses=RESPOSTAS_PADRAO,
)
def registrar_leitura_medidor_vehicle(
    vehicle_id: str,
    body: RecordVehicleMeterReadingRequest,
    contexto: Annotated[OrganizationContext, Depends(require_vehicle_record_meter)],
    idempotency_key: Annotated[str, Header(alias=IDEMPOTENCY_HEADER, min_length=1)],
    service: Annotated[VehicleService, Depends(get_vehicle_service)],
    idempotency_service: Annotated[IdempotencyService, Depends(get_idempotency_service)],
) -> VehicleDetailResponse:
    parsed_vehicle_id = _typed_id_or_problem(vehicle_id, entity_type="vehicle", campo="vehicle_id")
    _require_utc_or_problem(body.observed_at, field_name="observed_at")
    request = _idempotency_request(
        body=body,
        contexto=contexto,
        idempotency_key=idempotency_key,
        operation=RECORD_VEHICLE_METER_OPERATION,
        purpose=RECORD_VEHICLE_METER_PURPOSE,
        requested_at=datetime.now(UTC),
        extra_intent={"vehicle_id": vehicle_id},
    )
    operation_context = AssetOperationContext.from_organization_context(
        contexto,
        source_id=TypedId.new("api_request"),
    )

    def _handler() -> CanonicalPayload:
        try:
            vehicle = service.record_meter_reading(
                operation_context,
                parsed_vehicle_id,
                kind=body.kind,
                value=body.value,
                observed_at=body.observed_at,
                recorded_at=datetime.now(UTC),
                source=body.source,
                expected_version=body.expected_version,
            )
        except VehicleNaoEncontrado as exc:
            raise _not_found(str(exc)) from exc
        except OptimisticConcurrencyConflict as exc:
            raise DomainProblem(
                status_code=status.HTTP_409_CONFLICT,
                reason_code=OptimisticConcurrencyConflict.code,
                title="Versão de agregado conflitante",
                detail="A versão informada não corresponde à versão atual do Vehicle.",
            ) from exc
        except ValueError as exc:
            raise _domain_conflict(str(exc)) from exc
        response = _vehicle_detail(vehicle)
        return CanonicalPayload(
            schema="asset.record_vehicle_meter_reading.response",
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

    return VehicleDetailResponse.model_validate(
        _canonical_response_data(execution.result_canonical_bytes)
    )


@router.post(
    "/vehicles/{vehicle_id}/meter-readings/{reading_id}/corrections",
    response_model=VehicleDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Corrigir leitura de medidor de um Vehicle",
    responses=RESPOSTAS_PADRAO,
)
def corrigir_leitura_medidor_vehicle(
    vehicle_id: str,
    reading_id: str,
    body: CorrectVehicleMeterReadingRequest,
    contexto: Annotated[OrganizationContext, Depends(require_vehicle_correct_meter)],
    idempotency_key: Annotated[str, Header(alias=IDEMPOTENCY_HEADER, min_length=1)],
    service: Annotated[VehicleService, Depends(get_vehicle_service)],
    idempotency_service: Annotated[IdempotencyService, Depends(get_idempotency_service)],
) -> VehicleDetailResponse:
    parsed_vehicle_id = _typed_id_or_problem(vehicle_id, entity_type="vehicle", campo="vehicle_id")
    parsed_reading_id = _typed_id_or_problem(
        reading_id,
        entity_type="vehicle_meter_reading",
        campo="reading_id",
    )
    request = _idempotency_request(
        body=body,
        contexto=contexto,
        idempotency_key=idempotency_key,
        operation=CORRECT_VEHICLE_METER_OPERATION,
        purpose=CORRECT_VEHICLE_METER_PURPOSE,
        requested_at=datetime.now(UTC),
        extra_intent={"vehicle_id": vehicle_id, "reading_id": reading_id},
    )
    operation_context = AssetOperationContext.from_organization_context(
        contexto,
        source_id=TypedId.new("api_request"),
    )

    def _handler() -> CanonicalPayload:
        try:
            vehicle = service.correct_meter_reading(
                operation_context,
                parsed_vehicle_id,
                original_reading_id=parsed_reading_id,
                corrected_value=body.corrected_value,
                reason=body.reason,
                corrected_at=datetime.now(UTC),
                expected_version=body.expected_version,
            )
        except (VehicleNaoEncontrado, KeyError) as exc:
            raise _not_found(str(exc)) from exc
        except OptimisticConcurrencyConflict as exc:
            raise DomainProblem(
                status_code=status.HTTP_409_CONFLICT,
                reason_code=OptimisticConcurrencyConflict.code,
                title="Versão de agregado conflitante",
                detail="A versão informada não corresponde à versão atual do Vehicle.",
            ) from exc
        except ValueError as exc:
            raise _domain_conflict(str(exc)) from exc
        response = _vehicle_detail(vehicle)
        return CanonicalPayload(
            schema="asset.correct_vehicle_meter_reading.response",
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

    return VehicleDetailResponse.model_validate(
        _canonical_response_data(execution.result_canonical_bytes)
    )


@router.post(
    "/vehicles/{vehicle_id}/transition-lifecycle",
    response_model=VehicleDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Transicionar o ciclo de vida de um Vehicle",
    responses=RESPOSTAS_PADRAO,
)
def transicionar_ciclo_de_vida_vehicle(
    vehicle_id: str,
    body: TransitionVehicleLifecycleRequest,
    contexto: Annotated[OrganizationContext, Depends(require_vehicle_transition)],
    idempotency_key: Annotated[str, Header(alias=IDEMPOTENCY_HEADER, min_length=1)],
    service: Annotated[VehicleService, Depends(get_vehicle_service)],
    idempotency_service: Annotated[IdempotencyService, Depends(get_idempotency_service)],
) -> VehicleDetailResponse:
    parsed_vehicle_id = _typed_id_or_problem(vehicle_id, entity_type="vehicle", campo="vehicle_id")
    request = _idempotency_request(
        body=body,
        contexto=contexto,
        idempotency_key=idempotency_key,
        operation=TRANSITION_VEHICLE_LIFECYCLE_OPERATION,
        purpose=TRANSITION_VEHICLE_LIFECYCLE_PURPOSE,
        requested_at=datetime.now(UTC),
        extra_intent={"vehicle_id": vehicle_id},
    )
    operation_context = AssetOperationContext.from_organization_context(
        contexto,
        source_id=TypedId.new("api_request"),
    )

    def _handler() -> CanonicalPayload:
        try:
            vehicle = service.transition_lifecycle(
                operation_context,
                parsed_vehicle_id,
                new_state=body.new_state,
                reason=body.reason,
                expected_version=body.expected_version,
                occurred_at=datetime.now(UTC),
            )
        except VehicleNaoEncontrado as exc:
            raise _not_found(str(exc)) from exc
        except OptimisticConcurrencyConflict as exc:
            raise DomainProblem(
                status_code=status.HTTP_409_CONFLICT,
                reason_code=OptimisticConcurrencyConflict.code,
                title="Versão de agregado conflitante",
                detail="A versão informada não corresponde à versão atual do Vehicle.",
            ) from exc
        except ValueError as exc:
            raise _domain_conflict(str(exc)) from exc
        response = _vehicle_detail(vehicle)
        return CanonicalPayload(
            schema="asset.transition_vehicle_lifecycle.response",
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

    return VehicleDetailResponse.model_validate(
        _canonical_response_data(execution.result_canonical_bytes)
    )


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


@router.post(
    "/work-orders/{work_order_id}/tasks",
    response_model=WorkOrderDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Adicionar tarefa a uma WorkOrder",
    responses=RESPOSTAS_PADRAO,
)
def adicionar_tarefa_work_order(
    work_order_id: str,
    body: AddWorkOrderTaskRequest,
    contexto: Annotated[OrganizationContext, Depends(require_work_order_add_task)],
    idempotency_key: Annotated[str, Header(alias=IDEMPOTENCY_HEADER, min_length=1)],
    service: Annotated[WorkOrderService, Depends(get_open_work_order_service)],
    idempotency_service: Annotated[IdempotencyService, Depends(get_idempotency_service)],
) -> WorkOrderDetailResponse:
    parsed_work_order_id = _typed_id_or_problem(
        work_order_id, entity_type="work_order", campo="work_order_id"
    )
    request = _idempotency_request(
        body=body,
        contexto=contexto,
        idempotency_key=idempotency_key,
        operation=ADD_WORK_ORDER_TASK_OPERATION,
        purpose=ADD_WORK_ORDER_TASK_PURPOSE,
        requested_at=datetime.now(UTC),
        extra_intent={"work_order_id": work_order_id},
    )
    operation_context = AssetOperationContext.from_organization_context(
        contexto,
        source_id=TypedId.new("api_request"),
    )

    def _handler() -> CanonicalPayload:
        try:
            work_order = service.add_task(
                operation_context,
                parsed_work_order_id,
                description=body.description,
                mandatory=body.mandatory,
                expected_version=body.expected_version,
                occurred_at=datetime.now(UTC),
            )
        except WorkOrderNaoEncontrada as exc:
            raise _not_found(str(exc)) from exc
        except OptimisticConcurrencyConflict as exc:
            raise _version_conflict() from exc
        except ValueError as exc:
            raise _domain_conflict(str(exc)) from exc
        response = _work_order_detail(work_order)
        return CanonicalPayload(
            schema="asset.add_work_order_task.response",
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


@router.post(
    "/work-orders/{work_order_id}/material-demands",
    response_model=WorkOrderDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Demandar material para uma tarefa de WorkOrder",
    responses=RESPOSTAS_PADRAO,
)
def demandar_material_work_order(
    work_order_id: str,
    body: DemandMaterialRequest,
    contexto: Annotated[OrganizationContext, Depends(require_work_order_demand_material)],
    idempotency_key: Annotated[str, Header(alias=IDEMPOTENCY_HEADER, min_length=1)],
    service: Annotated[WorkOrderService, Depends(get_open_work_order_service)],
    idempotency_service: Annotated[IdempotencyService, Depends(get_idempotency_service)],
) -> WorkOrderDetailResponse:
    parsed_work_order_id = _typed_id_or_problem(
        work_order_id, entity_type="work_order", campo="work_order_id"
    )
    part_id = _typed_id_or_problem(body.part_id, entity_type="part", campo="part_id")
    task_id = _typed_id_or_problem(body.task_id, entity_type="work_task", campo="task_id")
    request = _idempotency_request(
        body=body,
        contexto=contexto,
        idempotency_key=idempotency_key,
        operation=DEMAND_MATERIAL_OPERATION,
        purpose=DEMAND_MATERIAL_PURPOSE,
        requested_at=datetime.now(UTC),
        extra_intent={"work_order_id": work_order_id},
    )
    operation_context = AssetOperationContext.from_organization_context(
        contexto,
        source_id=TypedId.new("api_request"),
    )

    def _handler() -> CanonicalPayload:
        try:
            work_order = service.demand_material(
                operation_context,
                parsed_work_order_id,
                part_ref=part_id,
                qty=body.qty,
                task_id=task_id,
                expected_version=body.expected_version,
                occurred_at=datetime.now(UTC),
            )
        except (WorkOrderNaoEncontrada, PartNaoEncontrado, KeyError) as exc:
            raise _not_found(str(exc)) from exc
        except OptimisticConcurrencyConflict as exc:
            raise _version_conflict() from exc
        except ValueError as exc:
            raise _domain_conflict(str(exc)) from exc
        response = _work_order_detail(work_order)
        return CanonicalPayload(
            schema="asset.demand_work_order_material.response",
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


@router.post(
    "/work-orders/{work_order_id}/material-reservations",
    response_model=WorkOrderDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Reservar material demandado por uma WorkOrder",
    responses=RESPOSTAS_PADRAO,
)
def reservar_material_work_order(
    work_order_id: str,
    body: ReserveWorkOrderMaterialRequest,
    contexto: Annotated[OrganizationContext, Depends(require_work_order_reserve_material)],
    idempotency_key: Annotated[str, Header(alias=IDEMPOTENCY_HEADER, min_length=1)],
    service: Annotated[WorkOrderService, Depends(get_open_work_order_service)],
    event_log: Annotated[DomainEventRepository, Depends(get_domain_event_repository)],
    idempotency_service: Annotated[IdempotencyService, Depends(get_idempotency_service)],
) -> WorkOrderDetailResponse:
    parsed_work_order_id = _typed_id_or_problem(
        work_order_id, entity_type="work_order", campo="work_order_id"
    )
    stock_position_id = _typed_id_or_problem(
        body.stock_position_id,
        entity_type="stock_position",
        campo="stock_position_id",
    )
    part_id = _typed_id_or_problem(body.part_id, entity_type="part", campo="part_id")
    entitlement_event_id = _typed_id_or_problem(
        body.entitlement_event_id,
        entity_type="event",
        campo="entitlement_event_id",
    )
    occurred_at = datetime.now(UTC)
    request = _idempotency_request(
        body=body,
        contexto=contexto,
        idempotency_key=idempotency_key,
        operation=RESERVE_WORK_ORDER_MATERIAL_OPERATION,
        purpose=RESERVE_WORK_ORDER_MATERIAL_PURPOSE,
        requested_at=occurred_at,
        extra_intent={"work_order_id": work_order_id},
    )
    operation_context = AssetOperationContext.from_organization_context(
        contexto,
        source_id=TypedId.new("api_request"),
    )

    def _handler() -> CanonicalPayload:
        try:
            entitlement = _entitlement_resolution_from_event(event_log, entitlement_event_id)
            work_order = service.reserve_material_for_work_order(
                operation_context,
                parsed_work_order_id,
                stock_position_id=stock_position_id,
                part_ref=part_id,
                qty=body.qty,
                priority=body.priority,
                entitlement=entitlement,
                occurred_at=occurred_at,
                expected_version=body.expected_version,
            )
        except (WorkOrderNaoEncontrada, KeyError) as exc:
            raise _not_found(str(exc)) from exc
        except OptimisticConcurrencyConflict as exc:
            raise _version_conflict() from exc
        except ValueError as exc:
            raise _domain_conflict(str(exc)) from exc
        response = _work_order_detail(work_order)
        return CanonicalPayload(
            schema="asset.reserve_work_order_material.response",
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


@router.post(
    "/work-orders/{work_order_id}/mark-planned",
    response_model=WorkOrderDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Marcar uma WorkOrder como planejada",
    responses=RESPOSTAS_PADRAO,
)
def marcar_work_order_planejada(
    work_order_id: str,
    body: MarkWorkOrderPlannedRequest,
    contexto: Annotated[OrganizationContext, Depends(require_work_order_transition)],
    idempotency_key: Annotated[str, Header(alias=IDEMPOTENCY_HEADER, min_length=1)],
    service: Annotated[WorkOrderService, Depends(get_open_work_order_service)],
    idempotency_service: Annotated[IdempotencyService, Depends(get_idempotency_service)],
) -> WorkOrderDetailResponse:
    parsed_work_order_id = _typed_id_or_problem(
        work_order_id, entity_type="work_order", campo="work_order_id"
    )
    request = _idempotency_request(
        body=body,
        contexto=contexto,
        idempotency_key=idempotency_key,
        operation=MARK_WORK_ORDER_PLANNED_OPERATION,
        purpose=MARK_WORK_ORDER_PLANNED_PURPOSE,
        requested_at=datetime.now(UTC),
        extra_intent={"work_order_id": work_order_id},
    )
    operation_context = AssetOperationContext.from_organization_context(
        contexto,
        source_id=TypedId.new("api_request"),
    )

    def _handler() -> CanonicalPayload:
        try:
            work_order = service.mark_planned(
                operation_context,
                parsed_work_order_id,
                expected_version=body.expected_version,
                occurred_at=datetime.now(UTC),
            )
        except WorkOrderNaoEncontrada as exc:
            raise _not_found(str(exc)) from exc
        except OptimisticConcurrencyConflict as exc:
            raise _version_conflict() from exc
        except ValueError as exc:
            raise _domain_conflict(str(exc)) from exc
        response = _work_order_detail(work_order)
        return CanonicalPayload(
            schema="asset.mark_work_order_planned.response",
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


@router.post(
    "/work-orders/{work_order_id}/mark-ready",
    response_model=WorkOrderDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Marcar uma WorkOrder como pronta",
    responses=RESPOSTAS_PADRAO,
)
def marcar_work_order_pronta(
    work_order_id: str,
    body: MarkWorkOrderReadyRequest,
    contexto: Annotated[OrganizationContext, Depends(require_work_order_transition)],
    idempotency_key: Annotated[str, Header(alias=IDEMPOTENCY_HEADER, min_length=1)],
    service: Annotated[WorkOrderService, Depends(get_open_work_order_service)],
    idempotency_service: Annotated[IdempotencyService, Depends(get_idempotency_service)],
) -> WorkOrderDetailResponse:
    parsed_work_order_id = _typed_id_or_problem(
        work_order_id, entity_type="work_order", campo="work_order_id"
    )
    request = _idempotency_request(
        body=body,
        contexto=contexto,
        idempotency_key=idempotency_key,
        operation=MARK_WORK_ORDER_READY_OPERATION,
        purpose=MARK_WORK_ORDER_READY_PURPOSE,
        requested_at=datetime.now(UTC),
        extra_intent={"work_order_id": work_order_id},
    )
    operation_context = AssetOperationContext.from_organization_context(
        contexto,
        source_id=TypedId.new("api_request"),
    )

    def _handler() -> CanonicalPayload:
        try:
            work_order = service.mark_ready(
                operation_context,
                parsed_work_order_id,
                expected_version=body.expected_version,
                occurred_at=datetime.now(UTC),
            )
        except WorkOrderNaoEncontrada as exc:
            raise _not_found(str(exc)) from exc
        except OptimisticConcurrencyConflict as exc:
            raise _version_conflict() from exc
        except ValueError as exc:
            raise _domain_conflict(str(exc)) from exc
        response = _work_order_detail(work_order)
        return CanonicalPayload(
            schema="asset.mark_work_order_ready.response",
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


@router.post(
    "/work-orders/{work_order_id}/schedule",
    response_model=WorkOrderDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Agendar uma WorkOrder",
    responses=RESPOSTAS_PADRAO,
)
def agendar_work_order(
    work_order_id: str,
    body: ScheduleWorkOrderRequest,
    contexto: Annotated[OrganizationContext, Depends(require_work_order_transition)],
    idempotency_key: Annotated[str, Header(alias=IDEMPOTENCY_HEADER, min_length=1)],
    service: Annotated[WorkOrderService, Depends(get_open_work_order_service)],
    idempotency_service: Annotated[IdempotencyService, Depends(get_idempotency_service)],
) -> WorkOrderDetailResponse:
    parsed_work_order_id = _typed_id_or_problem(
        work_order_id, entity_type="work_order", campo="work_order_id"
    )
    request = _idempotency_request(
        body=body,
        contexto=contexto,
        idempotency_key=idempotency_key,
        operation=SCHEDULE_WORK_ORDER_OPERATION,
        purpose=SCHEDULE_WORK_ORDER_PURPOSE,
        requested_at=datetime.now(UTC),
        extra_intent={"work_order_id": work_order_id},
    )
    operation_context = AssetOperationContext.from_organization_context(
        contexto,
        source_id=TypedId.new("api_request"),
    )

    def _handler() -> CanonicalPayload:
        try:
            work_order = service.schedule(
                operation_context,
                parsed_work_order_id,
                technician_and_workshop_allocated=body.technician_and_workshop_allocated,
                expected_version=body.expected_version,
                occurred_at=datetime.now(UTC),
            )
        except WorkOrderNaoEncontrada as exc:
            raise _not_found(str(exc)) from exc
        except OptimisticConcurrencyConflict as exc:
            raise _version_conflict() from exc
        except ValueError as exc:
            raise _domain_conflict(str(exc)) from exc
        response = _work_order_detail(work_order)
        return CanonicalPayload(
            schema="asset.schedule_work_order.response",
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


@router.post(
    "/work-orders/{work_order_id}/mark-waiting-technician",
    response_model=WorkOrderDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Marcar uma WorkOrder como aguardando técnico",
    responses=RESPOSTAS_PADRAO,
)
def marcar_work_order_aguardando_tecnico(
    work_order_id: str,
    body: MarkWorkOrderWaitingTechnicianRequest,
    contexto: Annotated[OrganizationContext, Depends(require_work_order_transition)],
    idempotency_key: Annotated[str, Header(alias=IDEMPOTENCY_HEADER, min_length=1)],
    service: Annotated[WorkOrderService, Depends(get_open_work_order_service)],
    idempotency_service: Annotated[IdempotencyService, Depends(get_idempotency_service)],
) -> WorkOrderDetailResponse:
    parsed_work_order_id = _typed_id_or_problem(
        work_order_id, entity_type="work_order", campo="work_order_id"
    )
    request = _idempotency_request(
        body=body,
        contexto=contexto,
        idempotency_key=idempotency_key,
        operation=MARK_WORK_ORDER_WAITING_TECHNICIAN_OPERATION,
        purpose=MARK_WORK_ORDER_WAITING_TECHNICIAN_PURPOSE,
        requested_at=datetime.now(UTC),
        extra_intent={"work_order_id": work_order_id},
    )
    operation_context = AssetOperationContext.from_organization_context(
        contexto,
        source_id=TypedId.new("api_request"),
    )

    def _handler() -> CanonicalPayload:
        try:
            work_order = service.mark_waiting_technician(
                operation_context,
                parsed_work_order_id,
                expected_version=body.expected_version,
                occurred_at=datetime.now(UTC),
            )
        except WorkOrderNaoEncontrada as exc:
            raise _not_found(str(exc)) from exc
        except OptimisticConcurrencyConflict as exc:
            raise _version_conflict() from exc
        except ValueError as exc:
            raise _domain_conflict(str(exc)) from exc
        response = _work_order_detail(work_order)
        return CanonicalPayload(
            schema="asset.mark_work_order_waiting_technician.response",
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


@router.post(
    "/work-orders/{work_order_id}/start-progress",
    response_model=WorkOrderDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Iniciar execução de uma WorkOrder",
    responses=RESPOSTAS_PADRAO,
)
def iniciar_execucao_work_order(
    work_order_id: str,
    body: StartWorkOrderProgressRequest,
    contexto: Annotated[OrganizationContext, Depends(require_work_order_transition)],
    idempotency_key: Annotated[str, Header(alias=IDEMPOTENCY_HEADER, min_length=1)],
    service: Annotated[WorkOrderService, Depends(get_open_work_order_service)],
    idempotency_service: Annotated[IdempotencyService, Depends(get_idempotency_service)],
) -> WorkOrderDetailResponse:
    parsed_work_order_id = _typed_id_or_problem(
        work_order_id, entity_type="work_order", campo="work_order_id"
    )
    request = _idempotency_request(
        body=body,
        contexto=contexto,
        idempotency_key=idempotency_key,
        operation=START_WORK_ORDER_PROGRESS_OPERATION,
        purpose=START_WORK_ORDER_PROGRESS_PURPOSE,
        requested_at=datetime.now(UTC),
        extra_intent={"work_order_id": work_order_id},
    )
    operation_context = AssetOperationContext.from_organization_context(
        contexto,
        source_id=TypedId.new("api_request"),
    )

    def _handler() -> CanonicalPayload:
        try:
            work_order = service.start_progress(
                operation_context,
                parsed_work_order_id,
                vehicle_in_maintenance=body.vehicle_in_maintenance,
                expected_version=body.expected_version,
                occurred_at=datetime.now(UTC),
            )
        except WorkOrderNaoEncontrada as exc:
            raise _not_found(str(exc)) from exc
        except OptimisticConcurrencyConflict as exc:
            raise _version_conflict() from exc
        except ValueError as exc:
            raise _domain_conflict(str(exc)) from exc
        response = _work_order_detail(work_order)
        return CanonicalPayload(
            schema="asset.start_work_order_progress.response",
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


@router.post(
    "/work-orders/{work_order_id}/interrupt",
    response_model=WorkOrderDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Interromper uma WorkOrder em execução",
    responses=RESPOSTAS_PADRAO,
)
def interromper_work_order(
    work_order_id: str,
    body: InterruptWorkOrderRequest,
    contexto: Annotated[OrganizationContext, Depends(require_work_order_transition)],
    idempotency_key: Annotated[str, Header(alias=IDEMPOTENCY_HEADER, min_length=1)],
    service: Annotated[WorkOrderService, Depends(get_open_work_order_service)],
    idempotency_service: Annotated[IdempotencyService, Depends(get_idempotency_service)],
) -> WorkOrderDetailResponse:
    parsed_work_order_id = _typed_id_or_problem(
        work_order_id, entity_type="work_order", campo="work_order_id"
    )
    request = _idempotency_request(
        body=body,
        contexto=contexto,
        idempotency_key=idempotency_key,
        operation=INTERRUPT_WORK_ORDER_OPERATION,
        purpose=INTERRUPT_WORK_ORDER_PURPOSE,
        requested_at=datetime.now(UTC),
        extra_intent={"work_order_id": work_order_id},
    )
    operation_context = AssetOperationContext.from_organization_context(
        contexto,
        source_id=TypedId.new("api_request"),
    )

    def _handler() -> CanonicalPayload:
        try:
            work_order = service.interrupt(
                operation_context,
                parsed_work_order_id,
                reason=body.reason,
                expected_version=body.expected_version,
                occurred_at=datetime.now(UTC),
            )
        except WorkOrderNaoEncontrada as exc:
            raise _not_found(str(exc)) from exc
        except OptimisticConcurrencyConflict as exc:
            raise _version_conflict() from exc
        except ValueError as exc:
            raise _domain_conflict(str(exc)) from exc
        response = _work_order_detail(work_order)
        return CanonicalPayload(
            schema="asset.interrupt_work_order.response",
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


@router.post(
    "/work-orders/{work_order_id}/resume",
    response_model=WorkOrderDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Retomar uma WorkOrder interrompida",
    responses=RESPOSTAS_PADRAO,
)
def retomar_work_order(
    work_order_id: str,
    body: ResumeWorkOrderRequest,
    contexto: Annotated[OrganizationContext, Depends(require_work_order_transition)],
    idempotency_key: Annotated[str, Header(alias=IDEMPOTENCY_HEADER, min_length=1)],
    service: Annotated[WorkOrderService, Depends(get_open_work_order_service)],
    idempotency_service: Annotated[IdempotencyService, Depends(get_idempotency_service)],
) -> WorkOrderDetailResponse:
    parsed_work_order_id = _typed_id_or_problem(
        work_order_id, entity_type="work_order", campo="work_order_id"
    )
    request = _idempotency_request(
        body=body,
        contexto=contexto,
        idempotency_key=idempotency_key,
        operation=RESUME_WORK_ORDER_OPERATION,
        purpose=RESUME_WORK_ORDER_PURPOSE,
        requested_at=datetime.now(UTC),
        extra_intent={"work_order_id": work_order_id},
    )
    operation_context = AssetOperationContext.from_organization_context(
        contexto,
        source_id=TypedId.new("api_request"),
    )

    def _handler() -> CanonicalPayload:
        try:
            work_order = service.resume(
                operation_context,
                parsed_work_order_id,
                expected_version=body.expected_version,
                occurred_at=datetime.now(UTC),
            )
        except WorkOrderNaoEncontrada as exc:
            raise _not_found(str(exc)) from exc
        except OptimisticConcurrencyConflict as exc:
            raise _version_conflict() from exc
        except ValueError as exc:
            raise _domain_conflict(str(exc)) from exc
        response = _work_order_detail(work_order)
        return CanonicalPayload(
            schema="asset.resume_work_order.response",
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


@router.post(
    "/work-orders/{work_order_id}/tasks/start",
    response_model=WorkOrderDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Iniciar uma tarefa de WorkOrder em execução",
    responses=RESPOSTAS_PADRAO,
)
def iniciar_tarefa_work_order(
    work_order_id: str,
    body: StartWorkOrderTaskRequest,
    contexto: Annotated[OrganizationContext, Depends(require_work_order_execute)],
    idempotency_key: Annotated[str, Header(alias=IDEMPOTENCY_HEADER, min_length=1)],
    service: Annotated[WorkOrderService, Depends(get_open_work_order_service)],
    idempotency_service: Annotated[IdempotencyService, Depends(get_idempotency_service)],
) -> WorkOrderDetailResponse:
    parsed_work_order_id = _typed_id_or_problem(
        work_order_id, entity_type="work_order", campo="work_order_id"
    )
    task_id = _typed_id_or_problem(body.task_id, entity_type="work_task", campo="task_id")
    request = _idempotency_request(
        body=body,
        contexto=contexto,
        idempotency_key=idempotency_key,
        operation=START_WORK_ORDER_TASK_OPERATION,
        purpose=START_WORK_ORDER_TASK_PURPOSE,
        requested_at=datetime.now(UTC),
        extra_intent={"work_order_id": work_order_id},
    )
    operation_context = AssetOperationContext.from_organization_context(
        contexto,
        source_id=TypedId.new("api_request"),
    )

    def _handler() -> CanonicalPayload:
        try:
            work_order = service.start_task(
                operation_context,
                parsed_work_order_id,
                task_id=task_id,
                expected_version=body.expected_version,
                occurred_at=datetime.now(UTC),
            )
        except WorkOrderNaoEncontrada as exc:
            raise _not_found(str(exc)) from exc
        except OptimisticConcurrencyConflict as exc:
            raise _version_conflict() from exc
        except ValueError as exc:
            raise _domain_conflict(str(exc)) from exc
        response = _work_order_detail(work_order)
        return CanonicalPayload(
            schema="asset.start_work_order_task.response",
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


@router.post(
    "/work-orders/{work_order_id}/tasks/complete",
    response_model=WorkOrderDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Concluir uma tarefa de WorkOrder em execução",
    responses=RESPOSTAS_PADRAO,
)
def concluir_tarefa_work_order(
    work_order_id: str,
    body: CompleteWorkOrderTaskRequest,
    contexto: Annotated[OrganizationContext, Depends(require_work_order_execute)],
    idempotency_key: Annotated[str, Header(alias=IDEMPOTENCY_HEADER, min_length=1)],
    service: Annotated[WorkOrderService, Depends(get_open_work_order_service)],
    idempotency_service: Annotated[IdempotencyService, Depends(get_idempotency_service)],
) -> WorkOrderDetailResponse:
    parsed_work_order_id = _typed_id_or_problem(
        work_order_id, entity_type="work_order", campo="work_order_id"
    )
    task_id = _typed_id_or_problem(body.task_id, entity_type="work_task", campo="task_id")
    request = _idempotency_request(
        body=body,
        contexto=contexto,
        idempotency_key=idempotency_key,
        operation=COMPLETE_WORK_ORDER_TASK_OPERATION,
        purpose=COMPLETE_WORK_ORDER_TASK_PURPOSE,
        requested_at=datetime.now(UTC),
        extra_intent={"work_order_id": work_order_id},
    )
    operation_context = AssetOperationContext.from_organization_context(
        contexto,
        source_id=TypedId.new("api_request"),
    )

    def _handler() -> CanonicalPayload:
        try:
            work_order = service.complete_task(
                operation_context,
                parsed_work_order_id,
                task_id=task_id,
                labor_entry=body.labor_entry,
                expected_version=body.expected_version,
                occurred_at=datetime.now(UTC),
            )
        except WorkOrderNaoEncontrada as exc:
            raise _not_found(str(exc)) from exc
        except OptimisticConcurrencyConflict as exc:
            raise _version_conflict() from exc
        except ValueError as exc:
            raise _domain_conflict(str(exc)) from exc
        response = _work_order_detail(work_order)
        return CanonicalPayload(
            schema="asset.complete_work_order_task.response",
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


@router.post(
    "/work-orders/{work_order_id}/removed-components",
    response_model=WorkOrderDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Registrar componente removido de uma WorkOrder",
    responses=RESPOSTAS_PADRAO,
)
def registrar_componente_removido_work_order(
    work_order_id: str,
    body: RecordRemovedComponentRequest,
    contexto: Annotated[OrganizationContext, Depends(require_work_order_record_removal)],
    idempotency_key: Annotated[str, Header(alias=IDEMPOTENCY_HEADER, min_length=1)],
    service: Annotated[WorkOrderService, Depends(get_open_work_order_service)],
    idempotency_service: Annotated[IdempotencyService, Depends(get_idempotency_service)],
) -> WorkOrderDetailResponse:
    parsed_work_order_id = _typed_id_or_problem(
        work_order_id, entity_type="work_order", campo="work_order_id"
    )
    part_ref = _typed_id_or_problem(body.part_id, entity_type="part", campo="part_id")
    request = _idempotency_request(
        body=body,
        contexto=contexto,
        idempotency_key=idempotency_key,
        operation=RECORD_REMOVED_COMPONENT_OPERATION,
        purpose=RECORD_REMOVED_COMPONENT_PURPOSE,
        requested_at=datetime.now(UTC),
        extra_intent={"work_order_id": work_order_id},
    )
    operation_context = AssetOperationContext.from_organization_context(
        contexto,
        source_id=TypedId.new("api_request"),
    )

    def _handler() -> CanonicalPayload:
        try:
            work_order = service.record_removed_component(
                operation_context,
                parsed_work_order_id,
                part_ref=part_ref,
                disposition=body.disposition,
                serial=body.serial,
                expected_version=body.expected_version,
                occurred_at=datetime.now(UTC),
            )
        except WorkOrderNaoEncontrada as exc:
            raise _not_found(str(exc)) from exc
        except OptimisticConcurrencyConflict as exc:
            raise _version_conflict() from exc
        except ValueError as exc:
            raise _domain_conflict(str(exc)) from exc
        response = _work_order_detail(work_order)
        return CanonicalPayload(
            schema="asset.record_removed_component.response",
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


@router.post(
    "/work-orders/{work_order_id}/complete-technically",
    response_model=WorkOrderDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Concluir tecnicamente uma WorkOrder",
    responses=RESPOSTAS_PADRAO,
)
def concluir_tecnicamente_work_order(
    work_order_id: str,
    body: CompleteWorkOrderTechnicallyRequest,
    contexto: Annotated[OrganizationContext, Depends(require_work_order_tech_complete)],
    idempotency_key: Annotated[str, Header(alias=IDEMPOTENCY_HEADER, min_length=1)],
    service: Annotated[WorkOrderService, Depends(get_open_work_order_service)],
    idempotency_service: Annotated[IdempotencyService, Depends(get_idempotency_service)],
) -> WorkOrderDetailResponse:
    parsed_work_order_id = _typed_id_or_problem(
        work_order_id, entity_type="work_order", campo="work_order_id"
    )
    request = _idempotency_request(
        body=body,
        contexto=contexto,
        idempotency_key=idempotency_key,
        operation=COMPLETE_WORK_ORDER_TECHNICALLY_OPERATION,
        purpose=COMPLETE_WORK_ORDER_TECHNICALLY_PURPOSE,
        requested_at=datetime.now(UTC),
        extra_intent={"work_order_id": work_order_id},
    )
    operation_context = AssetOperationContext.from_organization_context(
        contexto,
        source_id=TypedId.new("api_request"),
    )

    def _handler() -> CanonicalPayload:
        try:
            work_order = service.complete_technically(
                operation_context,
                parsed_work_order_id,
                diagnosis=body.diagnosis,
                root_cause=body.root_cause,
                resolution=body.resolution,
                expected_version=body.expected_version,
                occurred_at=datetime.now(UTC),
            )
        except WorkOrderNaoEncontrada as exc:
            raise _not_found(str(exc)) from exc
        except OptimisticConcurrencyConflict as exc:
            raise _version_conflict() from exc
        except ValueError as exc:
            raise _domain_conflict(str(exc)) from exc
        response = _work_order_detail(work_order)
        return CanonicalPayload(
            schema="asset.complete_work_order_technically.response",
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


@router.post(
    "/work-orders/{work_order_id}/send-to-validation",
    response_model=WorkOrderDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Enviar uma WorkOrder para validação pós-manutenção",
    responses=RESPOSTAS_PADRAO,
)
def enviar_work_order_para_validacao(
    work_order_id: str,
    body: SendWorkOrderToValidationRequest,
    contexto: Annotated[OrganizationContext, Depends(require_work_order_validate)],
    idempotency_key: Annotated[str, Header(alias=IDEMPOTENCY_HEADER, min_length=1)],
    service: Annotated[WorkOrderService, Depends(get_open_work_order_service)],
    idempotency_service: Annotated[IdempotencyService, Depends(get_idempotency_service)],
) -> WorkOrderDetailResponse:
    parsed_work_order_id = _typed_id_or_problem(
        work_order_id, entity_type="work_order", campo="work_order_id"
    )
    request = _idempotency_request(
        body=body,
        contexto=contexto,
        idempotency_key=idempotency_key,
        operation=SEND_WORK_ORDER_TO_VALIDATION_OPERATION,
        purpose=SEND_WORK_ORDER_TO_VALIDATION_PURPOSE,
        requested_at=datetime.now(UTC),
        extra_intent={"work_order_id": work_order_id},
    )
    operation_context = AssetOperationContext.from_organization_context(
        contexto,
        source_id=TypedId.new("api_request"),
    )

    def _handler() -> CanonicalPayload:
        try:
            work_order = service.send_to_validation(
                operation_context,
                parsed_work_order_id,
                expected_version=body.expected_version,
                occurred_at=datetime.now(UTC),
            )
        except WorkOrderNaoEncontrada as exc:
            raise _not_found(str(exc)) from exc
        except OptimisticConcurrencyConflict as exc:
            raise _version_conflict() from exc
        except ValueError as exc:
            raise _domain_conflict(str(exc)) from exc
        response = _work_order_detail(work_order)
        return CanonicalPayload(
            schema="asset.send_work_order_to_validation.response",
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


@router.post(
    "/work-orders/{work_order_id}/fail-validation",
    response_model=WorkOrderDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Reprovar a validação pós-manutenção de uma WorkOrder",
    responses=RESPOSTAS_PADRAO,
)
def reprovar_validacao_work_order(
    work_order_id: str,
    body: FailWorkOrderValidationRequest,
    contexto: Annotated[OrganizationContext, Depends(require_work_order_validate)],
    idempotency_key: Annotated[str, Header(alias=IDEMPOTENCY_HEADER, min_length=1)],
    service: Annotated[WorkOrderService, Depends(get_open_work_order_service)],
    idempotency_service: Annotated[IdempotencyService, Depends(get_idempotency_service)],
) -> WorkOrderDetailResponse:
    parsed_work_order_id = _typed_id_or_problem(
        work_order_id, entity_type="work_order", campo="work_order_id"
    )
    request = _idempotency_request(
        body=body,
        contexto=contexto,
        idempotency_key=idempotency_key,
        operation=FAIL_WORK_ORDER_VALIDATION_OPERATION,
        purpose=FAIL_WORK_ORDER_VALIDATION_PURPOSE,
        requested_at=datetime.now(UTC),
        extra_intent={"work_order_id": work_order_id},
    )
    operation_context = AssetOperationContext.from_organization_context(
        contexto,
        source_id=TypedId.new("api_request"),
    )

    def _handler() -> CanonicalPayload:
        try:
            work_order = service.perform_post_maintenance_validation(
                operation_context,
                parsed_work_order_id,
                validator_ref=contexto.actor_id,
                reason=body.reason,
                notes=body.notes,
                expected_version=body.expected_version,
                occurred_at=datetime.now(UTC),
            )
        except WorkOrderNaoEncontrada as exc:
            raise _not_found(str(exc)) from exc
        except OptimisticConcurrencyConflict as exc:
            raise _version_conflict() from exc
        except ValueError as exc:
            raise _domain_conflict(str(exc)) from exc
        response = _work_order_detail(work_order)
        return CanonicalPayload(
            schema="asset.fail_work_order_validation.response",
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


@router.post(
    "/work-orders/{work_order_id}/close",
    response_model=WorkOrderDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Fechar uma WorkOrder aprovada na validação pós-manutenção",
    responses=RESPOSTAS_PADRAO,
)
def fechar_work_order(
    work_order_id: str,
    body: CloseWorkOrderRequest,
    contexto: Annotated[OrganizationContext, Depends(require_work_order_close)],
    idempotency_key: Annotated[str, Header(alias=IDEMPOTENCY_HEADER, min_length=1)],
    service: Annotated[WorkOrderService, Depends(get_open_work_order_service)],
    idempotency_service: Annotated[IdempotencyService, Depends(get_idempotency_service)],
) -> WorkOrderDetailResponse:
    parsed_work_order_id = _typed_id_or_problem(
        work_order_id, entity_type="work_order", campo="work_order_id"
    )
    request = _idempotency_request(
        body=body,
        contexto=contexto,
        idempotency_key=idempotency_key,
        operation=CLOSE_WORK_ORDER_OPERATION,
        purpose=CLOSE_WORK_ORDER_PURPOSE,
        requested_at=datetime.now(UTC),
        extra_intent={"work_order_id": work_order_id},
    )
    operation_context = AssetOperationContext.from_organization_context(
        contexto,
        source_id=TypedId.new("api_request"),
    )

    def _handler() -> CanonicalPayload:
        try:
            work_order = service.close_work_order(
                operation_context,
                parsed_work_order_id,
                validator_ref=contexto.actor_id,
                notes=body.notes,
                expected_version=body.expected_version,
                occurred_at=datetime.now(UTC),
            )
        except WorkOrderNaoEncontrada as exc:
            raise _not_found(str(exc)) from exc
        except OptimisticConcurrencyConflict as exc:
            raise _version_conflict() from exc
        except ValueError as exc:
            raise _domain_conflict(str(exc)) from exc
        response = _work_order_detail(work_order)
        return CanonicalPayload(
            schema="asset.close_work_order.response",
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


@router.post(
    "/work-orders/{work_order_id}/cancel",
    response_model=WorkOrderDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancelar uma WorkOrder",
    responses=RESPOSTAS_PADRAO,
)
def cancelar_work_order(
    work_order_id: str,
    body: CancelWorkOrderRequest,
    contexto: Annotated[OrganizationContext, Depends(require_work_order_cancel)],
    idempotency_key: Annotated[str, Header(alias=IDEMPOTENCY_HEADER, min_length=1)],
    service: Annotated[WorkOrderService, Depends(get_open_work_order_service)],
    idempotency_service: Annotated[IdempotencyService, Depends(get_idempotency_service)],
) -> WorkOrderDetailResponse:
    parsed_work_order_id = _typed_id_or_problem(
        work_order_id, entity_type="work_order", campo="work_order_id"
    )
    request = _idempotency_request(
        body=body,
        contexto=contexto,
        idempotency_key=idempotency_key,
        operation=CANCEL_WORK_ORDER_OPERATION,
        purpose=CANCEL_WORK_ORDER_PURPOSE,
        requested_at=datetime.now(UTC),
        extra_intent={"work_order_id": work_order_id},
    )
    operation_context = AssetOperationContext.from_organization_context(
        contexto,
        source_id=TypedId.new("api_request"),
    )

    def _handler() -> CanonicalPayload:
        try:
            work_order = service.cancel_work_order(
                operation_context,
                parsed_work_order_id,
                reason=body.reason,
                expected_version=body.expected_version,
                occurred_at=datetime.now(UTC),
            )
        except WorkOrderNaoEncontrada as exc:
            raise _not_found(str(exc)) from exc
        except OptimisticConcurrencyConflict as exc:
            raise _version_conflict() from exc
        except ValueError as exc:
            raise _domain_conflict(str(exc)) from exc
        response = _work_order_detail(work_order)
        return CanonicalPayload(
            schema="asset.cancel_work_order.response",
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
    body: BaseModel,
    contexto: OrganizationContext,
    idempotency_key: str,
    operation: str = OPEN_WORK_ORDER_OPERATION,
    purpose: str = OPEN_WORK_ORDER_PURPOSE,
    requested_at: datetime,
    extra_intent: dict[str, CanonicalValue] | None = None,
) -> IdempotencyRequest:
    return IdempotencyRequest(
        key=idempotency_key,
        organization_id=contexto.organization_id,
        principal_reference=UniversalReference(
            target_id=contexto.user_id,
            organization_id=contexto.organization_id,
            contract_version=1,
        ),
        purpose=purpose,
        operation=operation,
        intent_digest=_intent_digest(body, extra=extra_intent),
        requested_at=requested_at,
    )


def _intent_digest(body: BaseModel, *, extra: dict[str, CanonicalValue] | None = None) -> bytes:
    value = _canonicalize(body.model_dump(mode="python"))
    if not isinstance(value, dict):
        raise TypeError("Request idempotente deve ser um objeto.")
    if extra:
        value.update(extra)
    return hashlib.sha256(CanonicalSerializer().serialize(value)).digest()


def _canonicalize(value: object) -> CanonicalValue:
    if isinstance(value, dict):
        return {str(key): _canonicalize(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_canonicalize(item) for item in value]
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, str | int | bool | datetime) or value is None:
        return value
    raise TypeError(f"Tipo não suportado no digest idempotente: {type(value).__name__}.")


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


def _version_conflict() -> DomainProblem:
    return DomainProblem(
        status_code=status.HTTP_409_CONFLICT,
        reason_code=OptimisticConcurrencyConflict.code,
        title="Versão de agregado conflitante",
        detail="A versão informada não corresponde à versão atual do agregado.",
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
