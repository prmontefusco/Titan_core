"""Contrato HTTP de `OpenStockPosition` — Titan Asset A5."""

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
from packages.asset_application.authorization import INVENTORY_OPEN_POSITION
from packages.asset_application.event_recorder import AssetOperationContext
from packages.asset_domain.inventory import (
    StockOwnership,
    StockPosition,
    StockPurpose,
    StockQuantities,
)
from packages.core_application import IdempotencyExecution
from packages.core_domain import AuthenticatedPrincipal, CanonicalPayload, OrganizationContext
from packages.core_domain.organization_context import PrincipalType
from packages.shared_kernel import OrganizationId, TypedId

ROUTE = "/v1/asset/stock-positions"
PART_ID = "00000000-0000-0000-0000-000000001101"
LOCATION_ID = "00000000-0000-0000-0000-000000001102"
NOW = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _restore_app() -> Iterator[None]:
    yield
    main_module.app.dependency_overrides.clear()
    importlib.reload(main_module)


def _context(
    permissions: frozenset[str] = frozenset({INVENTORY_OPEN_POSITION}),
) -> OrganizationContext:
    return OrganizationContext(
        organization_id=OrganizationId.new(),
        authenticated_principal=AuthenticatedPrincipal(
            issuer="https://issuer.example.test",
            subject="inventory-test-user",
            principal_type=PrincipalType.USER,
            authenticated_at=NOW,
            client_id="inventory-test",
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
        "part_id": PART_ID,
        "location_id": LOCATION_ID,
        "purpose": "SERVICE_SLI",
        "ownership": "COMPANY_OWNED",
        "on_hand": "10",
        "quarantine": "2",
        "lot": "LOT-FICTICIO",
    }
    body.update(overrides)
    return body


class _Request(Protocol):
    operation: str


class _Idempotency:
    def execute(
        self, request: _Request, handler: Callable[[], CanonicalPayload]
    ) -> IdempotencyExecution:
        payload = handler()
        return IdempotencyExecution(payload.schema, payload.version, payload.canonical_bytes, False)


class _Service:
    def open_stock_position(
        self,
        context: AssetOperationContext,
        *,
        part_ref: TypedId,
        location_ref: TypedId,
        purpose: StockPurpose,
        ownership: StockOwnership,
        quantities: StockQuantities | None,
        lot: str | None,
        serial: str | None,
        occurred_at: datetime,
    ) -> StockPosition:
        del occurred_at
        assert quantities is not None
        return StockPosition(
            stock_position_id=TypedId.parse(
                "stock_position", "00000000-0000-0000-0000-000000001103"
            ),
            organization_id=context.organization_id,
            part_ref=part_ref,
            location_ref=location_ref,
            purpose=purpose,
            ownership=ownership,
            quantities=quantities,
            lot=lot,
            serial=serial,
        )


def _override(context: OrganizationContext) -> None:
    main_module.app.dependency_overrides[asset_commands.require_inventory_open_position] = lambda: (
        context
    )
    main_module.app.dependency_overrides[asset_commands.get_inventory_service] = _Service
    main_module.app.dependency_overrides[asset_commands.get_idempotency_service] = _Idempotency


def test_route_is_registered() -> None:
    assert ROUTE in main_module.app.openapi()["paths"]


def test_open_stock_position_requires_authentication() -> None:
    response = TestClient(main_module.app).post(
        ROUTE, json=_body(), headers={"Idempotency-Key": "inventory-auth"}
    )
    assert response.status_code == 401


def test_open_stock_position_rejects_missing_permission(monkeypatch: MonkeyPatch) -> None:
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
            "Idempotency-Key": "inventory-permission",
        },
    )
    assert response.status_code == 403
    assert response.json()["reason_code"] == "PERMISSAO_AUSENTE"


def test_open_stock_position_returns_breakdown() -> None:
    context = _context()
    _override(context)
    response = TestClient(main_module.app).post(
        ROUTE, json=_body(), headers={"Idempotency-Key": "inventory-success"}
    )
    assert response.status_code == 201
    assert response.json()["part_ref"] == PART_ID
    assert response.json()["location_ref"] == LOCATION_ID
    assert Decimal(response.json()["on_hand"]) == Decimal("10")
    assert Decimal(response.json()["quarantine"]) == Decimal("2")
    assert Decimal(response.json()["available"]) == Decimal("8")
    assert response.json()["version"] == 1


def test_open_stock_position_rejects_negative_bucket() -> None:
    context = _context()
    _override(context)
    response = TestClient(main_module.app).post(
        ROUTE,
        json=_body(damaged="-1"),
        headers={"Idempotency-Key": "inventory-negative"},
    )
    assert response.status_code == 422
