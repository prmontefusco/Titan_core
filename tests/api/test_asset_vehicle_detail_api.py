"""Contrato HTTP de `GetVehicle` — Titan Asset A5."""

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
from packages.asset_application.authorization import VEHICLE_READ
from packages.asset_application.vehicle_query import VehicleDetailNaoEncontrado
from packages.asset_domain.vehicle import (
    AssetOwnership,
    MeterCorrection,
    MeterKind,
    MeterReading,
    Vehicle,
    VehicleIdentifiers,
    VehicleLifecycleState,
)
from packages.core_domain import AuthenticatedPrincipal, OrganizationContext, PrincipalType
from packages.shared_kernel import OrganizationId, TypedId

VEHICLE_ID = "00000000-0000-0000-0000-000000000401"
ROUTE = f"/v1/asset/vehicles/{VEHICLE_ID}"
OCCURRED_AT = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _restore_default_app() -> Iterator[None]:
    yield
    main_module.app.dependency_overrides.clear()
    importlib.reload(main_module)


def _context(permissions: frozenset[str] = frozenset({VEHICLE_READ})) -> OrganizationContext:
    return OrganizationContext(
        organization_id=OrganizationId.new(),
        authenticated_principal=AuthenticatedPrincipal(
            issuer="https://issuer.example.test",
            subject="asset-vehicle-test-user",
            principal_type=PrincipalType.USER,
            authenticated_at=OCCURRED_AT,
            client_id="asset-vehicle-test",
            technical_scopes=frozenset({"openid"}),
        ),
        user_id=TypedId.new("user"),
        actor_id=TypedId.new("actor"),
        membership_id=TypedId.new("membership"),
        role_ids=(TypedId.new("role"),),
        permission_codes=permissions,
        validated_at=OCCURRED_AT,
    )


def _vehicle(vehicle_id: TypedId) -> Vehicle:
    reading_id = TypedId.parse("vehicle_meter_reading", "00000000-0000-0000-0000-000000000901")
    return Vehicle(
        vehicle_id=vehicle_id,
        organization_id=OrganizationId.new(),
        model_ref=TypedId.parse("vehicle_model", "00000000-0000-0000-0000-000000000801"),
        identifiers=VehicleIdentifiers(
            serial_number="SN-001",
            chassis="CH-001",
            fleet_number="FROTA-7",
        ),
        ownership=AssetOwnership.COMPANY,
        variant_ref=TypedId.parse("vehicle_variant", "00000000-0000-0000-0000-000000000802"),
        site_ref=TypedId.parse("customer_site", "00000000-0000-0000-0000-000000000101"),
        current_baseline_ref=TypedId.parse(
            "configuration_baseline", "00000000-0000-0000-0000-000000000803"
        ),
        baseline_valid_from=OCCURRED_AT,
        lifecycle_state=VehicleLifecycleState.DEGRADED,
        meter_readings=(
            MeterReading(
                reading_id=reading_id,
                kind=MeterKind.HOURS,
                value=Decimal("123.4"),
                observed_at=OCCURRED_AT,
                recorded_at=OCCURRED_AT,
                source="telemetria",
            ),
        ),
        meter_corrections=(
            MeterCorrection(
                correction_id=TypedId.parse(
                    "vehicle_meter_correction", "00000000-0000-0000-0000-000000000902"
                ),
                original_reading_id=reading_id,
                corrected_value=Decimal("123.5"),
                reason="ajuste",
                corrected_at=OCCURRED_AT,
            ),
        ),
        created_at=OCCURRED_AT,
    )


class _FakeVehicleQueryService:
    seen_vehicle_id: TypedId | None = None

    def get_vehicle(self, vehicle_id: TypedId) -> Vehicle:
        self.seen_vehicle_id = vehicle_id
        return _vehicle(vehicle_id)


class _MissingVehicleQueryService:
    def get_vehicle(self, vehicle_id: TypedId) -> Vehicle:
        raise VehicleDetailNaoEncontrado(f"Vehicle '{vehicle_id.value}' não encontrado.")


def _fake_connection() -> object:
    return SimpleNamespace()


def test_vehicle_detail_route_is_registered_in_openapi() -> None:
    paths = set(main_module.app.openapi()["paths"])

    assert "/v1/asset/vehicles/{vehicle_id}" in paths


def test_vehicle_detail_requires_authentication() -> None:
    response = TestClient(main_module.app).get(ROUTE)

    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")


def test_vehicle_detail_rejects_missing_permission(monkeypatch: MonkeyPatch) -> None:
    contexto = _context(permissions=frozenset())
    main_module.app.dependency_overrides[require_authenticated_principal] = lambda: (
        contexto.authenticated_principal
    )
    main_module.app.dependency_overrides[request_connection] = _fake_connection
    main_module.app.dependency_overrides[asset_queries.get_vehicle_query_service] = (
        _FakeVehicleQueryService
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


def test_vehicle_detail_returns_aggregate_detail() -> None:
    contexto = _context()
    service = _FakeVehicleQueryService()
    main_module.app.dependency_overrides[asset_queries.require_vehicle_read] = lambda: contexto
    main_module.app.dependency_overrides[asset_queries.get_vehicle_query_service] = lambda: service

    response = TestClient(main_module.app).get(ROUTE)

    assert response.status_code == 200
    assert service.seen_vehicle_id == TypedId.parse("vehicle", VEHICLE_ID)
    payload = response.json()
    assert payload["vehicle_id"] == VEHICLE_ID
    assert payload["identifiers"] == {
        "serial_number": "SN-001",
        "chassis": "CH-001",
        "fleet_number": "FROTA-7",
    }
    assert payload["ownership"] == "COMPANY"
    assert payload["site_ref"] == "00000000-0000-0000-0000-000000000101"
    assert payload["current_baseline_ref"] == "00000000-0000-0000-0000-000000000803"
    assert payload["lifecycle_state"] == "DEGRADED"
    assert payload["meter_readings"][0]["value"] == "123.4"
    assert payload["meter_corrections"][0]["corrected_value"] == "123.5"


def test_vehicle_detail_rejects_invalid_identifier() -> None:
    contexto = _context()
    main_module.app.dependency_overrides[asset_queries.require_vehicle_read] = lambda: contexto
    main_module.app.dependency_overrides[asset_queries.get_vehicle_query_service] = (
        _FakeVehicleQueryService
    )

    response = TestClient(main_module.app).get("/v1/asset/vehicles/nao-e-uuid")

    assert response.status_code == 422
    assert response.json()["reason_code"] == "IDENTIFICADOR_INVALIDO"


def test_vehicle_detail_returns_404_when_missing() -> None:
    contexto = _context()
    main_module.app.dependency_overrides[asset_queries.require_vehicle_read] = lambda: contexto
    main_module.app.dependency_overrides[asset_queries.get_vehicle_query_service] = (
        _MissingVehicleQueryService
    )

    response = TestClient(main_module.app).get(ROUTE)

    assert response.status_code == 404
    assert response.json()["reason_code"] == "RECURSO_NAO_ENCONTRADO"
