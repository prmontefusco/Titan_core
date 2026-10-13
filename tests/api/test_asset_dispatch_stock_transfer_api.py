"""Contrato HTTP de `DispatchStockTransfer` — Titan Asset A5."""

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
from packages.asset_application.authorization import INVENTORY_TRANSFER_DISPATCH
from packages.asset_application.event_recorder import AssetOperationContext
from packages.asset_domain.inventory import (
    StockOwnership,
    StockPosition,
    StockPurpose,
    StockQuantities,
    StockTransfer,
    TransferState,
)
from packages.core_application import IdempotencyExecution
from packages.core_domain import AuthenticatedPrincipal, CanonicalPayload, OrganizationContext
from packages.core_domain.organization_context import PrincipalType
from packages.shared_kernel import OrganizationId, TypedId

TRANSFER_ID = "00000000-0000-0000-0000-000000001704"
PART_ID = "00000000-0000-0000-0000-000000001701"
FROM_LOCATION_ID = "00000000-0000-0000-0000-000000001702"
TO_LOCATION_ID = "00000000-0000-0000-0000-000000001703"
ROUTE = f"/v1/asset/stock-transfers/{TRANSFER_ID}/dispatch"
NOW = datetime(2026, 10, 13, 16, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _restore_app() -> Iterator[None]:
    yield
    main_module.app.dependency_overrides.clear()
    importlib.reload(main_module)


def _context(permissions: frozenset[str]) -> OrganizationContext:
    return OrganizationContext(
        organization_id=OrganizationId.new(),
        authenticated_principal=AuthenticatedPrincipal(
            issuer="https://issuer.example.test",
            subject="dispatch-transfer-test-user",
            principal_type=PrincipalType.USER,
            authenticated_at=NOW,
            client_id="dispatch-transfer-test",
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
        assert request.operation == "asset.inventory.dispatch_transfer"
        payload = handler()
        return IdempotencyExecution(payload.schema, payload.version, payload.canonical_bytes, False)


class _Service:
    def __init__(self, organization_id: OrganizationId) -> None:
        self.organization_id = organization_id

    def dispatch_transfer(
        self,
        context: AssetOperationContext,
        transfer_id: TypedId,
        *,
        occurred_at: datetime,
        expected_version: int | None = None,
    ) -> tuple[StockPosition, StockTransfer]:
        del occurred_at
        assert context.organization_id == self.organization_id
        assert str(transfer_id.value) == TRANSFER_ID
        assert expected_version == 1
        part_ref = TypedId.parse("part", PART_ID)
        from_ref = TypedId.parse("stock_location", FROM_LOCATION_ID)
        return (
            StockPosition(
                stock_position_id=TypedId.new("stock_position"),
                organization_id=self.organization_id,
                part_ref=part_ref,
                location_ref=from_ref,
                purpose=StockPurpose.SERVICE_SLI,
                ownership=StockOwnership.COMPANY_OWNED,
                quantities=StockQuantities(on_hand=Decimal("7")),
                version=2,
            ),
            StockTransfer(
                transfer_id=transfer_id,
                organization_id=self.organization_id,
                part_ref=part_ref,
                purpose=StockPurpose.SERVICE_SLI,
                from_location_ref=from_ref,
                to_location_ref=TypedId.parse("stock_location", TO_LOCATION_ID),
                qty=Decimal("3"),
                state=TransferState.IN_TRANSIT,
                version=2,
            ),
        )


def _override(context: OrganizationContext) -> None:
    main_module.app.dependency_overrides[asset_commands.require_inventory_transfer_dispatch] = (
        lambda: context
    )
    main_module.app.dependency_overrides[asset_commands.get_inventory_service] = lambda: _Service(
        context.organization_id
    )
    main_module.app.dependency_overrides[asset_commands.get_idempotency_service] = _Idempotency


def test_dispatch_transfer_requires_authentication() -> None:
    response = TestClient(main_module.app).post(
        ROUTE, json={"expected_version": 1}, headers={"Idempotency-Key": "dispatch-auth"}
    )
    assert response.status_code == 401


def test_dispatch_transfer_rejects_missing_permission(monkeypatch: MonkeyPatch) -> None:
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
            "Idempotency-Key": "dispatch-permission",
        },
    )
    assert response.status_code == 403
    assert response.json()["reason_code"] == "PERMISSAO_AUSENTE"


def test_dispatch_transfer_returns_in_transit_and_updated_source() -> None:
    context = _context(frozenset({INVENTORY_TRANSFER_DISPATCH}))
    _override(context)
    response = TestClient(main_module.app).post(
        ROUTE, json={"expected_version": 1}, headers={"Idempotency-Key": "dispatch-success"}
    )
    assert response.status_code == 200
    assert response.json()["transfer"]["state"] == "IN_TRANSIT"
    assert Decimal(response.json()["source_stock_position"]["on_hand"]) == Decimal("7")


def test_dispatch_transfer_rejects_invalid_expected_version() -> None:
    context = _context(frozenset({INVENTORY_TRANSFER_DISPATCH}))
    _override(context)
    response = TestClient(main_module.app).post(
        ROUTE, json={"expected_version": 0}, headers={"Idempotency-Key": "dispatch-version"}
    )
    assert response.status_code == 422
