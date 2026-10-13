"""Contrato HTTP de `RequestStockTransfer` — Titan Asset A5."""

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
from packages.asset_application.authorization import INVENTORY_TRANSFER_REQUEST
from packages.asset_application.event_recorder import AssetOperationContext
from packages.asset_domain.inventory import StockPurpose, StockTransfer
from packages.core_application import IdempotencyExecution
from packages.core_domain import AuthenticatedPrincipal, CanonicalPayload, OrganizationContext
from packages.core_domain.organization_context import PrincipalType
from packages.shared_kernel import OrganizationId, TypedId

PART_ID = "00000000-0000-0000-0000-000000001701"
FROM_LOCATION_ID = "00000000-0000-0000-0000-000000001702"
TO_LOCATION_ID = "00000000-0000-0000-0000-000000001703"
TRANSFER_ID = "00000000-0000-0000-0000-000000001704"
ROUTE = "/v1/asset/stock-transfers"
NOW = datetime(2026, 10, 13, 16, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _restore_app() -> Iterator[None]:
    yield
    main_module.app.dependency_overrides.clear()
    importlib.reload(main_module)


def _context(
    permissions: frozenset[str] = frozenset({INVENTORY_TRANSFER_REQUEST}),
) -> OrganizationContext:
    return OrganizationContext(
        organization_id=OrganizationId.new(),
        authenticated_principal=AuthenticatedPrincipal(
            issuer="https://issuer.example.test",
            subject="inventory-transfer-test-user",
            principal_type=PrincipalType.USER,
            authenticated_at=NOW,
            client_id="inventory-transfer-test",
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
        assert request.operation == "asset.inventory.request_transfer"
        payload = handler()
        return IdempotencyExecution(payload.schema, payload.version, payload.canonical_bytes, False)


class _Service:
    def __init__(self, organization_id: OrganizationId) -> None:
        self.organization_id = organization_id

    def request_transfer(
        self,
        context: AssetOperationContext,
        *,
        part_ref: TypedId,
        from_location_ref: TypedId,
        to_location_ref: TypedId,
        qty: Decimal,
        purpose: StockPurpose,
        linked_reservation_ref: TypedId | None = None,
        occurred_at: datetime,
    ) -> StockTransfer:
        del occurred_at
        assert context.organization_id == self.organization_id
        assert str(part_ref.value) == PART_ID
        assert qty == Decimal("3")
        assert purpose is StockPurpose.SERVICE_SLI
        assert linked_reservation_ref is None
        return StockTransfer(
            transfer_id=TypedId.parse("stock_transfer", TRANSFER_ID),
            organization_id=self.organization_id,
            part_ref=part_ref,
            purpose=purpose,
            from_location_ref=from_location_ref,
            to_location_ref=to_location_ref,
            qty=qty,
        )


def _body() -> dict[str, object]:
    return {
        "part_id": PART_ID,
        "from_location_id": FROM_LOCATION_ID,
        "to_location_id": TO_LOCATION_ID,
        "purpose": "SERVICE_SLI",
        "qty": "3",
    }


def _override(context: OrganizationContext) -> None:
    main_module.app.dependency_overrides[asset_commands.require_inventory_transfer_request] = (
        lambda: context
    )
    main_module.app.dependency_overrides[asset_commands.get_inventory_service] = lambda: _Service(
        context.organization_id
    )
    main_module.app.dependency_overrides[asset_commands.get_idempotency_service] = _Idempotency


def test_route_is_registered() -> None:
    assert ROUTE in main_module.app.openapi()["paths"]


def test_request_transfer_requires_authentication() -> None:
    response = TestClient(main_module.app).post(
        ROUTE, json=_body(), headers={"Idempotency-Key": "inventory-transfer-auth"}
    )
    assert response.status_code == 401


def test_request_transfer_rejects_missing_permission(monkeypatch: MonkeyPatch) -> None:
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
            "Idempotency-Key": "inventory-transfer-permission",
        },
    )
    assert response.status_code == 403
    assert response.json()["reason_code"] == "PERMISSAO_AUSENTE"


def test_request_transfer_returns_requested_transfer() -> None:
    context = _context()
    _override(context)
    response = TestClient(main_module.app).post(
        ROUTE, json=_body(), headers={"Idempotency-Key": "inventory-transfer-success"}
    )
    assert response.status_code == 201
    assert response.json()["state"] == "REQUESTED"
    assert response.json()["purpose"] == "SERVICE_SLI"
    assert Decimal(response.json()["qty"]) == Decimal("3")


def test_request_transfer_rejects_non_positive_qty() -> None:
    context = _context()
    _override(context)
    body = _body()
    body["qty"] = "0"
    response = TestClient(main_module.app).post(
        ROUTE, json=body, headers={"Idempotency-Key": "inventory-transfer-qty"}
    )
    assert response.status_code == 422
