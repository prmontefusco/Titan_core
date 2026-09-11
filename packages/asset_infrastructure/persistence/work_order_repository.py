"""Persistência do agregado `WorkOrder` — Titan Asset (A3, módulo `sustainment`).

O agregado mais complexo do slice (`docs/asset/05_DOMAIN_MODEL.md` §2.4).
`contract_context`/`failure`/`priority`/`validation` são VOs únicos por
instância, embutidos como colunas (mesmo padrão de `Applicability.target`).
`workshop_ref`, `priority.evaluation_ref` e `validation.validator_ref` são
`TypedId` sem `entity_type` fixado pelo domínio — cada um ganha coluna
`*_entity_type` própria (mesmo caso de `Applicability.asserted_by`).
`material_reservations`/`priority.breakdown` viram `ARRAY`/`JSONB`.

`tasks` tem identidade estável (`task_id`) e `material_demands` referencia
`task_id` por FK — mesma armadilha de `part_revisions`/`interchangeability_group_members`
(`part_repository.py`): `update()` faz **upsert** de `tasks`, nunca
delete+reinsert. `material_demands`/`removed_components` não têm identidade
própria nem nada aponta FK para eles — `update()` segue delete+reinsert
normalmente.
"""

from dataclasses import dataclass
from datetime import UTC
from typing import Any

from sqlalchemy import (
    Boolean,
    Column,
    Connection,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
    Table,
    delete,
    select,
)
from sqlalchemy import (
    insert as sa_insert,
)
from sqlalchemy import (
    update as sa_update,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Row

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
    WorkTaskState,
)
from packages.asset_infrastructure.persistence.metadata import asset_metadata
from packages.core_infrastructure.persistence.events import CORE_AUDIT_SCHEMA
from packages.shared_kernel import OrganizationId, TypedId

work_orders_table = Table(
    "work_orders",
    asset_metadata,
    Column("work_order_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("vehicle_id", PG_UUID(as_uuid=True), nullable=False),
    Column("site_id", PG_UUID(as_uuid=True), nullable=False),
    Column("contract_ref_id", PG_UUID(as_uuid=True), nullable=False),
    Column("contract_version_no", Integer, nullable=False),
    Column("contract_resolved_at", DateTime(timezone=True), nullable=False),
    Column("failure_mode", String(200), nullable=False),
    Column("failure_reported_at", DateTime(timezone=True), nullable=False),
    Column("failure_affected_position", String(100), nullable=True),
    Column("workshop_id", PG_UUID(as_uuid=True), nullable=True),
    Column("workshop_entity_type", String(100), nullable=True),
    Column("material_reservations", ARRAY(PG_UUID(as_uuid=True)), nullable=False, default=list),
    Column("state", String(30), nullable=False),
    Column("pre_wait_authorization_state", String(30), nullable=True),
    Column("priority_score", Integer, nullable=True),
    Column("priority_breakdown", JSONB, nullable=True),
    Column("priority_evaluation_id", PG_UUID(as_uuid=True), nullable=True),
    Column("priority_evaluation_entity_type", String(100), nullable=True),
    Column("diagnosis", String(2000), nullable=True),
    Column("root_cause", String(2000), nullable=True),
    Column("resolution", String(2000), nullable=True),
    Column("validation_validated_at", DateTime(timezone=True), nullable=True),
    Column("validation_validator_id", PG_UUID(as_uuid=True), nullable=True),
    Column("validation_validator_entity_type", String(100), nullable=True),
    Column("validation_result", String(20), nullable=True),
    Column("validation_notes", String(2000), nullable=True),
    Column("version", Integer, nullable=False, default=1),
    Column("created_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_work_orders_organization",
    ),
    ForeignKeyConstraint(
        ["vehicle_id"], ["core_audit.vehicles.vehicle_id"], name="fk_work_orders_vehicle"
    ),
    ForeignKeyConstraint(
        ["site_id"], ["core_audit.customer_sites.site_id"], name="fk_work_orders_site"
    ),
    ForeignKeyConstraint(
        ["contract_ref_id"],
        ["core_audit.sli_contracts.contract_id"],
        name="fk_work_orders_contract",
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=asset",
)

work_order_tasks_table = Table(
    "work_order_tasks",
    asset_metadata,
    Column("task_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("work_order_id", PG_UUID(as_uuid=True), nullable=False),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("description", String(500), nullable=False),
    Column("mandatory", Boolean, nullable=False),
    Column("state", String(20), nullable=False),
    Column("labor_entries", ARRAY(String), nullable=False, default=list),
    ForeignKeyConstraint(
        ["work_order_id"],
        ["core_audit.work_orders.work_order_id"],
        name="fk_work_order_tasks_work_order",
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=asset",
)

work_order_material_demands_table = Table(
    "work_order_material_demands",
    asset_metadata,
    Column("work_order_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("ordinal", Integer, primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("part_id", PG_UUID(as_uuid=True), nullable=False),
    Column("qty", Numeric, nullable=False),
    Column("task_id", PG_UUID(as_uuid=True), nullable=False),
    ForeignKeyConstraint(
        ["work_order_id"],
        ["core_audit.work_orders.work_order_id"],
        name="fk_work_order_material_demands_work_order",
    ),
    ForeignKeyConstraint(
        ["part_id"], ["core_audit.parts.part_id"], name="fk_work_order_material_demands_part"
    ),
    ForeignKeyConstraint(
        ["task_id"],
        ["core_audit.work_order_tasks.task_id"],
        name="fk_work_order_material_demands_task",
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=asset",
)

work_order_removed_components_table = Table(
    "work_order_removed_components",
    asset_metadata,
    Column("work_order_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("ordinal", Integer, primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("part_id", PG_UUID(as_uuid=True), nullable=False),
    Column("disposition", String(200), nullable=False),
    Column("serial", String(100), nullable=True),
    ForeignKeyConstraint(
        ["work_order_id"],
        ["core_audit.work_orders.work_order_id"],
        name="fk_work_order_removed_components_work_order",
    ),
    ForeignKeyConstraint(
        ["part_id"], ["core_audit.parts.part_id"], name="fk_work_order_removed_components_part"
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=asset",
)


@dataclass(frozen=True, slots=True)
class TransactionalWorkOrderRepository:
    connection: Connection

    def __post_init__(self) -> None:
        if not isinstance(self.connection, Connection) or not self.connection.in_transaction():
            raise RuntimeError(
                "TransactionalWorkOrderRepository exige Connection com transação ativa."
            )

    def save(self, work_order: WorkOrder) -> None:
        self.connection.execute(sa_insert(work_orders_table).values(**self._values(work_order)))
        self._upsert_tasks(work_order)
        self._replace_material_demands(work_order)
        self._replace_removed_components(work_order)

    def update(self, work_order: WorkOrder) -> None:
        self.connection.execute(
            sa_update(work_orders_table)
            .where(work_orders_table.c.work_order_id == work_order.work_order_id.value)
            .values(**self._values(work_order, include_id=False))
        )
        self._upsert_tasks(work_order)
        self._replace_material_demands(work_order)
        self._replace_removed_components(work_order)

    def _values(self, work_order: WorkOrder, *, include_id: bool = True) -> dict[str, Any]:
        priority = work_order.priority
        validation = work_order.validation
        values: dict[str, Any] = {
            "record_owner_organization_id": work_order.organization_id.value,
            "vehicle_id": work_order.vehicle_ref.value,
            "site_id": work_order.site_ref.value,
            "contract_ref_id": work_order.contract_context.contract_ref.value,
            "contract_version_no": work_order.contract_context.contract_version_no,
            "contract_resolved_at": work_order.contract_context.resolved_at,
            "failure_mode": work_order.failure.mode,
            "failure_reported_at": work_order.failure.reported_at,
            "failure_affected_position": work_order.failure.affected_position,
            "workshop_id": work_order.workshop_ref.value if work_order.workshop_ref else None,
            "workshop_entity_type": (
                work_order.workshop_ref.entity_type if work_order.workshop_ref else None
            ),
            "material_reservations": [ref.value for ref in work_order.material_reservations],
            "state": work_order.state.value,
            "pre_wait_authorization_state": (
                work_order.pre_wait_authorization_state.value
                if work_order.pre_wait_authorization_state
                else None
            ),
            "priority_score": priority.score if priority else None,
            "priority_breakdown": dict(priority.breakdown) if priority else None,
            "priority_evaluation_id": (
                priority.evaluation_ref.value if priority and priority.evaluation_ref else None
            ),
            "priority_evaluation_entity_type": (
                priority.evaluation_ref.entity_type
                if priority and priority.evaluation_ref
                else None
            ),
            "diagnosis": work_order.diagnosis,
            "root_cause": work_order.root_cause,
            "resolution": work_order.resolution,
            "validation_validated_at": validation.validated_at if validation else None,
            "validation_validator_id": validation.validator_ref.value if validation else None,
            "validation_validator_entity_type": (
                validation.validator_ref.entity_type if validation else None
            ),
            "validation_result": validation.result.value if validation else None,
            "validation_notes": validation.notes if validation else None,
            "version": work_order.version,
            "created_at": work_order.created_at,
        }
        if include_id:
            values["work_order_id"] = work_order.work_order_id.value
        return values

    def _upsert_tasks(self, work_order: WorkOrder) -> None:
        for task in work_order.tasks:
            stmt = pg_insert(work_order_tasks_table).values(
                task_id=task.task_id.value,
                work_order_id=work_order.work_order_id.value,
                record_owner_organization_id=work_order.organization_id.value,
                description=task.description,
                mandatory=task.mandatory,
                state=task.state.value,
                labor_entries=list(task.labor_entries),
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=[work_order_tasks_table.c.task_id],
                set_={
                    "state": stmt.excluded.state,
                    "labor_entries": stmt.excluded.labor_entries,
                },
            )
            self.connection.execute(stmt)

    def _replace_material_demands(self, work_order: WorkOrder) -> None:
        self.connection.execute(
            delete(work_order_material_demands_table).where(
                work_order_material_demands_table.c.work_order_id == work_order.work_order_id.value
            )
        )
        for ordinal, demand in enumerate(work_order.material_demands):
            self.connection.execute(
                sa_insert(work_order_material_demands_table).values(
                    work_order_id=work_order.work_order_id.value,
                    ordinal=ordinal,
                    record_owner_organization_id=work_order.organization_id.value,
                    part_id=demand.part_ref.value,
                    qty=demand.qty,
                    task_id=demand.task_id.value,
                )
            )

    def _replace_removed_components(self, work_order: WorkOrder) -> None:
        self.connection.execute(
            delete(work_order_removed_components_table).where(
                work_order_removed_components_table.c.work_order_id
                == work_order.work_order_id.value
            )
        )
        for ordinal, disposition in enumerate(work_order.removed_components):
            self.connection.execute(
                sa_insert(work_order_removed_components_table).values(
                    work_order_id=work_order.work_order_id.value,
                    ordinal=ordinal,
                    record_owner_organization_id=work_order.organization_id.value,
                    part_id=disposition.part_ref.value,
                    disposition=disposition.disposition,
                    serial=disposition.serial,
                )
            )

    def get_by_id(self, work_order_id: TypedId) -> WorkOrder | None:
        row = self.connection.execute(
            select(work_orders_table).where(
                work_orders_table.c.work_order_id == work_order_id.value
            )
        ).fetchone()
        if row is None:
            return None
        return self._map(row)

    def _map(self, row: Row[Any]) -> WorkOrder:
        def _tz(value: Any) -> Any:
            if value is not None and value.tzinfo is None:
                return value.replace(tzinfo=UTC)
            return value

        task_rows = self.connection.execute(
            select(work_order_tasks_table).where(
                work_order_tasks_table.c.work_order_id == row.work_order_id
            )
        ).fetchall()
        tasks = tuple(
            WorkTask(
                task_id=TypedId(entity_type="work_task", value=task_row.task_id),
                description=task_row.description,
                mandatory=task_row.mandatory,
                state=WorkTaskState(task_row.state),
                labor_entries=tuple(task_row.labor_entries or ()),
            )
            for task_row in task_rows
        )
        demand_rows = self.connection.execute(
            select(work_order_material_demands_table)
            .where(work_order_material_demands_table.c.work_order_id == row.work_order_id)
            .order_by(work_order_material_demands_table.c.ordinal)
        ).fetchall()
        material_demands = tuple(
            MaterialDemand(
                part_ref=TypedId(entity_type="part", value=demand_row.part_id),
                qty=demand_row.qty,
                task_id=TypedId(entity_type="work_task", value=demand_row.task_id),
            )
            for demand_row in demand_rows
        )
        component_rows = self.connection.execute(
            select(work_order_removed_components_table)
            .where(work_order_removed_components_table.c.work_order_id == row.work_order_id)
            .order_by(work_order_removed_components_table.c.ordinal)
        ).fetchall()
        removed_components = tuple(
            RemovedComponentDisposition(
                part_ref=TypedId(entity_type="part", value=component_row.part_id),
                disposition=component_row.disposition,
                serial=component_row.serial,
            )
            for component_row in component_rows
        )
        priority = (
            PriorityScore(
                score=row.priority_score,
                breakdown=dict(row.priority_breakdown or {}),
                evaluation_ref=(
                    TypedId(
                        entity_type=row.priority_evaluation_entity_type,
                        value=row.priority_evaluation_id,
                    )
                    if row.priority_evaluation_id is not None
                    else None
                ),
            )
            if row.priority_score is not None
            else None
        )
        validation = (
            PostMaintenanceValidation(
                validated_at=_tz(row.validation_validated_at),
                validator_ref=TypedId(
                    entity_type=row.validation_validator_entity_type,
                    value=row.validation_validator_id,
                ),
                result=ValidationResult(row.validation_result),
                notes=row.validation_notes,
            )
            if row.validation_validated_at is not None
            else None
        )
        return WorkOrder(
            work_order_id=TypedId(entity_type="work_order", value=row.work_order_id),
            organization_id=OrganizationId(row.record_owner_organization_id),
            vehicle_ref=TypedId(entity_type="vehicle", value=row.vehicle_id),
            site_ref=TypedId(entity_type="customer_site", value=row.site_id),
            contract_context=ContractContext(
                contract_ref=TypedId(entity_type="sli_contract", value=row.contract_ref_id),
                contract_version_no=row.contract_version_no,
                resolved_at=_tz(row.contract_resolved_at),
            ),
            failure=FailureRecord(
                mode=row.failure_mode,
                reported_at=_tz(row.failure_reported_at),
                affected_position=row.failure_affected_position,
            ),
            workshop_ref=(
                TypedId(entity_type=row.workshop_entity_type, value=row.workshop_id)
                if row.workshop_id is not None
                else None
            ),
            tasks=tasks,
            material_demands=material_demands,
            material_reservations=tuple(
                TypedId(entity_type="stock_reservation", value=reservation_id)
                for reservation_id in (row.material_reservations or ())
            ),
            state=WorkOrderState(row.state),
            pre_wait_authorization_state=(
                WorkOrderState(row.pre_wait_authorization_state)
                if row.pre_wait_authorization_state
                else None
            ),
            priority=priority,
            diagnosis=row.diagnosis,
            root_cause=row.root_cause,
            resolution=row.resolution,
            removed_components=removed_components,
            validation=validation,
            version=row.version,
            created_at=_tz(row.created_at),
        )
