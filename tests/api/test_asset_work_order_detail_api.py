"""Contrato HTTP de `GetWorkOrder` — Titan Asset A5."""

import importlib
from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pytest import MonkeyPatch

import apps.api.main as main_module
from apps.api.asset import queries as asset_queries
from apps.api.authentication import require_authenticated_principal
from apps.api.livestock_dependencies import ORGANIZATION_HEADER, request_connection
from packages.asset_application.authorization import WO_READ
from packages.asset_application.work_order_query import WorkOrderDetailNaoEncontrado
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
from packages.core_domain import AuthenticatedPrincipal, OrganizationContext, PrincipalType
from packages.shared_kernel import OrganizationId, TypedId

WORK_ORDER_ID = "00000000-0000-0000-0000-000000000301"
ROUTE = f"/v1/asset/work-orders/{WORK_ORDER_ID}"
OCCURRED_AT = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _restore_default_app() -> Iterator[None]:
    yield
    main_module.app.dependency_overrides.clear()
    importlib.reload(main_module)


def _context(permissions: frozenset[str] = frozenset({WO_READ})) -> OrganizationContext:
    return OrganizationContext(
        organization_id=OrganizationId.new(),
        authenticated_principal=AuthenticatedPrincipal(
            issuer="https://issuer.example.test",
            subject="asset-work-order-test-user",
            principal_type=PrincipalType.USER,
            authenticated_at=OCCURRED_AT,
            client_id="asset-work-order-test",
            technical_scopes=frozenset({"openid"}),
        ),
        user_id=TypedId.new("user"),
        actor_id=TypedId.new("actor"),
        membership_id=TypedId.new("membership"),
        role_ids=(TypedId.new("role"),),
        permission_codes=permissions,
        validated_at=OCCURRED_AT,
    )


def _work_order(work_order_id: TypedId) -> WorkOrder:
    task = WorkTask(
        task_id=TypedId.parse("work_task", "00000000-0000-0000-0000-000000000901"),
        description="Trocar bomba hidráulica",
        mandatory=True,
        state=WorkTaskState.DONE,
        labor_entries=("2h",),
    )
    return WorkOrder(
        work_order_id=work_order_id,
        organization_id=OrganizationId.new(),
        vehicle_ref=TypedId.parse("vehicle", "00000000-0000-0000-0000-000000000401"),
        site_ref=TypedId.parse("customer_site", "00000000-0000-0000-0000-000000000101"),
        contract_context=ContractContext(
            contract_ref=TypedId.parse("sli_contract", "00000000-0000-0000-0000-000000000701"),
            contract_version_no=3,
            resolved_at=OCCURRED_AT,
        ),
        failure=FailureRecord(
            mode="Falha hidráulica",
            reported_at=OCCURRED_AT,
            affected_position="braço",
        ),
        workshop_ref=TypedId.parse("workshop", "00000000-0000-0000-0000-000000000201"),
        tasks=(task,),
        material_demands=(
            MaterialDemand(
                part_ref=TypedId.parse("part", "00000000-0000-0000-0000-000000000801"),
                qty=Decimal("2.5"),
                task_id=task.task_id,
            ),
        ),
        material_reservations=(
            TypedId.parse("stock_reservation", "00000000-0000-0000-0000-000000000601"),
        ),
        state=WorkOrderState.VALIDATION,
        priority=PriorityScore(
            score=90,
            breakdown={"sla": 60, "criticidade": 30},
            evaluation_ref=TypedId.parse("evaluation", "00000000-0000-0000-0000-000000000501"),
        ),
        diagnosis="Vazamento",
        root_cause="Vedação rompida",
        resolution="Componente substituído",
        removed_components=(
            RemovedComponentDisposition(
                part_ref=TypedId.parse("part", "00000000-0000-0000-0000-000000000801"),
                disposition="SCRAP",
                serial="SER-123",
            ),
        ),
        validation=PostMaintenanceValidation(
            validated_at=OCCURRED_AT,
            validator_ref=TypedId.parse("actor", "00000000-0000-0000-0000-000000000901"),
            result=ValidationResult.PASS_,
            notes="OK",
        ),
        created_at=OCCURRED_AT,
    )


class _FakeWorkOrderQueryService:
    seen_work_order_id: TypedId | None = None

    def get_work_order(self, work_order_id: TypedId) -> WorkOrder:
        self.seen_work_order_id = work_order_id
        return _work_order(work_order_id)


class _MissingWorkOrderQueryService:
    def get_work_order(self, work_order_id: TypedId) -> WorkOrder:
        raise WorkOrderDetailNaoEncontrado(f"WorkOrder '{work_order_id.value}' não encontrada.")


def _fake_connection() -> object:
    return SimpleNamespace()


def test_work_order_detail_route_is_registered_in_openapi() -> None:
    paths = set(main_module.app.openapi()["paths"])

    assert "/v1/asset/work-orders/{work_order_id}" in paths


def test_work_order_detail_requires_authentication() -> None:
    response = TestClient(main_module.app).get(ROUTE)

    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")


def test_work_order_detail_rejects_missing_permission(monkeypatch: MonkeyPatch) -> None:
    contexto = _context(permissions=frozenset())
    main_module.app.dependency_overrides[require_authenticated_principal] = lambda: (
        contexto.authenticated_principal
    )
    main_module.app.dependency_overrides[request_connection] = _fake_connection
    main_module.app.dependency_overrides[asset_queries.get_work_order_query_service] = (
        _FakeWorkOrderQueryService
    )

    monkeypatch.setattr(
        "apps.api.livestock_dependencies.resolve_organization_context",
        lambda *_args, **_kwargs: contexto,
    )

    response = TestClient(main_module.app).get(
        ROUTE,
        headers={ORGANIZATION_HEADER: str(contexto.organization_id.value)},
    )

    assert response.status_code == 403
    assert response.json()["reason_code"] == "PERMISSAO_AUSENTE"


def test_work_order_detail_returns_aggregate_detail() -> None:
    contexto = _context()
    service = _FakeWorkOrderQueryService()
    main_module.app.dependency_overrides[asset_queries.require_work_order_read] = lambda: contexto
    main_module.app.dependency_overrides[asset_queries.get_work_order_query_service] = lambda: (
        service
    )

    response = TestClient(main_module.app).get(ROUTE)

    assert response.status_code == 200
    assert service.seen_work_order_id == TypedId.parse("work_order", WORK_ORDER_ID)
    payload = response.json()
    assert payload["work_order_id"] == WORK_ORDER_ID
    assert payload["state"] == "VALIDATION"
    assert payload["contract_context"] == {
        "contract_ref": "00000000-0000-0000-0000-000000000701",
        "contract_version_no": 3,
        "resolved_at": "2026-10-02T12:00:00Z",
    }
    assert payload["failure"]["mode"] == "Falha hidráulica"
    assert payload["tasks"][0]["state"] == "DONE"
    assert payload["material_demands"][0]["qty"] == "2.5"
    assert payload["material_reservations"] == ["00000000-0000-0000-0000-000000000601"]
    assert payload["priority"] == {
        "score": 90,
        "breakdown": {"sla": 60, "criticidade": 30},
        "evaluation_ref": "00000000-0000-0000-0000-000000000501",
    }
    assert payload["removed_components"][0]["disposition"] == "SCRAP"
    assert payload["validation"]["result"] == "PASS"


def test_work_order_detail_rejects_invalid_identifier() -> None:
    contexto = _context()
    main_module.app.dependency_overrides[asset_queries.require_work_order_read] = lambda: contexto
    main_module.app.dependency_overrides[asset_queries.get_work_order_query_service] = (
        _FakeWorkOrderQueryService
    )

    response = TestClient(main_module.app).get("/v1/asset/work-orders/nao-e-uuid")

    assert response.status_code == 422
    assert response.json()["reason_code"] == "IDENTIFICADOR_INVALIDO"


def test_work_order_detail_returns_404_when_missing() -> None:
    contexto = _context()
    main_module.app.dependency_overrides[asset_queries.require_work_order_read] = lambda: contexto
    main_module.app.dependency_overrides[asset_queries.get_work_order_query_service] = (
        _MissingWorkOrderQueryService
    )

    response = TestClient(main_module.app).get(ROUTE)

    assert response.status_code == 404
    assert response.json()["reason_code"] == "RECURSO_NAO_ENCONTRADO"
