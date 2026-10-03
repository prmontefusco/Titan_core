"""Contrato HTTP de `OpenWorkOrder` — Titan Asset A5."""

import importlib
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import Protocol

import pytest
from fastapi.testclient import TestClient
from pytest import MonkeyPatch

import apps.api.main as main_module
from apps.api.asset import commands as asset_commands
from apps.api.authentication import require_authenticated_principal
from apps.api.livestock_dependencies import ORGANIZATION_HEADER, request_connection
from packages.asset_application.authorization import (
    WO_ADD_TASK,
    WO_DEMAND_MATERIAL,
    WO_OPEN,
    WO_TRANSITION,
)
from packages.asset_application.contract_context_query import (
    ContractContextAmbiguo,
    ContractContextForVehicle,
    ContractContextNaoEncontrado,
)
from packages.asset_domain.sustainment_contract import (
    SLA,
    ContractScope,
    ContractVersion,
    CoverageLine,
    KnownValidInterval,
    SLIContract,
)
from packages.asset_domain.vehicle import AssetOwnership, Vehicle, VehicleIdentifiers
from packages.asset_domain.work_order import (
    ContractContext,
    FailureRecord,
    MaterialDemand,
    WorkOrder,
    WorkOrderState,
    WorkTask,
)
from packages.core_application import IdempotencyExecution, OptimisticConcurrencyConflict
from packages.core_domain import AuthenticatedPrincipal, CanonicalPayload, OrganizationContext
from packages.core_domain.organization_context import PrincipalType
from packages.shared_kernel import OrganizationId, TypedId

VEHICLE_ID = "00000000-0000-0000-0000-000000000401"
SITE_ID = "00000000-0000-0000-0000-000000000101"
CONTRACT_ID = "00000000-0000-0000-0000-000000000501"
ROUTE = "/v1/asset/work-orders"
OCCURRED_AT = datetime(2026, 10, 3, 12, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _restore_default_app() -> Iterator[None]:
    yield
    main_module.app.dependency_overrides.clear()
    importlib.reload(main_module)


def _context(permissions: frozenset[str] = frozenset({WO_OPEN})) -> OrganizationContext:
    return OrganizationContext(
        organization_id=OrganizationId.new(),
        authenticated_principal=AuthenticatedPrincipal(
            issuer="https://issuer.example.test",
            subject="asset-open-wo-test-user",
            principal_type=PrincipalType.USER,
            authenticated_at=OCCURRED_AT,
            client_id="asset-open-wo-test",
            technical_scopes=frozenset({"openid"}),
        ),
        user_id=TypedId.new("user"),
        actor_id=TypedId.new("actor"),
        membership_id=TypedId.new("membership"),
        role_ids=(TypedId.new("role"),),
        permission_codes=permissions,
        validated_at=OCCURRED_AT,
    )


def _body(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "vehicle_id": VEHICLE_ID,
        "at_instant": "2026-10-03T12:00:00Z",
        "failure_mode": "Falha hidráulica",
        "failure_reported_at": "2026-10-03T12:00:00Z",
        "failure_affected_position": "braço",
    }
    body.update(overrides)
    return body


def _vehicle(vehicle_id: TypedId) -> Vehicle:
    return Vehicle(
        vehicle_id=vehicle_id,
        organization_id=OrganizationId.new(),
        model_ref=TypedId.new("vehicle_model"),
        identifiers=VehicleIdentifiers(serial_number="SN-OPEN-WO"),
        ownership=AssetOwnership.COMPANY,
        site_ref=TypedId.parse("customer_site", SITE_ID),
        created_at=OCCURRED_AT,
    )


def _contract() -> SLIContract:
    return SLIContract(
        contract_id=TypedId.parse("sli_contract", CONTRACT_ID),
        organization_id=OrganizationId.new(),
        customer_ref=TypedId.new("customer"),
        versions=(
            ContractVersion(
                version_no=1,
                effective=KnownValidInterval(valid_from=OCCURRED_AT, known_at=OCCURRED_AT),
                coverage_lines=(
                    CoverageLine(
                        scope=ContractScope.VEHICLE,
                        scope_value=VEHICLE_ID,
                    ),
                ),
                response_sla=SLA(
                    duration=timedelta(hours=2),
                    clock_start_event="work_order_opened",
                    clock_stop_event="technician_allocated",
                ),
                repair_sla=SLA(
                    duration=timedelta(hours=8),
                    clock_start_event="work_started",
                    clock_stop_event="technically_completed",
                ),
                availability_target_percentage=Decimal("97.5"),
            ),
        ),
    )


class _RequestWithOperation(Protocol):
    operation: str


class _ImmediateIdempotencyService:
    seen_request_operation: str | None = None

    def execute(
        self,
        request: _RequestWithOperation,
        handler: Callable[[], CanonicalPayload],
    ) -> IdempotencyExecution:
        self.seen_request_operation = request.operation
        payload = handler()
        return IdempotencyExecution(
            payload.schema,
            payload.version,
            payload.canonical_bytes,
            False,
        )


class _FakeContractContextQueryService:
    seen_vehicle_id: TypedId | None = None
    seen_instant: datetime | None = None

    def get_context_for_vehicle(
        self, *, vehicle_id: TypedId, instant: datetime
    ) -> ContractContextForVehicle:
        self.seen_vehicle_id = vehicle_id
        self.seen_instant = instant
        contract = _contract()
        return ContractContextForVehicle(
            vehicle=_vehicle(vehicle_id),
            contract=contract,
            contract_version=contract.versions[0],
            coverage_line=contract.versions[0].coverage_lines[0],
            resolved_at=instant,
        )


class _MissingContractContextQueryService:
    def get_context_for_vehicle(
        self, *, vehicle_id: TypedId, instant: datetime
    ) -> ContractContextForVehicle:
        raise ContractContextNaoEncontrado("Vehicle sem contrato vigente.")


class _AmbiguousContractContextQueryService:
    def get_context_for_vehicle(
        self, *, vehicle_id: TypedId, instant: datetime
    ) -> ContractContextForVehicle:
        raise ContractContextAmbiguo("Mais de uma cobertura vigente.")


class _FakeOpenWorkOrderService:
    seen_vehicle_ref: TypedId | None = None
    seen_site_ref: TypedId | None = None
    seen_contract_ref: TypedId | None = None
    seen_work_order_id: TypedId | None = None
    seen_expected_version: int | None = None
    seen_part_ref: TypedId | None = None
    seen_qty: Decimal | None = None
    seen_task_id: TypedId | None = None

    def open_work_order(
        self,
        _context: object,
        *,
        vehicle_ref: TypedId,
        site_ref: TypedId,
        contract_ref: TypedId,
        failure: FailureRecord,
        at_instant: datetime,
        occurred_at: datetime,
    ) -> WorkOrder:
        self.seen_vehicle_ref = vehicle_ref
        self.seen_site_ref = site_ref
        self.seen_contract_ref = contract_ref
        return WorkOrder(
            work_order_id=TypedId.parse("work_order", "00000000-0000-0000-0000-000000000301"),
            organization_id=OrganizationId.new(),
            vehicle_ref=vehicle_ref,
            site_ref=site_ref,
            contract_context=ContractContext(
                contract_ref=contract_ref,
                contract_version_no=1,
                resolved_at=at_instant,
            ),
            failure=failure,
            created_at=occurred_at,
        )

    def demand_material(
        self,
        _context: object,
        work_order_id: TypedId,
        *,
        part_ref: TypedId,
        qty: Decimal,
        task_id: TypedId,
        expected_version: int | None,
        occurred_at: datetime,
    ) -> WorkOrder:
        self.seen_work_order_id = work_order_id
        self.seen_part_ref = part_ref
        self.seen_qty = qty
        self.seen_task_id = task_id
        self.seen_expected_version = expected_version
        task = WorkTask(
            task_id=task_id,
            description="Inspecionar bomba",
            mandatory=True,
        )
        demand = MaterialDemand(part_ref=part_ref, qty=qty, task_id=task_id)
        return WorkOrder(
            work_order_id=work_order_id,
            organization_id=OrganizationId.new(),
            vehicle_ref=TypedId.parse("vehicle", VEHICLE_ID),
            site_ref=TypedId.parse("customer_site", SITE_ID),
            contract_context=ContractContext(
                contract_ref=TypedId.parse("sli_contract", CONTRACT_ID),
                contract_version_no=1,
                resolved_at=OCCURRED_AT,
            ),
            failure=FailureRecord(mode="Falha hidráulica", reported_at=OCCURRED_AT),
            tasks=(task,),
            material_demands=(demand,),
            version=(expected_version or 1) + 1,
            created_at=occurred_at,
        )

    def add_task(
        self,
        _context: object,
        work_order_id: TypedId,
        *,
        description: str,
        mandatory: bool,
        expected_version: int | None,
        occurred_at: datetime,
    ) -> WorkOrder:
        self.seen_work_order_id = work_order_id
        self.seen_expected_version = expected_version
        task = WorkTask(
            task_id=TypedId.parse("work_task", "00000000-0000-0000-0000-000000000901"),
            description=description,
            mandatory=mandatory,
        )
        return WorkOrder(
            work_order_id=work_order_id,
            organization_id=OrganizationId.new(),
            vehicle_ref=TypedId.parse("vehicle", VEHICLE_ID),
            site_ref=TypedId.parse("customer_site", SITE_ID),
            contract_context=ContractContext(
                contract_ref=TypedId.parse("sli_contract", CONTRACT_ID),
                contract_version_no=1,
                resolved_at=OCCURRED_AT,
            ),
            failure=FailureRecord(mode="Falha hidráulica", reported_at=OCCURRED_AT),
            tasks=(task,),
            version=(expected_version or 1) + 1,
            created_at=occurred_at,
        )

    def mark_planned(
        self,
        _context: object,
        work_order_id: TypedId,
        *,
        expected_version: int | None,
        occurred_at: datetime,
    ) -> WorkOrder:
        self.seen_work_order_id = work_order_id
        self.seen_expected_version = expected_version
        task = WorkTask(
            task_id=TypedId.parse("work_task", "00000000-0000-0000-0000-000000000901"),
            description="Inspecionar bomba",
            mandatory=True,
        )
        demand = MaterialDemand(
            part_ref=TypedId.parse("part", "00000000-0000-0000-0000-000000000701"),
            qty=Decimal("2"),
            task_id=task.task_id,
        )
        return WorkOrder(
            work_order_id=work_order_id,
            organization_id=OrganizationId.new(),
            vehicle_ref=TypedId.parse("vehicle", VEHICLE_ID),
            site_ref=TypedId.parse("customer_site", SITE_ID),
            contract_context=ContractContext(
                contract_ref=TypedId.parse("sli_contract", CONTRACT_ID),
                contract_version_no=1,
                resolved_at=OCCURRED_AT,
            ),
            failure=FailureRecord(mode="Falha hidráulica", reported_at=OCCURRED_AT),
            tasks=(task,),
            material_demands=(demand,),
            state=WorkOrderState.PLANNED,
            version=(expected_version or 1) + 1,
            created_at=occurred_at,
        )


class _ConflictingTaskWorkOrderService(_FakeOpenWorkOrderService):
    def add_task(
        self,
        _context: object,
        work_order_id: TypedId,
        *,
        description: str,
        mandatory: bool,
        expected_version: int | None,
        occurred_at: datetime,
    ) -> WorkOrder:
        raise OptimisticConcurrencyConflict()

    def demand_material(
        self,
        _context: object,
        work_order_id: TypedId,
        *,
        part_ref: TypedId,
        qty: Decimal,
        task_id: TypedId,
        expected_version: int | None,
        occurred_at: datetime,
    ) -> WorkOrder:
        raise OptimisticConcurrencyConflict()

    def mark_planned(
        self,
        _context: object,
        work_order_id: TypedId,
        *,
        expected_version: int | None,
        occurred_at: datetime,
    ) -> WorkOrder:
        raise OptimisticConcurrencyConflict()


def _fake_connection() -> object:
    return SimpleNamespace()


def test_open_work_order_route_is_registered_in_openapi() -> None:
    paths = set(main_module.app.openapi()["paths"])

    assert "/v1/asset/work-orders" in paths
    assert "post" in main_module.app.openapi()["paths"]["/v1/asset/work-orders"]
    assert "/v1/asset/work-orders/{work_order_id}/tasks" in paths
    assert (
        "post" in main_module.app.openapi()["paths"]["/v1/asset/work-orders/{work_order_id}/tasks"]
    )
    assert "/v1/asset/work-orders/{work_order_id}/material-demands" in paths
    assert (
        "post"
        in main_module.app.openapi()["paths"][
            "/v1/asset/work-orders/{work_order_id}/material-demands"
        ]
    )
    assert "/v1/asset/work-orders/{work_order_id}/mark-planned" in paths
    assert (
        "post"
        in main_module.app.openapi()["paths"]["/v1/asset/work-orders/{work_order_id}/mark-planned"]
    )


def test_open_work_order_requires_authentication() -> None:
    response = TestClient(main_module.app).post(
        ROUTE,
        json=_body(),
        headers={"Idempotency-Key": "open-wo-test-001"},
    )

    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")


def test_open_work_order_rejects_missing_permission(monkeypatch: MonkeyPatch) -> None:
    contexto = _context(permissions=frozenset())
    main_module.app.dependency_overrides[require_authenticated_principal] = lambda: (
        contexto.authenticated_principal
    )
    main_module.app.dependency_overrides[request_connection] = _fake_connection
    main_module.app.dependency_overrides[asset_commands.get_open_work_order_service] = (
        _FakeOpenWorkOrderService
    )
    main_module.app.dependency_overrides[asset_commands.get_contract_context_query_service] = (
        _FakeContractContextQueryService
    )
    main_module.app.dependency_overrides[asset_commands.get_idempotency_service] = (
        _ImmediateIdempotencyService
    )
    monkeypatch.setattr(
        "apps.api.livestock_dependencies.resolve_organization_context",
        lambda *_args, **_kwargs: contexto,
    )

    response = TestClient(main_module.app).post(
        ROUTE,
        json=_body(),
        headers={
            ORGANIZATION_HEADER: str(contexto.organization_id.value),
            "Idempotency-Key": "open-wo-test-002",
        },
    )

    assert response.status_code == 403
    assert response.json()["reason_code"] == "PERMISSAO_AUSENTE"


def test_open_work_order_returns_created_work_order() -> None:
    contexto = _context()
    service = _FakeOpenWorkOrderService()
    context_query = _FakeContractContextQueryService()
    idempotency = _ImmediateIdempotencyService()
    main_module.app.dependency_overrides[asset_commands.require_work_order_open] = lambda: contexto
    main_module.app.dependency_overrides[asset_commands.get_open_work_order_service] = lambda: (
        service
    )
    main_module.app.dependency_overrides[asset_commands.get_contract_context_query_service] = (
        lambda: context_query
    )
    main_module.app.dependency_overrides[asset_commands.get_idempotency_service] = lambda: (
        idempotency
    )

    response = TestClient(main_module.app).post(
        ROUTE,
        json=_body(),
        headers={"Idempotency-Key": "open-wo-test-003"},
    )

    assert response.status_code == 201
    assert context_query.seen_vehicle_id == TypedId.parse("vehicle", VEHICLE_ID)
    assert service.seen_vehicle_ref == TypedId.parse("vehicle", VEHICLE_ID)
    assert service.seen_site_ref == TypedId.parse("customer_site", SITE_ID)
    assert service.seen_contract_ref == TypedId.parse("sli_contract", CONTRACT_ID)
    assert idempotency.seen_request_operation == asset_commands.OPEN_WORK_ORDER_OPERATION
    payload = response.json()
    assert payload["work_order_id"] == "00000000-0000-0000-0000-000000000301"
    assert payload["vehicle_ref"] == VEHICLE_ID
    assert payload["site_ref"] == SITE_ID
    assert payload["contract_context"]["contract_ref"] == CONTRACT_ID
    assert payload["state"] == "DRAFT"
    assert payload["failure"] == {
        "mode": "Falha hidráulica",
        "reported_at": "2026-10-03T12:00:00Z",
        "affected_position": "braço",
    }


def test_open_work_order_requires_idempotency_key() -> None:
    contexto = _context()
    main_module.app.dependency_overrides[asset_commands.require_work_order_open] = lambda: contexto
    main_module.app.dependency_overrides[asset_commands.get_open_work_order_service] = (
        _FakeOpenWorkOrderService
    )
    main_module.app.dependency_overrides[asset_commands.get_contract_context_query_service] = (
        _FakeContractContextQueryService
    )
    main_module.app.dependency_overrides[asset_commands.get_idempotency_service] = (
        _ImmediateIdempotencyService
    )

    response = TestClient(main_module.app).post(ROUTE, json=_body())

    assert response.status_code == 422
    assert response.json()["reason_code"] == "ENTRADA_INVALIDA"


def test_open_work_order_rejects_invalid_vehicle_id() -> None:
    contexto = _context()
    main_module.app.dependency_overrides[asset_commands.require_work_order_open] = lambda: contexto
    main_module.app.dependency_overrides[asset_commands.get_open_work_order_service] = (
        _FakeOpenWorkOrderService
    )
    main_module.app.dependency_overrides[asset_commands.get_contract_context_query_service] = (
        _FakeContractContextQueryService
    )
    main_module.app.dependency_overrides[asset_commands.get_idempotency_service] = (
        _ImmediateIdempotencyService
    )

    response = TestClient(main_module.app).post(
        ROUTE,
        json=_body(vehicle_id="nao-e-uuid"),
        headers={"Idempotency-Key": "open-wo-test-004"},
    )

    assert response.status_code == 422
    assert response.json()["reason_code"] == "IDENTIFICADOR_INVALIDO"


def test_open_work_order_rejects_non_utc_instant() -> None:
    contexto = _context()
    main_module.app.dependency_overrides[asset_commands.require_work_order_open] = lambda: contexto
    main_module.app.dependency_overrides[asset_commands.get_open_work_order_service] = (
        _FakeOpenWorkOrderService
    )
    main_module.app.dependency_overrides[asset_commands.get_contract_context_query_service] = (
        _FakeContractContextQueryService
    )
    main_module.app.dependency_overrides[asset_commands.get_idempotency_service] = (
        _ImmediateIdempotencyService
    )

    response = TestClient(main_module.app).post(
        ROUTE,
        json=_body(at_instant="2026-10-03T08:00:00-04:00"),
        headers={"Idempotency-Key": "open-wo-test-005"},
    )

    assert response.status_code == 422
    assert response.json()["reason_code"] == "DATA_INVALIDA"


def test_open_work_order_returns_404_when_contract_context_missing() -> None:
    contexto = _context()
    main_module.app.dependency_overrides[asset_commands.require_work_order_open] = lambda: contexto
    main_module.app.dependency_overrides[asset_commands.get_open_work_order_service] = (
        _FakeOpenWorkOrderService
    )
    main_module.app.dependency_overrides[asset_commands.get_contract_context_query_service] = (
        _MissingContractContextQueryService
    )
    main_module.app.dependency_overrides[asset_commands.get_idempotency_service] = (
        _ImmediateIdempotencyService
    )

    response = TestClient(main_module.app).post(
        ROUTE,
        json=_body(),
        headers={"Idempotency-Key": "open-wo-test-006"},
    )

    assert response.status_code == 404
    assert response.json()["reason_code"] == "RECURSO_NAO_ENCONTRADO"


def test_open_work_order_returns_409_when_contract_context_is_ambiguous() -> None:
    contexto = _context()
    main_module.app.dependency_overrides[asset_commands.require_work_order_open] = lambda: contexto
    main_module.app.dependency_overrides[asset_commands.get_open_work_order_service] = (
        _FakeOpenWorkOrderService
    )
    main_module.app.dependency_overrides[asset_commands.get_contract_context_query_service] = (
        _AmbiguousContractContextQueryService
    )
    main_module.app.dependency_overrides[asset_commands.get_idempotency_service] = (
        _ImmediateIdempotencyService
    )

    response = TestClient(main_module.app).post(
        ROUTE,
        json=_body(),
        headers={"Idempotency-Key": "open-wo-test-007"},
    )

    assert response.status_code == 409
    assert response.json()["reason_code"] == "CONFLITO_DE_DOMINIO"


def test_add_work_order_task_requires_authentication() -> None:
    response = TestClient(main_module.app).post(
        f"{ROUTE}/00000000-0000-0000-0000-000000000301/tasks",
        json={"expected_version": 1, "description": "Inspecionar bomba", "mandatory": True},
        headers={"Idempotency-Key": "add-task-test-001"},
    )

    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")


def test_add_work_order_task_rejects_missing_permission(monkeypatch: MonkeyPatch) -> None:
    contexto = _context(permissions=frozenset())
    main_module.app.dependency_overrides[require_authenticated_principal] = lambda: (
        contexto.authenticated_principal
    )
    main_module.app.dependency_overrides[request_connection] = _fake_connection
    main_module.app.dependency_overrides[asset_commands.get_open_work_order_service] = (
        _FakeOpenWorkOrderService
    )
    main_module.app.dependency_overrides[asset_commands.get_idempotency_service] = (
        _ImmediateIdempotencyService
    )
    monkeypatch.setattr(
        "apps.api.livestock_dependencies.resolve_organization_context",
        lambda *_args, **_kwargs: contexto,
    )

    response = TestClient(main_module.app).post(
        f"{ROUTE}/00000000-0000-0000-0000-000000000301/tasks",
        json={"expected_version": 1, "description": "Inspecionar bomba", "mandatory": True},
        headers={
            ORGANIZATION_HEADER: str(contexto.organization_id.value),
            "Idempotency-Key": "add-task-test-002",
        },
    )

    assert response.status_code == 403
    assert response.json()["reason_code"] == "PERMISSAO_AUSENTE"


def test_add_work_order_task_returns_updated_detail() -> None:
    contexto = _context(permissions=frozenset({WO_ADD_TASK}))
    service = _FakeOpenWorkOrderService()
    idempotency = _ImmediateIdempotencyService()
    main_module.app.dependency_overrides[asset_commands.require_work_order_add_task] = lambda: (
        contexto
    )
    main_module.app.dependency_overrides[asset_commands.get_open_work_order_service] = lambda: (
        service
    )
    main_module.app.dependency_overrides[asset_commands.get_idempotency_service] = lambda: (
        idempotency
    )

    response = TestClient(main_module.app).post(
        f"{ROUTE}/00000000-0000-0000-0000-000000000301/tasks",
        json={"expected_version": 1, "description": "Inspecionar bomba", "mandatory": True},
        headers={"Idempotency-Key": "add-task-test-003"},
    )

    assert response.status_code == 200
    assert service.seen_work_order_id == TypedId.parse(
        "work_order", "00000000-0000-0000-0000-000000000301"
    )
    assert service.seen_expected_version == 1
    assert idempotency.seen_request_operation == asset_commands.ADD_WORK_ORDER_TASK_OPERATION
    payload = response.json()
    assert payload["version"] == 2
    assert payload["tasks"] == [
        {
            "task_id": "00000000-0000-0000-0000-000000000901",
            "description": "Inspecionar bomba",
            "mandatory": True,
            "state": "PENDING",
            "labor_entries": [],
        }
    ]


def test_add_work_order_task_rejects_invalid_identifier() -> None:
    contexto = _context(permissions=frozenset({WO_ADD_TASK}))
    main_module.app.dependency_overrides[asset_commands.require_work_order_add_task] = lambda: (
        contexto
    )
    main_module.app.dependency_overrides[asset_commands.get_open_work_order_service] = (
        _FakeOpenWorkOrderService
    )
    main_module.app.dependency_overrides[asset_commands.get_idempotency_service] = (
        _ImmediateIdempotencyService
    )

    response = TestClient(main_module.app).post(
        f"{ROUTE}/nao-e-uuid/tasks",
        json={"expected_version": 1, "description": "Inspecionar bomba", "mandatory": True},
        headers={"Idempotency-Key": "add-task-test-004"},
    )

    assert response.status_code == 422
    assert response.json()["reason_code"] == "IDENTIFICADOR_INVALIDO"


def test_add_work_order_task_returns_409_on_stale_version() -> None:
    contexto = _context(permissions=frozenset({WO_ADD_TASK}))
    main_module.app.dependency_overrides[asset_commands.require_work_order_add_task] = lambda: (
        contexto
    )
    main_module.app.dependency_overrides[asset_commands.get_open_work_order_service] = (
        _ConflictingTaskWorkOrderService
    )
    main_module.app.dependency_overrides[asset_commands.get_idempotency_service] = (
        _ImmediateIdempotencyService
    )

    response = TestClient(main_module.app).post(
        f"{ROUTE}/00000000-0000-0000-0000-000000000301/tasks",
        json={"expected_version": 1, "description": "Inspecionar bomba", "mandatory": True},
        headers={"Idempotency-Key": "add-task-test-005"},
    )

    assert response.status_code == 409
    assert response.json()["reason_code"] == OptimisticConcurrencyConflict.code


def test_demand_work_order_material_requires_authentication() -> None:
    response = TestClient(main_module.app).post(
        f"{ROUTE}/00000000-0000-0000-0000-000000000301/material-demands",
        json={
            "expected_version": 2,
            "part_id": "00000000-0000-0000-0000-000000000701",
            "qty": "2",
            "task_id": "00000000-0000-0000-0000-000000000901",
        },
        headers={"Idempotency-Key": "demand-material-test-001"},
    )

    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")


def test_demand_work_order_material_rejects_missing_permission(monkeypatch: MonkeyPatch) -> None:
    contexto = _context(permissions=frozenset())
    main_module.app.dependency_overrides[require_authenticated_principal] = lambda: (
        contexto.authenticated_principal
    )
    main_module.app.dependency_overrides[request_connection] = _fake_connection
    main_module.app.dependency_overrides[asset_commands.get_open_work_order_service] = (
        _FakeOpenWorkOrderService
    )
    main_module.app.dependency_overrides[asset_commands.get_idempotency_service] = (
        _ImmediateIdempotencyService
    )
    monkeypatch.setattr(
        "apps.api.livestock_dependencies.resolve_organization_context",
        lambda *_args, **_kwargs: contexto,
    )

    response = TestClient(main_module.app).post(
        f"{ROUTE}/00000000-0000-0000-0000-000000000301/material-demands",
        json={
            "expected_version": 2,
            "part_id": "00000000-0000-0000-0000-000000000701",
            "qty": "2",
            "task_id": "00000000-0000-0000-0000-000000000901",
        },
        headers={
            ORGANIZATION_HEADER: str(contexto.organization_id.value),
            "Idempotency-Key": "demand-material-test-002",
        },
    )

    assert response.status_code == 403
    assert response.json()["reason_code"] == "PERMISSAO_AUSENTE"


def test_demand_work_order_material_returns_updated_detail() -> None:
    contexto = _context(permissions=frozenset({WO_DEMAND_MATERIAL}))
    service = _FakeOpenWorkOrderService()
    idempotency = _ImmediateIdempotencyService()
    main_module.app.dependency_overrides[asset_commands.require_work_order_demand_material] = (
        lambda: contexto
    )
    main_module.app.dependency_overrides[asset_commands.get_open_work_order_service] = lambda: (
        service
    )
    main_module.app.dependency_overrides[asset_commands.get_idempotency_service] = lambda: (
        idempotency
    )

    response = TestClient(main_module.app).post(
        f"{ROUTE}/00000000-0000-0000-0000-000000000301/material-demands",
        json={
            "expected_version": 2,
            "part_id": "00000000-0000-0000-0000-000000000701",
            "qty": "2",
            "task_id": "00000000-0000-0000-0000-000000000901",
        },
        headers={"Idempotency-Key": "demand-material-test-003"},
    )

    assert response.status_code == 200
    assert service.seen_work_order_id == TypedId.parse(
        "work_order", "00000000-0000-0000-0000-000000000301"
    )
    assert service.seen_part_ref == TypedId.parse("part", "00000000-0000-0000-0000-000000000701")
    assert service.seen_qty == Decimal("2")
    assert service.seen_task_id == TypedId.parse(
        "work_task", "00000000-0000-0000-0000-000000000901"
    )
    assert service.seen_expected_version == 2
    assert idempotency.seen_request_operation == asset_commands.DEMAND_MATERIAL_OPERATION
    payload = response.json()
    assert payload["version"] == 3
    assert payload["material_demands"] == [
        {
            "part_ref": "00000000-0000-0000-0000-000000000701",
            "qty": "2",
            "task_id": "00000000-0000-0000-0000-000000000901",
        }
    ]


def test_demand_work_order_material_rejects_invalid_identifier() -> None:
    contexto = _context(permissions=frozenset({WO_DEMAND_MATERIAL}))
    main_module.app.dependency_overrides[asset_commands.require_work_order_demand_material] = (
        lambda: contexto
    )
    main_module.app.dependency_overrides[asset_commands.get_open_work_order_service] = (
        _FakeOpenWorkOrderService
    )
    main_module.app.dependency_overrides[asset_commands.get_idempotency_service] = (
        _ImmediateIdempotencyService
    )

    response = TestClient(main_module.app).post(
        f"{ROUTE}/nao-e-uuid/material-demands",
        json={
            "expected_version": 2,
            "part_id": "00000000-0000-0000-0000-000000000701",
            "qty": "2",
            "task_id": "00000000-0000-0000-0000-000000000901",
        },
        headers={"Idempotency-Key": "demand-material-test-004"},
    )

    assert response.status_code == 422
    assert response.json()["reason_code"] == "IDENTIFICADOR_INVALIDO"


def test_demand_work_order_material_returns_409_on_stale_version() -> None:
    contexto = _context(permissions=frozenset({WO_DEMAND_MATERIAL}))
    main_module.app.dependency_overrides[asset_commands.require_work_order_demand_material] = (
        lambda: contexto
    )
    main_module.app.dependency_overrides[asset_commands.get_open_work_order_service] = (
        _ConflictingTaskWorkOrderService
    )
    main_module.app.dependency_overrides[asset_commands.get_idempotency_service] = (
        _ImmediateIdempotencyService
    )

    response = TestClient(main_module.app).post(
        f"{ROUTE}/00000000-0000-0000-0000-000000000301/material-demands",
        json={
            "expected_version": 2,
            "part_id": "00000000-0000-0000-0000-000000000701",
            "qty": "2",
            "task_id": "00000000-0000-0000-0000-000000000901",
        },
        headers={"Idempotency-Key": "demand-material-test-005"},
    )

    assert response.status_code == 409
    assert response.json()["reason_code"] == OptimisticConcurrencyConflict.code


def test_mark_work_order_planned_requires_authentication() -> None:
    response = TestClient(main_module.app).post(
        f"{ROUTE}/00000000-0000-0000-0000-000000000301/mark-planned",
        json={"expected_version": 3},
        headers={"Idempotency-Key": "mark-planned-test-001"},
    )

    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")


def test_mark_work_order_planned_rejects_missing_permission(monkeypatch: MonkeyPatch) -> None:
    contexto = _context(permissions=frozenset())
    main_module.app.dependency_overrides[require_authenticated_principal] = lambda: (
        contexto.authenticated_principal
    )
    main_module.app.dependency_overrides[request_connection] = _fake_connection
    main_module.app.dependency_overrides[asset_commands.get_open_work_order_service] = (
        _FakeOpenWorkOrderService
    )
    main_module.app.dependency_overrides[asset_commands.get_idempotency_service] = (
        _ImmediateIdempotencyService
    )
    monkeypatch.setattr(
        "apps.api.livestock_dependencies.resolve_organization_context",
        lambda *_args, **_kwargs: contexto,
    )

    response = TestClient(main_module.app).post(
        f"{ROUTE}/00000000-0000-0000-0000-000000000301/mark-planned",
        json={"expected_version": 3},
        headers={
            ORGANIZATION_HEADER: str(contexto.organization_id.value),
            "Idempotency-Key": "mark-planned-test-002",
        },
    )

    assert response.status_code == 403
    assert response.json()["reason_code"] == "PERMISSAO_AUSENTE"


def test_mark_work_order_planned_returns_updated_detail() -> None:
    contexto = _context(permissions=frozenset({WO_TRANSITION}))
    service = _FakeOpenWorkOrderService()
    idempotency = _ImmediateIdempotencyService()
    main_module.app.dependency_overrides[asset_commands.require_work_order_transition] = lambda: (
        contexto
    )
    main_module.app.dependency_overrides[asset_commands.get_open_work_order_service] = lambda: (
        service
    )
    main_module.app.dependency_overrides[asset_commands.get_idempotency_service] = lambda: (
        idempotency
    )

    response = TestClient(main_module.app).post(
        f"{ROUTE}/00000000-0000-0000-0000-000000000301/mark-planned",
        json={"expected_version": 3},
        headers={"Idempotency-Key": "mark-planned-test-003"},
    )

    assert response.status_code == 200
    assert service.seen_work_order_id == TypedId.parse(
        "work_order", "00000000-0000-0000-0000-000000000301"
    )
    assert service.seen_expected_version == 3
    assert idempotency.seen_request_operation == asset_commands.MARK_WORK_ORDER_PLANNED_OPERATION
    payload = response.json()
    assert payload["state"] == "PLANNED"
    assert payload["version"] == 4


def test_mark_work_order_planned_rejects_invalid_identifier() -> None:
    contexto = _context(permissions=frozenset({WO_TRANSITION}))
    main_module.app.dependency_overrides[asset_commands.require_work_order_transition] = lambda: (
        contexto
    )
    main_module.app.dependency_overrides[asset_commands.get_open_work_order_service] = (
        _FakeOpenWorkOrderService
    )
    main_module.app.dependency_overrides[asset_commands.get_idempotency_service] = (
        _ImmediateIdempotencyService
    )

    response = TestClient(main_module.app).post(
        f"{ROUTE}/nao-e-uuid/mark-planned",
        json={"expected_version": 3},
        headers={"Idempotency-Key": "mark-planned-test-004"},
    )

    assert response.status_code == 422
    assert response.json()["reason_code"] == "IDENTIFICADOR_INVALIDO"


def test_mark_work_order_planned_returns_409_on_stale_version() -> None:
    contexto = _context(permissions=frozenset({WO_TRANSITION}))
    main_module.app.dependency_overrides[asset_commands.require_work_order_transition] = lambda: (
        contexto
    )
    main_module.app.dependency_overrides[asset_commands.get_open_work_order_service] = (
        _ConflictingTaskWorkOrderService
    )
    main_module.app.dependency_overrides[asset_commands.get_idempotency_service] = (
        _ImmediateIdempotencyService
    )

    response = TestClient(main_module.app).post(
        f"{ROUTE}/00000000-0000-0000-0000-000000000301/mark-planned",
        json={"expected_version": 3},
        headers={"Idempotency-Key": "mark-planned-test-005"},
    )

    assert response.status_code == 409
    assert response.json()["reason_code"] == OptimisticConcurrencyConflict.code
