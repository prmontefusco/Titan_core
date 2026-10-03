"""Contrato HTTP de `GetAvailability` — Titan Asset A5."""

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
from packages.asset_application.authorization import INVENTORY_READ
from packages.asset_application.availability_query import AvailabilityResult
from packages.asset_domain.inventory import AvailabilityBreakdown, StockPurpose
from packages.core_domain import AuthenticatedPrincipal, OrganizationContext, PrincipalType
from packages.shared_kernel import OrganizationId, TypedId

PART_ID = "00000000-0000-0000-0000-000000000811"
LOCATION_ID = "00000000-0000-0000-0000-000000000821"
POSITION_ID = "00000000-0000-0000-0000-000000000831"
ROUTE = "/v1/asset/availability"
OCCURRED_AT = datetime(2026, 10, 3, 12, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _restore_default_app() -> Iterator[None]:
    yield
    main_module.app.dependency_overrides.clear()
    importlib.reload(main_module)


def _context(permissions: frozenset[str] = frozenset({INVENTORY_READ})) -> OrganizationContext:
    return OrganizationContext(
        organization_id=OrganizationId.new(),
        authenticated_principal=AuthenticatedPrincipal(
            issuer="https://issuer.example.test",
            subject="asset-availability-test-user",
            principal_type=PrincipalType.USER,
            authenticated_at=OCCURRED_AT,
            client_id="asset-availability-test",
            technical_scopes=frozenset({"openid"}),
        ),
        user_id=TypedId.new("user"),
        actor_id=TypedId.new("actor"),
        membership_id=TypedId.new("membership"),
        role_ids=(TypedId.new("role"),),
        permission_codes=permissions,
        validated_at=OCCURRED_AT,
    )


class _FakeAvailabilityQueryService:
    seen_part_ref: TypedId | None = None
    seen_location_ref: TypedId | None = None
    seen_purpose: StockPurpose | None = None

    def get_availability(
        self,
        *,
        part_ref: TypedId,
        location_ref: TypedId,
        purpose: StockPurpose,
    ) -> AvailabilityResult:
        self.seen_part_ref = part_ref
        self.seen_location_ref = location_ref
        self.seen_purpose = purpose
        return AvailabilityResult(
            part_ref=part_ref,
            location_ref=location_ref,
            purpose=purpose,
            breakdown=AvailabilityBreakdown(
                on_hand=Decimal("10"),
                reserved=Decimal("2"),
                quarantine=Decimal("1"),
                inspection=Decimal("0.5"),
                damaged=Decimal("0.5"),
            ),
            stock_position_refs=(TypedId.parse("stock_position", POSITION_ID),),
        )


def _fake_connection() -> object:
    return SimpleNamespace()


def _params(
    *,
    part_id: str = PART_ID,
    location_id: str = LOCATION_ID,
    purpose: str = "SERVICE_SLI",
) -> dict[str, str]:
    return {"part_id": part_id, "location_id": location_id, "purpose": purpose}


def test_availability_route_is_registered_in_openapi() -> None:
    paths = set(main_module.app.openapi()["paths"])

    assert "/v1/asset/availability" in paths


def test_availability_requires_authentication() -> None:
    response = TestClient(main_module.app).get(ROUTE, params=_params())

    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")


def test_availability_rejects_missing_permission(monkeypatch: MonkeyPatch) -> None:
    contexto = _context(permissions=frozenset())
    main_module.app.dependency_overrides[require_authenticated_principal] = lambda: (
        contexto.authenticated_principal
    )
    main_module.app.dependency_overrides[request_connection] = _fake_connection
    main_module.app.dependency_overrides[asset_queries.get_availability_query_service] = (
        _FakeAvailabilityQueryService
    )

    monkeypatch.setattr(
        "apps.api.livestock_dependencies.resolve_organization_context",
        lambda *_args, **_kwargs: contexto,
    )

    response = TestClient(main_module.app).get(
        ROUTE,
        params=_params(),
        headers={ORGANIZATION_HEADER: str(contexto.organization_id.value)},
    )

    assert response.status_code == 403
    assert response.json()["reason_code"] == "PERMISSAO_AUSENTE"


def test_availability_returns_explainable_breakdown() -> None:
    contexto = _context()
    service = _FakeAvailabilityQueryService()
    main_module.app.dependency_overrides[asset_queries.require_inventory_read] = lambda: contexto
    main_module.app.dependency_overrides[asset_queries.get_availability_query_service] = lambda: (
        service
    )

    response = TestClient(main_module.app).get(ROUTE, params=_params())

    assert response.status_code == 200
    assert service.seen_part_ref == TypedId.parse("part", PART_ID)
    assert service.seen_location_ref == TypedId.parse("stock_location", LOCATION_ID)
    assert service.seen_purpose is StockPurpose.SERVICE_SLI
    assert response.json() == {
        "part_ref": PART_ID,
        "location_ref": LOCATION_ID,
        "purpose": "SERVICE_SLI",
        "breakdown": {
            "on_hand": "10",
            "reserved": "2",
            "quarantine": "1",
            "inspection": "0.5",
            "damaged": "0.5",
            "available": "6.0",
        },
        "stock_position_refs": [POSITION_ID],
    }


def test_availability_rejects_invalid_part_identifier() -> None:
    contexto = _context()
    main_module.app.dependency_overrides[asset_queries.require_inventory_read] = lambda: contexto
    main_module.app.dependency_overrides[asset_queries.get_availability_query_service] = (
        _FakeAvailabilityQueryService
    )

    response = TestClient(main_module.app).get(ROUTE, params=_params(part_id="nao-e-uuid"))

    assert response.status_code == 422
    assert response.json()["reason_code"] == "IDENTIFICADOR_INVALIDO"


def test_availability_rejects_invalid_purpose() -> None:
    contexto = _context()
    main_module.app.dependency_overrides[asset_queries.require_inventory_read] = lambda: contexto
    main_module.app.dependency_overrides[asset_queries.get_availability_query_service] = (
        _FakeAvailabilityQueryService
    )

    response = TestClient(main_module.app).get(ROUTE, params=_params(purpose="INVALIDO"))

    assert response.status_code == 422
    assert response.json()["reason_code"] == "VALOR_INVALIDO"
