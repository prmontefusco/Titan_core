"""Caso de uso do agregado `WorkOrder` — Titan Asset (A4, módulo `sustainment`).

O serviço mais complexo do slice: coordena `Vehicle` (retorno ao serviço),
`SLIContract` (congelar `ContractContext` na abertura) e `Inventory`
(reservar/liberar material) além do próprio `WorkOrder`. Cada transição T1‑T17
já é validada pelo domínio (`work_order.py`); este serviço só carrega, chama
o método certo, persiste e grava o evento — e faz a coordenação entre
agregados que `09_COMMAND_MODEL.md` define como fronteira transacional de um
único comando (ex.: `ReserveMaterialForWorkOrder` = `WorkOrder`+`Inventory`;
`CloseWorkOrder` = `WorkOrder`+`Vehicle.ReturnToService`).

**Transições T2‑T12/T14 emitem o mesmo evento genérico**
`work_order_state_changed` (`08_DOMAIN_EVENTS.md`) — só `T13`
(`complete_technically`), `T15` (`fail_validation`), `T16` (`close`) e `T17`
(`cancel`) têm evento próprio.

**`PerformPostMaintenanceValidation` vs `CloseWorkOrder`:** o domínio só tem
`fail_validation` (resultado `FAIL`, volta a `TECHNICALLY_COMPLETE`) e `close`
(resultado `PASS`, fecha a WO) — não existe um terceiro método "registrar
validação sem transicionar". Por isso `perform_post_maintenance_validation`
cobre exclusivamente o caminho `FAIL`; o caminho `PASS` é `close_work_order`,
que já registra a validação **e** fecha no mesmo ato (é o que `close()` faz).

**`WorkOrder.material_reservations` não tem método de domínio próprio**
(`add_task`/`demand_material`/... existem; adicionar uma reserva à tupla,
não) — usa-se `dataclasses.replace()` diretamente, seguro porque o campo não
carrega nenhum invariante do `__post_init__` além de ser uma tupla de
`TypedId`.

**Entitlement (`ResolveEntitlement`/`AuthorizeEntitlementException`, I‑SLI‑4/5)
e o cálculo de `PriorityScore` via `Rule` governada continuam fora** — pedem
`Evaluation`→`Decision` do Core; `recalculate_priority` aqui aceita um
`PriorityScore` já calculado pelo chamador (mesmo padrão de
`InventoryService.reserve_stock` aceitando `cross_purpose_decision_ref` já
resolvido).
"""

from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal
from typing import Protocol

from packages.asset_application.event_recorder import AssetEventRecorder, AssetOperationContext
from packages.asset_application.inventory_service import InventoryService
from packages.asset_application.sustainment_contract_service import SLIContractRepositoryPort
from packages.asset_application.vehicle_service import VehicleService
from packages.asset_domain.events import (
    SUSTAINMENT_COMPONENT_REMOVED,
    SUSTAINMENT_FAILURE_RECORDED,
    SUSTAINMENT_MATERIAL_DEMANDED,
    SUSTAINMENT_MATERIAL_RESERVED,
    SUSTAINMENT_POST_MAINTENANCE_VALIDATED,
    SUSTAINMENT_TASK_COMPLETED,
    SUSTAINMENT_TASK_STARTED,
    SUSTAINMENT_WORK_ORDER_CANCELLED,
    SUSTAINMENT_WORK_ORDER_COMPLETED,
    SUSTAINMENT_WORK_ORDER_OPENED,
    SUSTAINMENT_WORK_ORDER_PRIORITY_RECALCULATED,
    SUSTAINMENT_WORK_ORDER_STATE_CHANGED,
    SUSTAINMENT_WORK_ORDER_TASK_ADDED,
    SUSTAINMENT_WORK_ORDER_TECHNICALLY_COMPLETE,
    sustainment_component_removed_payload,
    sustainment_failure_recorded_payload,
    sustainment_material_demanded_payload,
    sustainment_material_reserved_payload,
    sustainment_post_maintenance_validated_payload,
    sustainment_task_completed_payload,
    sustainment_task_started_payload,
    sustainment_work_order_cancelled_payload,
    sustainment_work_order_completed_payload,
    sustainment_work_order_opened_payload,
    sustainment_work_order_priority_recalculated_payload,
    sustainment_work_order_state_changed_payload,
    sustainment_work_order_task_added_payload,
    sustainment_work_order_technically_complete_payload,
)
from packages.asset_domain.inventory import DemandKind, DemandRef, ReservationState, StockPurpose
from packages.asset_domain.work_order import (
    ContractContext,
    FailureRecord,
    MaterialDemand,
    PostMaintenanceValidation,
    PriorityScore,
    RemovedComponentDisposition,
    ValidationResult,
    WorkOrder,
    WorkOrderState,
    WorkTask,
    all_material_fully_reserved,
    require_reservations_do_not_exceed_demand,
)
from packages.shared_kernel import TypedId


class WorkOrderNaoEncontrada(KeyError):
    """`work_order_id` não corresponde a nenhuma `WorkOrder` desta Organization."""


class SLIContractNaoEncontradoParaWorkOrder(KeyError):
    """`contract_ref` de `OpenWorkOrder` não corresponde a nenhum `SLIContract`."""


class WorkOrderRepositoryPort(Protocol):
    def save(self, work_order: WorkOrder) -> None: ...

    def update(self, work_order: WorkOrder) -> None: ...

    def get_by_id(self, work_order_id: TypedId) -> WorkOrder | None: ...


@dataclass(frozen=True, slots=True)
class WorkOrderService:
    repository: WorkOrderRepositoryPort
    sli_contract_repository: SLIContractRepositoryPort
    vehicle_service: VehicleService
    inventory_service: InventoryService
    recorder: AssetEventRecorder

    def _require(self, work_order_id: TypedId) -> WorkOrder:
        work_order = self.repository.get_by_id(work_order_id)
        if work_order is None:
            raise WorkOrderNaoEncontrada(f"WorkOrder '{work_order_id.value}' não encontrada.")
        return work_order

    def _reserved_qty_by_part(self, work_order: WorkOrder) -> dict[TypedId, Decimal]:
        """I-WO-2: soma de `StockReservation.qty` ativas vinculadas a esta WO,
        por peça — reconstruída a partir de `material_reservations` porque o
        próprio `WorkOrder` não guarda essa relação."""
        totals: dict[TypedId, Decimal] = {}
        for reservation_id in work_order.material_reservations:
            reservation = self.inventory_service.get_reservation(reservation_id)
            if reservation is None or reservation.state is ReservationState.RELEASED:
                continue
            position = self.inventory_service.get_stock_position(reservation.stock_position_ref)
            if position is None:
                continue
            totals[position.part_ref] = totals.get(position.part_ref, Decimal(0)) + reservation.qty
        return totals

    def _record_state_change(
        self,
        context: AssetOperationContext,
        work_order: WorkOrder,
        *,
        from_state: WorkOrderState,
        reason: str | None,
        occurred_at: datetime,
    ) -> None:
        self.recorder.record(
            context=context,
            aggregate_id=work_order.work_order_id,
            event_type=SUSTAINMENT_WORK_ORDER_STATE_CHANGED,
            payload=sustainment_work_order_state_changed_payload(
                work_order_id=work_order.work_order_id,
                from_state=from_state.value,
                to_state=work_order.state.value,
                reason=reason,
            ),
            occurred_at=occurred_at,
        )

    # -- T1: abertura -----------------------------------------------------

    def open_work_order(
        self,
        context: AssetOperationContext,
        *,
        vehicle_ref: TypedId,
        site_ref: TypedId,
        contract_ref: TypedId,
        failure: FailureRecord,
        at_instant: datetime,
        occurred_at: datetime,
    ) -> WorkOrder:
        contract = self.sli_contract_repository.get_by_id(contract_ref)
        if contract is None:
            raise SLIContractNaoEncontradoParaWorkOrder(
                f"SLIContract '{contract_ref.value}' não encontrado."
            )
        version = contract.resolve_version_at(at_instant)
        if version is None:
            raise ValueError(
                f"Nenhuma ContractVersion vigente em {at_instant.isoformat()} (I-SLI-1)."
            )
        work_order = WorkOrder(
            work_order_id=TypedId.new("work_order"),
            organization_id=context.organization_id,
            vehicle_ref=vehicle_ref,
            site_ref=site_ref,
            contract_context=ContractContext(
                contract_ref=contract_ref,
                contract_version_no=version.version_no,
                resolved_at=at_instant,
            ),
            failure=failure,
        )
        self.repository.save(work_order)
        self.recorder.record(
            context=context,
            aggregate_id=work_order.work_order_id,
            event_type=SUSTAINMENT_WORK_ORDER_OPENED,
            payload=sustainment_work_order_opened_payload(
                work_order_id=work_order.work_order_id,
                vehicle_ref=vehicle_ref,
                site_ref=site_ref,
                failure_mode=failure.mode,
                contract_ref=contract_ref,
                contract_version_no=version.version_no,
            ),
            occurred_at=occurred_at,
        )
        self.recorder.record(
            context=context,
            aggregate_id=work_order.work_order_id,
            event_type=SUSTAINMENT_FAILURE_RECORDED,
            payload=sustainment_failure_recorded_payload(
                work_order_id=work_order.work_order_id,
                vehicle_ref=vehicle_ref,
                mode=failure.mode,
                affected_position=failure.affected_position,
                observed_at=failure.reported_at,
            ),
            occurred_at=occurred_at,
        )
        return work_order

    # -- Tarefas e demanda (não mudam o estado da WO) ----------------------

    def add_task(
        self,
        context: AssetOperationContext,
        work_order_id: TypedId,
        *,
        description: str,
        mandatory: bool,
        occurred_at: datetime,
    ) -> WorkOrder:
        work_order = self._require(work_order_id)
        task = WorkTask(
            task_id=TypedId.new("work_task"), description=description, mandatory=mandatory
        )
        updated = work_order.add_task(task)
        self.repository.update(updated)
        self.recorder.record(
            context=context,
            aggregate_id=work_order_id,
            event_type=SUSTAINMENT_WORK_ORDER_TASK_ADDED,
            payload=sustainment_work_order_task_added_payload(
                work_order_id=work_order_id, task_id=task.task_id, mandatory=mandatory
            ),
            occurred_at=occurred_at,
        )
        return updated

    def demand_material(
        self,
        context: AssetOperationContext,
        work_order_id: TypedId,
        *,
        part_ref: TypedId,
        qty: Decimal,
        task_id: TypedId,
        occurred_at: datetime,
    ) -> WorkOrder:
        work_order = self._require(work_order_id)
        demand = MaterialDemand(part_ref=part_ref, qty=qty, task_id=task_id)
        updated = work_order.demand_material(demand)
        self.repository.update(updated)
        self.recorder.record(
            context=context,
            aggregate_id=work_order_id,
            event_type=SUSTAINMENT_MATERIAL_DEMANDED,
            payload=sustainment_material_demanded_payload(
                work_order_id=work_order_id, task_id=task_id, part_ref=part_ref, qty=qty
            ),
            occurred_at=occurred_at,
        )
        return updated

    # -- T2-T12/T14: transições genéricas ----------------------------------

    def mark_planned(
        self, context: AssetOperationContext, work_order_id: TypedId, *, occurred_at: datetime
    ) -> WorkOrder:
        work_order = self._require(work_order_id)
        from_state = work_order.state
        updated = work_order.mark_planned()
        self.repository.update(updated)
        self._record_state_change(
            context, updated, from_state=from_state, reason=None, occurred_at=occurred_at
        )
        return updated

    def enter_waiting_material(
        self, context: AssetOperationContext, work_order_id: TypedId, *, occurred_at: datetime
    ) -> WorkOrder:
        work_order = self._require(work_order_id)
        from_state = work_order.state
        updated = work_order.enter_waiting_material()
        self.repository.update(updated)
        self._record_state_change(
            context, updated, from_state=from_state, reason=None, occurred_at=occurred_at
        )
        return updated

    def exit_waiting_material(
        self, context: AssetOperationContext, work_order_id: TypedId, *, occurred_at: datetime
    ) -> WorkOrder:
        work_order = self._require(work_order_id)
        from_state = work_order.state
        updated = work_order.exit_waiting_material()
        self.repository.update(updated)
        self._record_state_change(
            context, updated, from_state=from_state, reason=None, occurred_at=occurred_at
        )
        return updated

    def mark_ready(
        self, context: AssetOperationContext, work_order_id: TypedId, *, occurred_at: datetime
    ) -> WorkOrder:
        work_order = self._require(work_order_id)
        from_state = work_order.state
        fully_reserved = all_material_fully_reserved(
            work_order, self._reserved_qty_by_part(work_order)
        )
        updated = work_order.mark_ready(material_fully_reserved=fully_reserved)
        self.repository.update(updated)
        self._record_state_change(
            context, updated, from_state=from_state, reason=None, occurred_at=occurred_at
        )
        return updated

    def require_authorization(
        self,
        context: AssetOperationContext,
        work_order_id: TypedId,
        *,
        reason: str,
        occurred_at: datetime,
    ) -> WorkOrder:
        work_order = self._require(work_order_id)
        from_state = work_order.state
        updated = work_order.require_authorization(reason=reason)
        self.repository.update(updated)
        self._record_state_change(
            context, updated, from_state=from_state, reason=reason, occurred_at=occurred_at
        )
        return updated

    def resolve_authorization(
        self,
        context: AssetOperationContext,
        work_order_id: TypedId,
        *,
        reason: str,
        decision_ref: TypedId,
        occurred_at: datetime,
    ) -> WorkOrder:
        work_order = self._require(work_order_id)
        from_state = work_order.state
        updated = work_order.resolve_authorization(reason=reason, decision_ref=decision_ref)
        self.repository.update(updated)
        self._record_state_change(
            context, updated, from_state=from_state, reason=reason, occurred_at=occurred_at
        )
        return updated

    def schedule(
        self,
        context: AssetOperationContext,
        work_order_id: TypedId,
        *,
        technician_and_workshop_allocated: bool,
        occurred_at: datetime,
    ) -> WorkOrder:
        work_order = self._require(work_order_id)
        from_state = work_order.state
        updated = work_order.schedule(
            technician_and_workshop_allocated=technician_and_workshop_allocated
        )
        self.repository.update(updated)
        self._record_state_change(
            context, updated, from_state=from_state, reason=None, occurred_at=occurred_at
        )
        return updated

    def mark_waiting_technician(
        self, context: AssetOperationContext, work_order_id: TypedId, *, occurred_at: datetime
    ) -> WorkOrder:
        work_order = self._require(work_order_id)
        from_state = work_order.state
        updated = work_order.mark_waiting_technician()
        self.repository.update(updated)
        self._record_state_change(
            context, updated, from_state=from_state, reason=None, occurred_at=occurred_at
        )
        return updated

    def start_progress(
        self,
        context: AssetOperationContext,
        work_order_id: TypedId,
        *,
        vehicle_in_maintenance: bool,
        occurred_at: datetime,
    ) -> WorkOrder:
        work_order = self._require(work_order_id)
        from_state = work_order.state
        updated = work_order.start_progress(vehicle_in_maintenance=vehicle_in_maintenance)
        self.repository.update(updated)
        self._record_state_change(
            context, updated, from_state=from_state, reason=None, occurred_at=occurred_at
        )
        return updated

    def interrupt(
        self,
        context: AssetOperationContext,
        work_order_id: TypedId,
        *,
        reason: str,
        occurred_at: datetime,
    ) -> WorkOrder:
        work_order = self._require(work_order_id)
        from_state = work_order.state
        updated = work_order.interrupt(reason=reason)
        self.repository.update(updated)
        self._record_state_change(
            context, updated, from_state=from_state, reason=reason, occurred_at=occurred_at
        )
        return updated

    def resume(
        self, context: AssetOperationContext, work_order_id: TypedId, *, occurred_at: datetime
    ) -> WorkOrder:
        work_order = self._require(work_order_id)
        from_state = work_order.state
        updated = work_order.resume()
        self.repository.update(updated)
        self._record_state_change(
            context, updated, from_state=from_state, reason=None, occurred_at=occurred_at
        )
        return updated

    def send_to_validation(
        self, context: AssetOperationContext, work_order_id: TypedId, *, occurred_at: datetime
    ) -> WorkOrder:
        work_order = self._require(work_order_id)
        from_state = work_order.state
        updated = work_order.send_to_validation()
        self.repository.update(updated)
        self._record_state_change(
            context, updated, from_state=from_state, reason=None, occurred_at=occurred_at
        )
        return updated

    # -- Execução de tarefas / remoção de componente -----------------------

    def start_task(
        self,
        context: AssetOperationContext,
        work_order_id: TypedId,
        *,
        task_id: TypedId,
        occurred_at: datetime,
    ) -> WorkOrder:
        work_order = self._require(work_order_id)
        updated = work_order.start_task(task_id)
        self.repository.update(updated)
        self.recorder.record(
            context=context,
            aggregate_id=work_order_id,
            event_type=SUSTAINMENT_TASK_STARTED,
            payload=sustainment_task_started_payload(work_order_id=work_order_id, task_id=task_id),
            occurred_at=occurred_at,
        )
        return updated

    def complete_task(
        self,
        context: AssetOperationContext,
        work_order_id: TypedId,
        *,
        task_id: TypedId,
        labor_entry: str | None = None,
        occurred_at: datetime,
    ) -> WorkOrder:
        work_order = self._require(work_order_id)
        updated = work_order.complete_task(task_id, labor_entry=labor_entry)
        self.repository.update(updated)
        self.recorder.record(
            context=context,
            aggregate_id=work_order_id,
            event_type=SUSTAINMENT_TASK_COMPLETED,
            payload=sustainment_task_completed_payload(
                work_order_id=work_order_id, task_id=task_id, labor_entry=labor_entry
            ),
            occurred_at=occurred_at,
        )
        return updated

    def record_removed_component(
        self,
        context: AssetOperationContext,
        work_order_id: TypedId,
        *,
        part_ref: TypedId,
        disposition: str,
        serial: str | None = None,
        occurred_at: datetime,
    ) -> WorkOrder:
        work_order = self._require(work_order_id)
        component = RemovedComponentDisposition(
            part_ref=part_ref, disposition=disposition, serial=serial
        )
        updated = work_order.record_removed_component(component)
        self.repository.update(updated)
        self.recorder.record(
            context=context,
            aggregate_id=work_order_id,
            event_type=SUSTAINMENT_COMPONENT_REMOVED,
            payload=sustainment_component_removed_payload(
                work_order_id=work_order_id,
                part_ref=part_ref,
                serial=serial,
                disposition=disposition,
            ),
            occurred_at=occurred_at,
        )
        return updated

    def recalculate_priority(
        self,
        context: AssetOperationContext,
        work_order_id: TypedId,
        *,
        priority: PriorityScore,
        occurred_at: datetime,
    ) -> WorkOrder:
        work_order = self._require(work_order_id)
        updated = work_order.recalculate_priority(priority)
        self.repository.update(updated)
        self.recorder.record(
            context=context,
            aggregate_id=work_order_id,
            event_type=SUSTAINMENT_WORK_ORDER_PRIORITY_RECALCULATED,
            payload=sustainment_work_order_priority_recalculated_payload(
                work_order_id=work_order_id,
                score=priority.score,
                breakdown="; ".join(f"{k}={v}" for k, v in priority.breakdown.items()),
                evaluation_ref=priority.evaluation_ref,
            ),
            occurred_at=occurred_at,
        )
        return updated

    # -- T13/T15/T16/T17: eventos próprios ---------------------------------

    def complete_technically(
        self,
        context: AssetOperationContext,
        work_order_id: TypedId,
        *,
        diagnosis: str,
        root_cause: str,
        resolution: str,
        occurred_at: datetime,
    ) -> WorkOrder:
        work_order = self._require(work_order_id)
        updated = work_order.complete_technically(
            diagnosis=diagnosis, root_cause=root_cause, resolution=resolution
        )
        self.repository.update(updated)
        self.recorder.record(
            context=context,
            aggregate_id=work_order_id,
            event_type=SUSTAINMENT_WORK_ORDER_TECHNICALLY_COMPLETE,
            payload=sustainment_work_order_technically_complete_payload(
                work_order_id=work_order_id,
                diagnosis=diagnosis,
                root_cause=root_cause,
                resolution=resolution,
            ),
            occurred_at=occurred_at,
        )
        return updated

    def perform_post_maintenance_validation(
        self,
        context: AssetOperationContext,
        work_order_id: TypedId,
        *,
        validator_ref: TypedId,
        reason: str,
        notes: str | None = None,
        occurred_at: datetime,
    ) -> WorkOrder:
        """Só cobre o caminho `FAIL` (`fail_validation`, T15) — o domínio não
        tem um terceiro método "registrar validação sem transicionar"; uma
        validação `PASS` é `close_work_order`, que registra e fecha no mesmo
        ato (ver docstring do módulo)."""
        work_order = self._require(work_order_id)
        validation = PostMaintenanceValidation(
            validated_at=occurred_at,
            validator_ref=validator_ref,
            result=ValidationResult.FAIL,
            notes=notes,
        )
        updated = work_order.fail_validation(reason=reason, validation=validation)
        self.repository.update(updated)
        validation_ref = TypedId.new("post_maintenance_validation")
        self.recorder.record(
            context=context,
            aggregate_id=work_order_id,
            event_type=SUSTAINMENT_POST_MAINTENANCE_VALIDATED,
            payload=sustainment_post_maintenance_validated_payload(
                work_order_id=work_order_id,
                validation_ref=validation_ref,
                result=ValidationResult.FAIL.value,
            ),
            occurred_at=occurred_at,
        )
        self._record_state_change(
            context,
            updated,
            from_state=WorkOrderState.VALIDATION,
            reason=reason,
            occurred_at=occurred_at,
        )
        return updated

    def close_work_order(
        self,
        context: AssetOperationContext,
        work_order_id: TypedId,
        *,
        validator_ref: TypedId,
        notes: str | None = None,
        occurred_at: datetime,
    ) -> WorkOrder:
        """T16: registra a validação `PASS` e fecha no mesmo ato, e coordena
        `Vehicle.return_to_service` (I-VEH-3) — fronteira transacional de
        `CloseWorkOrder` inclui os dois agregados (`09_COMMAND_MODEL.md`)."""
        work_order = self._require(work_order_id)
        validation = PostMaintenanceValidation(
            validated_at=occurred_at,
            validator_ref=validator_ref,
            result=ValidationResult.PASS_,
            notes=notes,
        )
        updated = work_order.close(validation=validation)
        self.repository.update(updated)
        validation_ref = TypedId.new("post_maintenance_validation")
        self.recorder.record(
            context=context,
            aggregate_id=work_order_id,
            event_type=SUSTAINMENT_POST_MAINTENANCE_VALIDATED,
            payload=sustainment_post_maintenance_validated_payload(
                work_order_id=work_order_id,
                validation_ref=validation_ref,
                result=ValidationResult.PASS_.value,
            ),
            occurred_at=occurred_at,
        )
        self.recorder.record(
            context=context,
            aggregate_id=work_order_id,
            event_type=SUSTAINMENT_WORK_ORDER_COMPLETED,
            payload=sustainment_work_order_completed_payload(
                work_order_id=work_order_id, closed_at=occurred_at
            ),
            occurred_at=occurred_at,
        )
        self.vehicle_service.return_to_service(
            context,
            work_order.vehicle_ref,
            work_order_ref=work_order_id,
            validation_ref=validation_ref,
            occurred_at=occurred_at,
        )
        return updated

    def cancel_work_order(
        self,
        context: AssetOperationContext,
        work_order_id: TypedId,
        *,
        reason: str,
        occurred_at: datetime,
    ) -> WorkOrder:
        """T17: libera toda reserva de material vinculada
        (`09_COMMAND_MODEL.md`: "+ libera reservas")."""
        work_order = self._require(work_order_id)
        from_state = work_order.state
        updated = work_order.cancel(reason=reason)
        self.repository.update(updated)
        for reservation_id in work_order.material_reservations:
            reservation = self.inventory_service.get_reservation(reservation_id)
            if reservation is not None and reservation.state is not ReservationState.RELEASED:
                self.inventory_service.release_reservation(
                    context, reservation_id, reason=reason, occurred_at=occurred_at
                )
        self.recorder.record(
            context=context,
            aggregate_id=work_order_id,
            event_type=SUSTAINMENT_WORK_ORDER_CANCELLED,
            payload=sustainment_work_order_cancelled_payload(
                work_order_id=work_order_id, from_state=from_state.value, reason=reason
            ),
            occurred_at=occurred_at,
        )
        return updated

    # -- Material (coordenado com Inventory) -------------------------------

    def reserve_material_for_work_order(
        self,
        context: AssetOperationContext,
        work_order_id: TypedId,
        *,
        stock_position_id: TypedId,
        part_ref: TypedId,
        qty: Decimal,
        priority: int,
        occurred_at: datetime,
    ) -> WorkOrder:
        work_order = self._require(work_order_id)
        prospective = dict(self._reserved_qty_by_part(work_order))
        prospective[part_ref] = prospective.get(part_ref, Decimal(0)) + qty
        require_reservations_do_not_exceed_demand(work_order, prospective)

        _, reservation = self.inventory_service.reserve_stock(
            context,
            stock_position_id,
            demand=DemandRef(kind=DemandKind.WORK_ORDER, ref=work_order_id),
            qty=qty,
            purpose=StockPurpose.SERVICE_SLI,
            priority=priority,
            occurred_at=occurred_at,
        )
        updated = replace(
            work_order,
            material_reservations=work_order.material_reservations + (reservation.reservation_id,),
            version=work_order.version + 1,
        )
        self.repository.update(updated)
        self.recorder.record(
            context=context,
            aggregate_id=work_order_id,
            event_type=SUSTAINMENT_MATERIAL_RESERVED,
            payload=sustainment_material_reserved_payload(
                work_order_id=work_order_id,
                reservation_ref=reservation.reservation_id,
                part_ref=part_ref,
                qty=qty,
            ),
            occurred_at=occurred_at,
        )
        return updated

    def get_work_order(self, work_order_id: TypedId) -> WorkOrder | None:
        return self.repository.get_by_id(work_order_id)
