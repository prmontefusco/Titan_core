"""Contrato HTTP de `GetFleetView` — Titan Asset A5."""

import importlib
from collections.abc import Iterator
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pytest import MonkeyPatch

import apps.api.main as main_module
from apps.api.asset import queries as asset_queries
from apps.api.authentication import require_authenticated_principal
from apps.api.livestock_dependencies import ORGANIZATION_HEADER, request_connection
from packages.asset_application.authorization import VEHICLE_READ
from packages.asset_application.fleet_view import (
    FleetOperationalState,
    FleetView,
    FleetViewLine,
)
from packages.asset_domain.vehicle import VehicleLifecycleState
from packages.core_domain import AuthenticatedPrincipal, OrganizationContext, PrincipalType
from packages.shared_kernel import OrganizationId, TypedId

SITE_ID = "00000000-0000-0000-0000-000000000101"
ROUTE = "/v1/asset/fleet-view"


@pytest.fixture(autouse=True)
def _restore_default_app() -> Iterator[None]:
    yield
    main_module.app.dependency_overrides.clear()
    importlib.reload(main_module)


def _context(permissions: frozenset[str] = frozenset({VEHICLE_READ})) -> OrganizationContext:
    now = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)
    return OrganizationContext(
        organization_id=OrganizationId.new(),
        authenticated_principal=AuthenticatedPrincipal(
            issuer="https://issuer.example.test",
            subject="asset-fleet-view-test-user",
            principal_type=PrincipalType.USER,
            authenticated_at=now,
            client_id="asset-fleet-view-test",
            technical_scopes=frozenset({"openid"}),
        ),
        user_id=TypedId.new("user"),
        actor_id=TypedId.new("actor"),
        membership_id=TypedId.new("membership"),
        role_ids=(TypedId.new("role"),),
        permission_codes=permissions,
        validated_at=now,
    )


class _FakeFleetViewService:
    seen_site_ref: TypedId | None = None

    def get_fleet_view(self, *, site_ref: TypedId | None = None) -> FleetView:
        self.seen_site_ref = site_ref
        line = FleetViewLine(
            vehicle_id=TypedId.parse("vehicle", "00000000-0000-0000-0000-000000000401"),
            site_ref=site_ref,
            lifecycle_state=VehicleLifecycleState.DEGRADED,
            operational_state=FleetOperationalState.SLA_RISK,
            open_work_order_refs=(
                TypedId.parse("work_order", "00000000-0000-0000-0000-000000000301"),
            ),
            signals=("VEHICLE:DEGRADED", "WORK_ORDER:SLA_RISK", "OPERATIONAL:SLA_RISK"),
        )
        return FleetView(
            site_ref=site_ref,
            lines=(line,),
            counts_by_state={
                FleetOperationalState.AVAILABLE: 0,
                FleetOperationalState.DEGRADED: 0,
                FleetOperationalState.MAINTENANCE: 0,
                FleetOperationalState.WAITING_MATERIAL: 0,
                FleetOperationalState.SLA_RISK: 1,
                FleetOperationalState.UNAVAILABLE: 0,
            },
        )


def _fake_connection() -> object:
    return SimpleNamespace()


def test_fleet_view_route_is_registered_in_openapi() -> None:
    paths = set(main_module.app.openapi()["paths"])

    assert "/v1/asset/fleet-view" in paths


def test_fleet_view_requires_authentication() -> None:
    response = TestClient(main_module.app).get(ROUTE)

    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")


def test_fleet_view_rejects_missing_permission(monkeypatch: MonkeyPatch) -> None:
    contexto = _context(permissions=frozenset())
    main_module.app.dependency_overrides[require_authenticated_principal] = lambda: (
        contexto.authenticated_principal
    )
    main_module.app.dependency_overrides[request_connection] = _fake_connection
    main_module.app.dependency_overrides[asset_queries.get_fleet_view_service] = (
        _FakeFleetViewService
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


def test_fleet_view_returns_lines_counts_and_passes_site_filter() -> None:
    contexto = _context()
    service = _FakeFleetViewService()
    main_module.app.dependency_overrides[asset_queries.require_vehicle_read] = lambda: contexto
    main_module.app.dependency_overrides[asset_queries.get_fleet_view_service] = lambda: service

    response = TestClient(main_module.app).get(ROUTE, params={"site_id": SITE_ID})

    assert response.status_code == 200
    assert service.seen_site_ref == TypedId.parse("customer_site", SITE_ID)
    payload = response.json()
    assert payload["site_ref"] == SITE_ID
    assert payload["counts_by_state"]["SLA_RISK"] == 1
    assert payload["lines"][0] == {
        "vehicle_id": "00000000-0000-0000-0000-000000000401",
        "site_ref": SITE_ID,
        "lifecycle_state": "DEGRADED",
        "operational_state": "SLA_RISK",
        "open_work_order_refs": ["00000000-0000-0000-0000-000000000301"],
        "signals": ["VEHICLE:DEGRADED", "WORK_ORDER:SLA_RISK", "OPERATIONAL:SLA_RISK"],
    }


def test_fleet_view_accepts_unfiltered_query() -> None:
    contexto = _context()
    service = _FakeFleetViewService()
    main_module.app.dependency_overrides[asset_queries.require_vehicle_read] = lambda: contexto
    main_module.app.dependency_overrides[asset_queries.get_fleet_view_service] = lambda: service

    response = TestClient(main_module.app).get(ROUTE)

    assert response.status_code == 200
    assert service.seen_site_ref is None
    assert response.json()["site_ref"] is None


def test_fleet_view_rejects_invalid_site_identifier() -> None:
    contexto = _context()
    main_module.app.dependency_overrides[asset_queries.require_vehicle_read] = lambda: contexto
    main_module.app.dependency_overrides[asset_queries.get_fleet_view_service] = (
        _FakeFleetViewService
    )

    response = TestClient(main_module.app).get(ROUTE, params={"site_id": "nao-e-uuid"})

    assert response.status_code == 422
    assert response.json()["reason_code"] == "IDENTIFICADOR_INVALIDO"
