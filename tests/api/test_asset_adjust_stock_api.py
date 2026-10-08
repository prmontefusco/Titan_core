"""Contrato HTTP de `AdjustStock` — Titan Asset A5."""

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
from packages.asset_application.authorization import INVENTORY_ADJUST
from packages.asset_application.event_recorder import AssetOperationContext
from packages.asset_domain.inventory import (
    StockOwnership,
    StockPosition,
    StockPurpose,
    StockQuantities,
)
from packages.core_application import IdempotencyExecution, OptimisticConcurrencyConflict
from packages.core_domain import AuthenticatedPrincipal, CanonicalPayload, OrganizationContext
from packages.core_domain.organization_context import PrincipalType
from packages.shared_kernel import OrganizationId, TypedId

POSITION_ID = "00000000-0000-0000-0000-000000001201"
PART_ID = "00000000-0000-0000-0000-000000001202"
LOCATION_ID = "00000000-0000-0000-0000-000000001203"
ROUTE = f"/v1/asset/stock-positions/{POSITION_ID}/adjustments"
NOW = datetime(2026, 10, 8, 14, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _restore_app() -> Iterator[None]:
    yield
    main_module.app.dependency_overrides.clear()
    importlib.reload(main_module)


def _context(permissions: frozenset[str] = frozenset({INVENTORY_ADJUST})) -> OrganizationContext:
    return OrganizationContext(
        organization_id=OrganizationId.new(),
        authenticated_principal=AuthenticatedPrincipal(
            issuer="https://issuer.example.test",
            subject="inventory-adjust-test-user",
            principal_type=PrincipalType.USER,
            authenticated_at=NOW,
            client_id="inventory-adjust-test",
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
        "delta_by_status": {"on_hand": "3", "quarantine": "2"},
        "reason": "Contagem física fictícia.",
    }
    body.update(overrides)
    return body


class _Request(Protocol):
    operation: str


class _Idempotency:
    def execute(
        self, request: _Request, handler: Callable[[], CanonicalPayload]
    ) -> IdempotencyExecution:
        assert request.operation == "asset.inventory.adjust"
        payload = handler()
        return IdempotencyExecution(payload.schema, payload.version, payload.canonical_bytes, False)


class _Service:
    def __init__(self, *, conflict: bool = False) -> None:
        self.conflict = conflict

    def adjust_stock(
        self,
        context: AssetOperationContext,
        stock_position_id: TypedId,
        *,
        deltas: dict[str, Decimal],
        reason: str,
        actor_ref: TypedId,
        occurred_at: datetime,
        expected_version: int | None = None,
    ) -> StockPosition:
        del occurred_at
        if self.conflict:
            raise OptimisticConcurrencyConflict()
        assert stock_position_id.value.hex == POSITION_ID.replace("-", "")
        assert deltas == {"on_hand": Decimal("3"), "quarantine": Decimal("2")}
        assert reason == "Contagem física fictícia."
        assert actor_ref.entity_type == "actor"
        assert expected_version == 1
        return StockPosition(
            stock_position_id=stock_position_id,
            organization_id=context.organization_id,
            part_ref=TypedId.parse("part", PART_ID),
            location_ref=TypedId.parse("stock_location", LOCATION_ID),
            purpose=StockPurpose.SERVICE_SLI,
            ownership=StockOwnership.COMPANY_OWNED,
            quantities=StockQuantities(on_hand=Decimal("13"), quarantine=Decimal("2")),
            version=2,
        )


def _override(context: OrganizationContext, service: _Service | None = None) -> None:
    main_module.app.dependency_overrides[asset_commands.require_inventory_adjust] = lambda: context
    main_module.app.dependency_overrides[asset_commands.get_inventory_service] = lambda: (
        service or _Service()
    )
    main_module.app.dependency_overrides[asset_commands.get_idempotency_service] = _Idempotency


def test_route_is_registered() -> None:
    assert (
        "/v1/asset/stock-positions/{stock_position_id}/adjustments"
        in main_module.app.openapi()["paths"]
    )


def test_adjust_stock_requires_authentication() -> None:
    response = TestClient(main_module.app).post(
        ROUTE, json=_body(), headers={"Idempotency-Key": "inventory-adjust-auth"}
    )
    assert response.status_code == 401


def test_adjust_stock_rejects_missing_permission(monkeypatch: MonkeyPatch) -> None:
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
            "Idempotency-Key": "inventory-adjust-permission",
        },
    )
    assert response.status_code == 403
    assert response.json()["reason_code"] == "PERMISSAO_AUSENTE"


def test_adjust_stock_returns_updated_breakdown() -> None:
    context = _context()
    _override(context)
    response = TestClient(main_module.app).post(
        ROUTE, json=_body(), headers={"Idempotency-Key": "inventory-adjust-success"}
    )
    assert response.status_code == 200
    assert Decimal(response.json()["on_hand"]) == Decimal("13")
    assert Decimal(response.json()["quarantine"]) == Decimal("2")
    assert Decimal(response.json()["available"]) == Decimal("11")
    assert response.json()["version"] == 2


@pytest.mark.parametrize(
    "delta_by_status",
    [{}, {"reserved": "1"}],
)
def test_adjust_stock_rejects_empty_or_unknown_bucket(
    delta_by_status: dict[str, str],
) -> None:
    context = _context()
    _override(context)
    response = TestClient(main_module.app).post(
        ROUTE,
        json=_body(delta_by_status=delta_by_status),
        headers={"Idempotency-Key": "inventory-adjust-invalid-bucket"},
    )
    assert response.status_code == 422


def test_adjust_stock_translates_version_conflict() -> None:
    context = _context()
    _override(context, _Service(conflict=True))
    response = TestClient(main_module.app).post(
        ROUTE, json=_body(), headers={"Idempotency-Key": "inventory-adjust-version"}
    )
    assert response.status_code == 409
    assert response.json()["reason_code"] == OptimisticConcurrencyConflict.code
