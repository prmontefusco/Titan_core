"""Contrato HTTP de `ReleaseStockReservation` — Titan Asset A5."""

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
from packages.asset_application.authorization import INVENTORY_RELEASE
from packages.asset_application.event_recorder import AssetOperationContext
from packages.asset_domain.inventory import (
    DemandKind,
    DemandRef,
    ReservationState,
    StockOwnership,
    StockPosition,
    StockPurpose,
    StockQuantities,
    StockReservation,
)
from packages.core_application import IdempotencyExecution, OptimisticConcurrencyConflict
from packages.core_domain import AuthenticatedPrincipal, CanonicalPayload, OrganizationContext
from packages.core_domain.organization_context import PrincipalType
from packages.shared_kernel import OrganizationId, TypedId

RESERVATION_ID = "00000000-0000-0000-0000-000000001401"
POSITION_ID = "00000000-0000-0000-0000-000000001402"
WORK_ORDER_ID = "00000000-0000-0000-0000-000000001403"
PART_ID = "00000000-0000-0000-0000-000000001404"
LOCATION_ID = "00000000-0000-0000-0000-000000001405"
ROUTE = f"/v1/asset/stock-reservations/{RESERVATION_ID}/release"
NOW = datetime(2026, 10, 13, 12, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _restore_app() -> Iterator[None]:
    yield
    main_module.app.dependency_overrides.clear()
    importlib.reload(main_module)


def _context(
    permissions: frozenset[str] = frozenset({INVENTORY_RELEASE}),
) -> OrganizationContext:
    return OrganizationContext(
        organization_id=OrganizationId.new(),
        authenticated_principal=AuthenticatedPrincipal(
            issuer="https://issuer.example.test",
            subject="inventory-release-test-user",
            principal_type=PrincipalType.USER,
            authenticated_at=NOW,
            client_id="inventory-release-test",
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
        "expected_version": 1,
        "reason": "Demanda cancelada durante validação fictícia.",
    }
    body.update(overrides)
    return body


class _Request(Protocol):
    operation: str


class _Idempotency:
    def execute(
        self, request: _Request, handler: Callable[[], CanonicalPayload]
    ) -> IdempotencyExecution:
        assert request.operation == "asset.inventory.release_reservation"
        payload = handler()
        return IdempotencyExecution(payload.schema, payload.version, payload.canonical_bytes, False)


class _Service:
    def __init__(self, organization_id: OrganizationId, *, conflict: bool = False) -> None:
        self.organization_id = organization_id
        self.conflict = conflict

    def release_reservation(
        self,
        context: AssetOperationContext,
        reservation_id: TypedId,
        *,
        reason: str,
        occurred_at: datetime,
        expected_version: int | None = None,
    ) -> tuple[StockPosition, StockReservation]:
        del occurred_at
        if self.conflict:
            raise OptimisticConcurrencyConflict()
        assert context.organization_id == self.organization_id
        assert reservation_id.value.hex == RESERVATION_ID.replace("-", "")
        assert reason == "Demanda cancelada durante validação fictícia."
        assert expected_version == 1
        position_id = TypedId.parse("stock_position", POSITION_ID)
        reservation = StockReservation(
            reservation_id=reservation_id,
            organization_id=self.organization_id,
            stock_position_ref=position_id,
            demand=DemandRef(
                kind=DemandKind.WORK_ORDER,
                ref=TypedId.parse("work_order", WORK_ORDER_ID),
            ),
            qty=Decimal("4"),
            purpose=StockPurpose.SERVICE_SLI,
            priority=10,
            state=ReservationState.RELEASED,
            version=2,
        )
        position = StockPosition(
            stock_position_id=position_id,
            organization_id=self.organization_id,
            part_ref=TypedId.parse("part", PART_ID),
            location_ref=TypedId.parse("stock_location", LOCATION_ID),
            purpose=StockPurpose.SERVICE_SLI,
            ownership=StockOwnership.COMPANY_OWNED,
            quantities=StockQuantities(on_hand=Decimal("10")),
            version=3,
        )
        return position, reservation


def _override(context: OrganizationContext, service: _Service | None = None) -> None:
    main_module.app.dependency_overrides[asset_commands.require_inventory_release] = lambda: context
    main_module.app.dependency_overrides[asset_commands.get_inventory_service] = lambda: (
        service or _Service(context.organization_id)
    )
    main_module.app.dependency_overrides[asset_commands.get_idempotency_service] = _Idempotency


def test_route_is_registered() -> None:
    assert (
        "/v1/asset/stock-reservations/{reservation_id}/release"
        in main_module.app.openapi()["paths"]
    )


def test_release_reservation_requires_authentication() -> None:
    response = TestClient(main_module.app).post(
        ROUTE, json=_body(), headers={"Idempotency-Key": "inventory-release-auth"}
    )
    assert response.status_code == 401


def test_release_reservation_rejects_missing_permission(monkeypatch: MonkeyPatch) -> None:
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
            "Idempotency-Key": "inventory-release-permission",
        },
    )
    assert response.status_code == 403
    assert response.json()["reason_code"] == "PERMISSAO_AUSENTE"


def test_release_reservation_returns_reservation_and_position() -> None:
    context = _context()
    _override(context)
    response = TestClient(main_module.app).post(
        ROUTE, json=_body(), headers={"Idempotency-Key": "inventory-release-success"}
    )
    assert response.status_code == 200
    assert response.json()["reservation"]["state"] == "RELEASED"
    assert response.json()["reservation"]["version"] == 2
    assert Decimal(response.json()["stock_position"]["available"]) == Decimal("10")


def test_release_reservation_rejects_blank_reason() -> None:
    context = _context()
    _override(context)
    response = TestClient(main_module.app).post(
        ROUTE,
        json=_body(reason=""),
        headers={"Idempotency-Key": "inventory-release-reason"},
    )
    assert response.status_code == 422


def test_release_reservation_translates_version_conflict() -> None:
    context = _context()
    _override(context, _Service(context.organization_id, conflict=True))
    response = TestClient(main_module.app).post(
        ROUTE, json=_body(), headers={"Idempotency-Key": "inventory-release-version"}
    )
    assert response.status_code == 409
    assert response.json()["reason_code"] == OptimisticConcurrencyConflict.code
