"""Contrato HTTP de `AllocateStockReservation` — Titan Asset A5."""

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
from packages.asset_application.authorization import INVENTORY_ALLOCATE
from packages.asset_application.event_recorder import AssetOperationContext
from packages.asset_domain.inventory import (
    DemandKind,
    DemandRef,
    ReservationState,
    StockPurpose,
    StockReservation,
)
from packages.core_application import IdempotencyExecution, OptimisticConcurrencyConflict
from packages.core_domain import AuthenticatedPrincipal, CanonicalPayload, OrganizationContext
from packages.core_domain.organization_context import PrincipalType
from packages.shared_kernel import OrganizationId, TypedId

RESERVATION_ID = "00000000-0000-0000-0000-000000001501"
POSITION_ID = "00000000-0000-0000-0000-000000001502"
WORK_ORDER_ID = "00000000-0000-0000-0000-000000001503"
ROUTE = f"/v1/asset/stock-reservations/{RESERVATION_ID}/allocate"
NOW = datetime(2026, 10, 13, 14, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _restore_app() -> Iterator[None]:
    yield
    main_module.app.dependency_overrides.clear()
    importlib.reload(main_module)


def _context(
    permissions: frozenset[str] = frozenset({INVENTORY_ALLOCATE}),
) -> OrganizationContext:
    return OrganizationContext(
        organization_id=OrganizationId.new(),
        authenticated_principal=AuthenticatedPrincipal(
            issuer="https://issuer.example.test",
            subject="inventory-allocate-test-user",
            principal_type=PrincipalType.USER,
            authenticated_at=NOW,
            client_id="inventory-allocate-test",
            technical_scopes=frozenset({"openid"}),
        ),
        user_id=TypedId.new("user"),
        actor_id=TypedId.new("actor"),
        membership_id=TypedId.new("membership"),
        role_ids=(TypedId.new("role"),),
        permission_codes=permissions,
        validated_at=NOW,
    )


class _Request(Protocol):
    operation: str


class _Idempotency:
    def execute(
        self, request: _Request, handler: Callable[[], CanonicalPayload]
    ) -> IdempotencyExecution:
        assert request.operation == "asset.inventory.allocate_reservation"
        payload = handler()
        return IdempotencyExecution(payload.schema, payload.version, payload.canonical_bytes, False)


class _Service:
    def __init__(self, organization_id: OrganizationId, *, conflict: bool = False) -> None:
        self.organization_id = organization_id
        self.conflict = conflict

    def allocate_reservation(
        self,
        context: AssetOperationContext,
        reservation_id: TypedId,
        *,
        occurred_at: datetime,
        expected_version: int | None = None,
    ) -> StockReservation:
        del occurred_at
        if self.conflict:
            raise OptimisticConcurrencyConflict()
        assert context.organization_id == self.organization_id
        assert reservation_id.value.hex == RESERVATION_ID.replace("-", "")
        assert expected_version == 1
        return StockReservation(
            reservation_id=reservation_id,
            organization_id=self.organization_id,
            stock_position_ref=TypedId.parse("stock_position", POSITION_ID),
            demand=DemandRef(
                kind=DemandKind.WORK_ORDER,
                ref=TypedId.parse("work_order", WORK_ORDER_ID),
            ),
            qty=Decimal("2"),
            purpose=StockPurpose.SERVICE_SLI,
            priority=10,
            state=ReservationState.ALLOCATED,
            version=2,
        )


def _override(context: OrganizationContext, service: _Service | None = None) -> None:
    main_module.app.dependency_overrides[asset_commands.require_inventory_allocate] = lambda: (
        context
    )
    main_module.app.dependency_overrides[asset_commands.get_inventory_service] = lambda: (
        service or _Service(context.organization_id)
    )
    main_module.app.dependency_overrides[asset_commands.get_idempotency_service] = _Idempotency


def test_route_is_registered() -> None:
    assert (
        "/v1/asset/stock-reservations/{reservation_id}/allocate"
        in main_module.app.openapi()["paths"]
    )


def test_allocate_reservation_requires_authentication() -> None:
    response = TestClient(main_module.app).post(
        ROUTE,
        json={"expected_version": 1},
        headers={"Idempotency-Key": "inventory-allocate-auth"},
    )
    assert response.status_code == 401


def test_allocate_reservation_rejects_missing_permission(monkeypatch: MonkeyPatch) -> None:
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
        json={"expected_version": 1},
        headers={
            ORGANIZATION_HEADER: str(context.organization_id.value),
            "Idempotency-Key": "inventory-allocate-permission",
        },
    )
    assert response.status_code == 403
    assert response.json()["reason_code"] == "PERMISSAO_AUSENTE"


def test_allocate_reservation_returns_allocated_state() -> None:
    context = _context()
    _override(context)
    response = TestClient(main_module.app).post(
        ROUTE,
        json={"expected_version": 1},
        headers={"Idempotency-Key": "inventory-allocate-success"},
    )
    assert response.status_code == 200
    assert response.json()["state"] == "ALLOCATED"
    assert response.json()["version"] == 2
    assert Decimal(response.json()["qty"]) == Decimal("2")


def test_allocate_reservation_requires_expected_version() -> None:
    context = _context()
    _override(context)
    response = TestClient(main_module.app).post(
        ROUTE,
        json={},
        headers={"Idempotency-Key": "inventory-allocate-version-required"},
    )
    assert response.status_code == 422


def test_allocate_reservation_translates_version_conflict() -> None:
    context = _context()
    _override(context, _Service(context.organization_id, conflict=True))
    response = TestClient(main_module.app).post(
        ROUTE,
        json={"expected_version": 1},
        headers={"Idempotency-Key": "inventory-allocate-version"},
    )
    assert response.status_code == 409
    assert response.json()["reason_code"] == OptimisticConcurrencyConflict.code
