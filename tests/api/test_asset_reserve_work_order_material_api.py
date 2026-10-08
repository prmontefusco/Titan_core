"""Contrato HTTP de `ReserveMaterialForWorkOrder` — Titan Asset A5."""

import importlib
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
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
from packages.asset_application.authorization import WO_RESERVE_MATERIAL
from packages.asset_application.entitlement_service import EntitlementResolution
from packages.asset_application.event_recorder import AssetOperationContext
from packages.asset_domain.events import (
    SUSTAINMENT_ENTITLEMENT_RESOLVED,
    sustainment_entitlement_resolved_payload,
)
from packages.asset_domain.work_order import ContractContext, FailureRecord, WorkOrder
from packages.core_application import IdempotencyExecution, OptimisticConcurrencyConflict
from packages.core_domain import AuthenticatedPrincipal, CanonicalPayload, OrganizationContext
from packages.core_domain.organization_context import PrincipalType
from packages.shared_kernel import OrganizationId, TypedId

WORK_ORDER_ID = "00000000-0000-0000-0000-000000001301"
VEHICLE_ID = "00000000-0000-0000-0000-000000001302"
PART_ID = "00000000-0000-0000-0000-000000001303"
POSITION_ID = "00000000-0000-0000-0000-000000001304"
ENTITLEMENT_EVENT_ID = "00000000-0000-0000-0000-000000001305"
DECISION_ID = "00000000-0000-0000-0000-000000001306"
ROUTE = f"/v1/asset/work-orders/{WORK_ORDER_ID}/material-reservations"
NOW = datetime(2026, 10, 8, 16, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _restore_app() -> Iterator[None]:
    yield
    main_module.app.dependency_overrides.clear()
    importlib.reload(main_module)


def _context(
    permissions: frozenset[str] = frozenset({WO_RESERVE_MATERIAL}),
) -> OrganizationContext:
    return OrganizationContext(
        organization_id=OrganizationId.new(),
        authenticated_principal=AuthenticatedPrincipal(
            issuer="https://issuer.example.test",
            subject="reserve-material-test-user",
            principal_type=PrincipalType.USER,
            authenticated_at=NOW,
            client_id="reserve-material-test",
            technical_scopes=frozenset({"openid"}),
        ),
        user_id=TypedId.new("user"),
        actor_id=TypedId.new("actor"),
        membership_id=TypedId.new("membership"),
        role_ids=(TypedId.new("role"),),
        permission_codes=permissions,
        validated_at=NOW,
    )


def _body(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "expected_version": 2,
        "stock_position_id": POSITION_ID,
        "part_id": PART_ID,
        "qty": "2",
        "priority": 10,
        "entitlement_event_id": ENTITLEMENT_EVENT_ID,
    }
    body.update(overrides)
    return body


class _Request(Protocol):
    operation: str


class _Idempotency:
    def execute(
        self, request: _Request, handler: Callable[[], CanonicalPayload]
    ) -> IdempotencyExecution:
        assert request.operation == "asset.work_order.reserve_material"
        payload = handler()
        return IdempotencyExecution(payload.schema, payload.version, payload.canonical_bytes, False)


class _EventLog:
    def __init__(self, *, found: bool = True) -> None:
        self.found = found

    def get_by_id(self, event_id: TypedId) -> object | None:
        assert event_id.value.hex == ENTITLEMENT_EVENT_ID.replace("-", "")
        if not self.found:
            return None
        payload = sustainment_entitlement_resolved_payload(
            vehicle_ref=TypedId.parse("vehicle", VEHICLE_ID),
            subject_ref=TypedId.parse("part", PART_ID),
            instant=NOW,
            decision_ref=TypedId.parse("decision", DECISION_ID),
            outcome="GRANTED",
            breakdown="Cobertura contratual fictícia válida.",
        )
        return SimpleNamespace(
            event_type=SUSTAINMENT_ENTITLEMENT_RESOLVED,
            payload_canonical_bytes=payload.canonical_bytes,
        )


class _Service:
    def __init__(self, organization_id: OrganizationId, *, conflict: bool = False) -> None:
        self.organization_id = organization_id
        self.conflict = conflict

    def reserve_material_for_work_order(
        self,
        context: AssetOperationContext,
        work_order_id: TypedId,
        *,
        stock_position_id: TypedId,
        part_ref: TypedId,
        qty: Decimal,
        priority: int,
        entitlement: EntitlementResolution,
        occurred_at: datetime,
        expected_version: int | None = None,
    ) -> WorkOrder:
        del occurred_at
        if self.conflict:
            raise OptimisticConcurrencyConflict()
        assert context.organization_id == self.organization_id
        assert stock_position_id.value.hex == POSITION_ID.replace("-", "")
        assert part_ref.value.hex == PART_ID.replace("-", "")
        assert qty == Decimal("2")
        assert priority == 10
        assert entitlement.decision_ref.value.hex == DECISION_ID.replace("-", "")
        assert expected_version == 2
        return WorkOrder(
            work_order_id=work_order_id,
            organization_id=self.organization_id,
            vehicle_ref=TypedId.parse("vehicle", VEHICLE_ID),
            site_ref=TypedId.new("customer_site"),
            contract_context=ContractContext(
                contract_ref=TypedId.new("sli_contract"),
                contract_version_no=1,
                resolved_at=NOW,
            ),
            failure=FailureRecord(mode="Falha fictícia", reported_at=NOW),
            material_reservations=(TypedId.new("stock_reservation"),),
            version=3,
            created_at=NOW,
        )


def _override(
    context: OrganizationContext,
    *,
    service: _Service | None = None,
    event_log: _EventLog | None = None,
) -> None:
    main_module.app.dependency_overrides[asset_commands.require_work_order_reserve_material] = (
        lambda: context
    )
    main_module.app.dependency_overrides[asset_commands.get_open_work_order_service] = lambda: (
        service or _Service(context.organization_id)
    )
    main_module.app.dependency_overrides[asset_commands.get_domain_event_repository] = lambda: (
        event_log or _EventLog()
    )
    main_module.app.dependency_overrides[asset_commands.get_idempotency_service] = _Idempotency


def test_route_is_registered() -> None:
    assert (
        "/v1/asset/work-orders/{work_order_id}/material-reservations"
        in main_module.app.openapi()["paths"]
    )


def test_reserve_material_requires_authentication() -> None:
    response = TestClient(main_module.app).post(
        ROUTE, json=_body(), headers={"Idempotency-Key": "reserve-material-auth"}
    )
    assert response.status_code == 401


def test_reserve_material_rejects_missing_permission(monkeypatch: MonkeyPatch) -> None:
    context = _context(frozenset())
    main_module.app.dependency_overrides[require_authenticated_principal] = lambda: (
        context.authenticated_principal
    )
    main_module.app.dependency_overrides[request_connection] = lambda: SimpleNamespace()
    monkeypatch.setattr(
        "apps.api.livestock_dependencies.resolve_organization_context",
        lambda *_args, **_kwargs: context,
    )
    response = TestClient(main_module.app).post(
        ROUTE,
        json=_body(),
        headers={
            ORGANIZATION_HEADER: str(context.organization_id.value),
            "Idempotency-Key": "reserve-material-permission",
        },
    )
    assert response.status_code == 403
    assert response.json()["reason_code"] == "PERMISSAO_AUSENTE"


def test_reserve_material_uses_persisted_entitlement() -> None:
    context = _context()
    _override(context)
    response = TestClient(main_module.app).post(
        ROUTE, json=_body(), headers={"Idempotency-Key": "reserve-material-success"}
    )
    assert response.status_code == 200
    assert len(response.json()["material_reservations"]) == 1
    assert response.json()["version"] == 3


def test_reserve_material_rejects_missing_entitlement_event() -> None:
    context = _context()
    _override(context, event_log=_EventLog(found=False))
    response = TestClient(main_module.app).post(
        ROUTE,
        json=_body(),
        headers={"Idempotency-Key": "reserve-material-entitlement-missing"},
    )
    assert response.status_code == 404


def test_reserve_material_translates_version_conflict() -> None:
    context = _context()
    _override(context, service=_Service(context.organization_id, conflict=True))
    response = TestClient(main_module.app).post(
        ROUTE, json=_body(), headers={"Idempotency-Key": "reserve-material-version"}
    )
    assert response.status_code == 409
    assert response.json()["reason_code"] == OptimisticConcurrencyConflict.code
