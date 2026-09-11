"""Teste de integração PostgreSQL com RLS para `WorkOrder` (A3, fecha A3)."""

import os
from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import Connection, create_engine, text

from packages.asset_domain.customer_site import CustomerSite, CustomerSiteKind
from packages.asset_domain.part import Part, PartIdentity, PartRevision
from packages.asset_domain.sustainment_contract import (
    ContractVersion,
    KnownValidInterval,
    SLIContract,
)
from packages.asset_domain.vehicle import AssetOwnership, Vehicle, VehicleIdentifiers
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
)
from packages.asset_infrastructure.persistence.customer_site_repository import (
    TransactionalCustomerSiteRepository,
)
from packages.asset_infrastructure.persistence.part_repository import TransactionalPartRepository
from packages.asset_infrastructure.persistence.sustainment_contract_repository import (
    TransactionalSLIContractRepository,
)
from packages.asset_infrastructure.persistence.vehicle_repository import (
    TransactionalVehicleRepository,
)
from packages.asset_infrastructure.persistence.work_order_repository import (
    TransactionalWorkOrderRepository,
)
from packages.shared_kernel import OrganizationId, TypedId


@pytest.fixture
def db_connection() -> Iterator[Connection]:
    db_url = os.getenv(
        "TITAN_DATABASE_URL",
        "postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan",
    )
    engine = create_engine(db_url, pool_pre_ping=True)
    with engine.connect() as conn:
        with conn.begin():
            yield conn


def _setup_dependencies(
    db_connection: Connection, org: OrganizationId
) -> tuple[TypedId, TypedId, TypedId, TypedId]:
    site = CustomerSite(
        site_id=TypedId.new("customer_site"),
        organization_id=org,
        customer_ref=TypedId.new("customer"),
        code="OM-900",
        display_name="Oficina WO",
        kind=CustomerSiteKind.OM,
    )
    TransactionalCustomerSiteRepository(connection=db_connection).save(site)

    vehicle = Vehicle(
        vehicle_id=TypedId.new("vehicle"),
        organization_id=org,
        model_ref=TypedId.new("vehicle_model"),
        identifiers=VehicleIdentifiers(serial_number="SN-900"),
        ownership=AssetOwnership.COMPANY,
        site_ref=site.site_id,
    )
    TransactionalVehicleRepository(connection=db_connection).save(vehicle)

    contract = SLIContract(
        contract_id=TypedId.new("sli_contract"),
        organization_id=org,
        customer_ref=TypedId.new("customer"),
        versions=(
            ContractVersion(
                version_no=1,
                effective=KnownValidInterval(
                    valid_from=datetime(2026, 1, 1, tzinfo=UTC),
                    known_at=datetime(2026, 1, 1, tzinfo=UTC),
                ),
            ),
        ),
    )
    TransactionalSLIContractRepository(connection=db_connection).save(contract)

    part_revision = PartRevision(revision_id=TypedId.new("part_revision"), revision_code="A")
    part = Part(
        part_id=TypedId.new("part"),
        organization_id=org,
        identity=PartIdentity(part_number="PN-900", description="Retentor", manufacturer="Acme"),
        revisions=(part_revision,),
    )
    TransactionalPartRepository(connection=db_connection).save(part)

    return vehicle.vehicle_id, site.site_id, contract.contract_id, part.part_id


def test_work_order_full_lifecycle_and_rls(db_connection: Connection) -> None:
    org_1 = OrganizationId(uuid4())
    org_2 = OrganizationId(uuid4())
    db_connection.execute(
        text(
            "INSERT INTO core_identity.organizations "
            "(organization_id, record_owner_organization_id) VALUES (:org1, :org1), (:org2, :org2)"
        ),
        {"org1": org_1.value, "org2": org_2.value},
    )
    db_connection.execute(
        text("SELECT set_config('titan.organization_id', :org_id, true)"),
        {"org_id": str(org_1.value)},
    )
    vehicle_id, site_id, contract_id, part_ref = _setup_dependencies(db_connection, org_1)

    repo = TransactionalWorkOrderRepository(connection=db_connection)
    task = WorkTask(task_id=TypedId.new("work_task"), description="Trocar retentor", mandatory=True)
    work_order = WorkOrder(
        work_order_id=TypedId.new("work_order"),
        organization_id=org_1,
        vehicle_ref=vehicle_id,
        site_ref=site_id,
        contract_context=ContractContext(
            contract_ref=contract_id,
            contract_version_no=1,
            resolved_at=datetime(2026, 2, 1, tzinfo=UTC),
        ),
        failure=FailureRecord(
            mode="Vazamento hidráulico", reported_at=datetime(2026, 2, 1, tzinfo=UTC)
        ),
        tasks=(task,),
    )
    work_order = work_order.demand_material(
        MaterialDemand(part_ref=part_ref, qty=Decimal(2), task_id=task.task_id)
    )
    priority = PriorityScore(score=70, breakdown={"criticidade": 50, "sla": 20})
    work_order = work_order.recalculate_priority(priority)
    repo.save(work_order)

    saved = repo.get_by_id(work_order.work_order_id)
    assert saved is not None
    assert saved.state is WorkOrderState.DRAFT
    assert len(saved.tasks) == 1
    assert len(saved.material_demands) == 1
    assert saved.priority == priority

    planned = saved.mark_planned()
    repo.update(planned)
    ready = repo.get_by_id(work_order.work_order_id)
    assert ready is not None
    assert ready.state is WorkOrderState.PLANNED

    ready = ready.mark_ready(material_fully_reserved=True)
    scheduled = ready.schedule(technician_and_workshop_allocated=True)
    in_progress = scheduled.start_progress(vehicle_in_maintenance=True)
    repo.update(in_progress)

    reloaded = repo.get_by_id(work_order.work_order_id)
    assert reloaded is not None
    assert reloaded.state is WorkOrderState.IN_PROGRESS

    started = reloaded.start_task(task.task_id)
    completed_task = started.complete_task(task.task_id, labor_entry="2h - técnico A")
    completed_task = completed_task.record_removed_component(
        RemovedComponentDisposition(part_ref=part_ref, disposition="SCRAP")
    )
    repo.update(completed_task)

    reloaded_2 = repo.get_by_id(work_order.work_order_id)
    assert reloaded_2 is not None
    assert reloaded_2.tasks[0].labor_entries == ("2h - técnico A",)
    assert len(reloaded_2.removed_components) == 1

    technically_complete = reloaded_2.complete_technically(
        diagnosis="Retentor rompido", root_cause="Desgaste", resolution="Substituído"
    )
    in_validation = technically_complete.send_to_validation()
    repo.update(in_validation)

    reloaded_3 = repo.get_by_id(work_order.work_order_id)
    assert reloaded_3 is not None
    assert reloaded_3.state is WorkOrderState.VALIDATION
    assert reloaded_3.diagnosis == "Retentor rompido"

    validation = PostMaintenanceValidation(
        validated_at=datetime(2026, 2, 5, tzinfo=UTC),
        validator_ref=TypedId.new("user"),
        result=ValidationResult.PASS_,
    )
    closed = reloaded_3.close(validation=validation)
    repo.update(closed)

    reloaded_final = repo.get_by_id(work_order.work_order_id)
    assert reloaded_final is not None
    assert reloaded_final.state is WorkOrderState.COMPLETED
    assert reloaded_final.validation is not None
    assert reloaded_final.validation.result is ValidationResult.PASS_
    assert reloaded_final.validation.validator_ref == validation.validator_ref
    # Tarefa não foi duplicada por causa do upsert em update().
    assert len(reloaded_final.tasks) == 1

    role_name = f"titan_rls_wo_{uuid4().hex[:12]}"
    quoted_role = f'"{role_name}"'
    db_connection.execute(
        text(
            f"CREATE ROLE {quoted_role} "
            "NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS"
        )
    )
    db_connection.execute(text(f"GRANT USAGE ON SCHEMA core_audit TO {quoted_role}"))
    for table in (
        "work_orders",
        "work_order_tasks",
        "work_order_material_demands",
        "work_order_removed_components",
    ):
        db_connection.execute(text(f"GRANT ALL ON core_audit.{table} TO {quoted_role}"))
    db_connection.execute(text(f"SET LOCAL ROLE {quoted_role}"))
    db_connection.execute(
        text("SELECT set_config('titan.organization_id', :org_id, true)"),
        {"org_id": str(org_2.value)},
    )
    repo_2 = TransactionalWorkOrderRepository(connection=db_connection)
    assert repo_2.get_by_id(work_order.work_order_id) is None
    db_connection.execute(text("RESET ROLE"))
    db_connection.execute(text(f"DROP OWNED BY {quoted_role}"))
    db_connection.execute(text(f"DROP ROLE {quoted_role}"))
