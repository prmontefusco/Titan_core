"""Contrato HTTP de `GetWorkshopDashboard` — Titan Asset A5."""

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
from packages.asset_application.authorization import DASHBOARD_READ
from packages.asset_application.workshop_dashboard import (
    WorkshopDashboard,
    WorkshopDashboardLine,
)
from packages.asset_domain.work_order import WorkOrderState
from packages.core_domain import AuthenticatedPrincipal, OrganizationContext, PrincipalType
from packages.shared_kernel import OrganizationId, TypedId

SITE_ID = "00000000-0000-0000-0000-000000000101"
WORKSHOP_ID = "00000000-0000-0000-0000-000000000201"
ROUTE = "/v1/asset/workshop-dashboard"


@pytest.fixture(autouse=True)
def _restore_default_app() -> Iterator[None]:
    yield
    main_module.app.dependency_overrides.clear()
    importlib.reload(main_module)


def _context(permissions: frozenset[str] = frozenset({DASHBOARD_READ})) -> OrganizationContext:
    now = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)
    return OrganizationContext(
        organization_id=OrganizationId.new(),
        authenticated_principal=AuthenticatedPrincipal(
            issuer="https://issuer.example.test",
            subject="asset-dashboard-test-user",
            principal_type=PrincipalType.USER,
            authenticated_at=now,
            client_id="asset-dashboard-test",
            technical_scopes=frozenset({"openid"}),
        ),
        user_id=TypedId.new("user"),
        actor_id=TypedId.new("actor"),
        membership_id=TypedId.new("membership"),
        role_ids=(TypedId.new("role"),),
        permission_codes=permissions,
        validated_at=now,
    )


class _FakeWorkshopDashboardService:
    seen_site_ref: TypedId | None = None
    seen_workshop_ref: TypedId | None = None

    def get_dashboard(
        self, *, site_ref: TypedId, workshop_ref: TypedId | None = None
    ) -> WorkshopDashboard:
        self.seen_site_ref = site_ref
        self.seen_workshop_ref = workshop_ref
        line = WorkshopDashboardLine(
            work_order_id=TypedId.parse("work_order", "00000000-0000-0000-0000-000000000301"),
            vehicle_ref=TypedId.parse("vehicle", "00000000-0000-0000-0000-000000000401"),
            site_ref=site_ref,
            workshop_ref=workshop_ref,
            state=WorkOrderState.WAITING_MATERIAL,
            priority_score=85,
            priority_breakdown={"sla": 55, "criticidade": 30},
            priority_evaluation_ref=TypedId.parse(
                "evaluation", "00000000-0000-0000-0000-000000000501"
            ),
            blockers=("MATERIAL_PENDENTE:00000000-0000-0000-0000-000000000601:0/1",),
            next_action="resolver_material",
        )
        return WorkshopDashboard(site_ref=site_ref, workshop_ref=workshop_ref, lines=(line,))


def _fake_connection() -> object:
    return SimpleNamespace()


def test_workshop_dashboard_route_is_registered_in_openapi() -> None:
    paths = set(main_module.app.openapi()["paths"])

    assert "/v1/asset/workshop-dashboard" in paths


def test_workshop_dashboard_requires_authentication() -> None:
    response = TestClient(main_module.app).get(ROUTE, params={"site_id": SITE_ID})

    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")


def test_workshop_dashboard_rejects_missing_permission(monkeypatch: MonkeyPatch) -> None:
    contexto = _context(permissions=frozenset())
    main_module.app.dependency_overrides[require_authenticated_principal] = lambda: (
        contexto.authenticated_principal
    )
    main_module.app.dependency_overrides[request_connection] = _fake_connection
    main_module.app.dependency_overrides[asset_queries.get_workshop_dashboard_service] = (
        _FakeWorkshopDashboardService
    )

    monkeypatch.setattr(
        "apps.api.livestock_dependencies.resolve_organization_context",
        lambda *_args, **_kwargs: contexto,
    )

    response = TestClient(main_module.app).get(
        ROUTE,
        params={"site_id": SITE_ID},
        headers={ORGANIZATION_HEADER: str(contexto.organization_id.value)},
    )

    assert response.status_code == 403
    assert response.json()["reason_code"] == "PERMISSAO_AUSENTE"


def test_workshop_dashboard_returns_lines_and_passes_filters() -> None:
    contexto = _context()
    service = _FakeWorkshopDashboardService()
    main_module.app.dependency_overrides[asset_queries.require_dashboard_read] = lambda: contexto
    main_module.app.dependency_overrides[asset_queries.get_workshop_dashboard_service] = lambda: (
        service
    )

    response = TestClient(main_module.app).get(
        ROUTE,
        params={"site_id": SITE_ID, "workshop_id": WORKSHOP_ID},
    )

    assert response.status_code == 200
    assert service.seen_site_ref == TypedId.parse("customer_site", SITE_ID)
    assert service.seen_workshop_ref == TypedId.parse("workshop", WORKSHOP_ID)
    payload = response.json()
    assert payload["site_ref"] == SITE_ID
    assert payload["workshop_ref"] == WORKSHOP_ID
    assert payload["lines"][0]["state"] == "WAITING_MATERIAL"
    assert payload["lines"][0]["priority_score"] == 85
    assert payload["lines"][0]["priority_breakdown"] == {"sla": 55, "criticidade": 30}
    assert payload["lines"][0]["next_action"] == "resolver_material"


def test_workshop_dashboard_rejects_invalid_identifiers() -> None:
    contexto = _context()
    main_module.app.dependency_overrides[asset_queries.require_dashboard_read] = lambda: contexto
    main_module.app.dependency_overrides[asset_queries.get_workshop_dashboard_service] = (
        _FakeWorkshopDashboardService
    )

    response = TestClient(main_module.app).get(ROUTE, params={"site_id": "nao-e-uuid"})

    assert response.status_code == 422
    assert response.json()["reason_code"] == "IDENTIFICADOR_INVALIDO"
