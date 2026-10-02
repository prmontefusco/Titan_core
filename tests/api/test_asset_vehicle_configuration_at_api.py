"""Contrato HTTP de `GetVehicleConfigurationAt` — Titan Asset A5."""

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
from packages.asset_application.vehicle_configuration_query import (
    VehicleConfigurationAt,
    VehicleConfigurationAtNaoEncontrada,
)
from packages.asset_domain.configuration import (
    BaselinePosition,
    ConfigurationBaseline,
    ConfigurationRevision,
    Effectivity,
)
from packages.asset_domain.vehicle import AssetOwnership, Vehicle, VehicleIdentifiers
from packages.core_domain import AuthenticatedPrincipal, OrganizationContext, PrincipalType
from packages.shared_kernel import OrganizationId, TypedId

VEHICLE_ID = "00000000-0000-0000-0000-000000000401"
BASELINE_ID = "00000000-0000-0000-0000-000000000803"
MODEL_ID = "00000000-0000-0000-0000-000000000801"
PART_ID = "00000000-0000-0000-0000-000000000811"
PART_REVISION_ID = "00000000-0000-0000-0000-000000000812"
INSTANT = "2026-10-02T12:00:00Z"
ROUTE = f"/v1/asset/vehicles/{VEHICLE_ID}/configuration-at"
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
            subject="asset-vehicle-configuration-test-user",
            principal_type=PrincipalType.USER,
            authenticated_at=OCCURRED_AT,
            client_id="asset-vehicle-configuration-test",
            technical_scopes=frozenset({"openid"}),
        ),
        user_id=TypedId.new("user"),
        actor_id=TypedId.new("actor"),
        membership_id=TypedId.new("membership"),
        role_ids=(TypedId.new("role"),),
        permission_codes=permissions,
        validated_at=OCCURRED_AT,
    )


def _vehicle(vehicle_id: TypedId, *, baseline_ref: TypedId, model_ref: TypedId) -> Vehicle:
    return Vehicle(
        vehicle_id=vehicle_id,
        organization_id=OrganizationId.new(),
        model_ref=model_ref,
        identifiers=VehicleIdentifiers(serial_number="SN-001"),
        ownership=AssetOwnership.COMPANY,
        current_baseline_ref=baseline_ref,
        baseline_valid_from=OCCURRED_AT,
        created_at=OCCURRED_AT,
    )


def _baseline(baseline_id: TypedId, *, model_ref: TypedId) -> ConfigurationBaseline:
    return ConfigurationBaseline(
        baseline_id=baseline_id,
        organization_id=OrganizationId.new(),
        model_ref=model_ref,
        revision=ConfigurationRevision(number=2),
        effectivity=Effectivity(valid_from=OCCURRED_AT, serial_from="SN-000"),
        positions=(
            BaselinePosition(
                position_code="MOTOR",
                part_ref=TypedId.parse("part", PART_ID),
                part_revision_ref=TypedId.parse("part_revision", PART_REVISION_ID),
            ),
        ),
        created_at=OCCURRED_AT,
    )


class _FakeVehicleConfigurationAtService:
    seen_vehicle_id: TypedId | None = None
    seen_instant: datetime | None = None

    def get_configuration_at(
        self, *, vehicle_id: TypedId, instant: datetime
    ) -> VehicleConfigurationAt:
        self.seen_vehicle_id = vehicle_id
        self.seen_instant = instant
        baseline_ref = TypedId.parse("configuration_baseline", BASELINE_ID)
        model_ref = TypedId.parse("vehicle_model", MODEL_ID)
        return VehicleConfigurationAt(
            vehicle=_vehicle(vehicle_id, baseline_ref=baseline_ref, model_ref=model_ref),
            baseline=_baseline(baseline_ref, model_ref=model_ref),
            instant=instant,
        )


class _MissingVehicleConfigurationAtService:
    def get_configuration_at(
        self, *, vehicle_id: TypedId, instant: datetime
    ) -> VehicleConfigurationAt:
        raise VehicleConfigurationAtNaoEncontrada(
            "ConfigurationBaseline de Vehicle "
            f"'{vehicle_id.value}' ausente em {instant.isoformat()}."
        )


def _fake_connection() -> object:
    return SimpleNamespace()


def test_vehicle_configuration_at_route_is_registered_in_openapi() -> None:
    paths = set(main_module.app.openapi()["paths"])

    assert "/v1/asset/vehicles/{vehicle_id}/configuration-at" in paths


def test_vehicle_configuration_at_requires_authentication() -> None:
    response = TestClient(main_module.app).get(ROUTE, params={"instant": INSTANT})

    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")


def test_vehicle_configuration_at_rejects_missing_permission(
    monkeypatch: MonkeyPatch,
) -> None:
    contexto = _context(permissions=frozenset())
    main_module.app.dependency_overrides[require_authenticated_principal] = lambda: (
        contexto.authenticated_principal
    )
    main_module.app.dependency_overrides[request_connection] = _fake_connection
    main_module.app.dependency_overrides[asset_queries.get_vehicle_configuration_at_service] = (
        _FakeVehicleConfigurationAtService
    )

    monkeypatch.setattr(
        "apps.api.livestock_dependencies.resolve_organization_context",
        lambda *_args, **_kwargs: contexto,
    )

    response = TestClient(main_module.app).get(
        ROUTE,
        params={"instant": INSTANT},
        headers={ORGANIZATION_HEADER: str(contexto.organization_id.value)},
    )

    assert response.status_code == 403
    assert response.json()["reason_code"] == "PERMISSAO_AUSENTE"


def test_vehicle_configuration_at_returns_current_baseline_covering_instant() -> None:
    contexto = _context()
    service = _FakeVehicleConfigurationAtService()
    main_module.app.dependency_overrides[asset_queries.require_vehicle_read] = lambda: contexto
    main_module.app.dependency_overrides[asset_queries.get_vehicle_configuration_at_service] = (
        lambda: service
    )

    response = TestClient(main_module.app).get(ROUTE, params={"instant": INSTANT})

    assert response.status_code == 200
    assert service.seen_vehicle_id == TypedId.parse("vehicle", VEHICLE_ID)
    assert service.seen_instant == OCCURRED_AT
    payload = response.json()
    assert payload["vehicle_id"] == VEHICLE_ID
    assert payload["instant"] == INSTANT
    assert payload["baseline"]["baseline_id"] == BASELINE_ID
    assert payload["baseline"]["model_ref"] == MODEL_ID
    assert payload["baseline"]["revision_number"] == 2
    assert payload["baseline"]["positions"] == [
        {
            "position_code": "MOTOR",
            "part_ref": PART_ID,
            "part_revision_ref": PART_REVISION_ID,
        }
    ]


def test_vehicle_configuration_at_rejects_invalid_identifier() -> None:
    contexto = _context()
    main_module.app.dependency_overrides[asset_queries.require_vehicle_read] = lambda: contexto
    main_module.app.dependency_overrides[asset_queries.get_vehicle_configuration_at_service] = (
        _FakeVehicleConfigurationAtService
    )

    response = TestClient(main_module.app).get(
        "/v1/asset/vehicles/nao-e-uuid/configuration-at",
        params={"instant": INSTANT},
    )

    assert response.status_code == 422
    assert response.json()["reason_code"] == "IDENTIFICADOR_INVALIDO"


def test_vehicle_configuration_at_rejects_non_utc_instant() -> None:
    contexto = _context()
    main_module.app.dependency_overrides[asset_queries.require_vehicle_read] = lambda: contexto
    main_module.app.dependency_overrides[asset_queries.get_vehicle_configuration_at_service] = (
        _FakeVehicleConfigurationAtService
    )

    response = TestClient(main_module.app).get(
        ROUTE,
        params={"instant": "2026-10-02T08:00:00-04:00"},
    )

    assert response.status_code == 422
    assert response.json()["reason_code"] == "DATA_INVALIDA"


def test_vehicle_configuration_at_returns_404_when_missing() -> None:
    contexto = _context()
    main_module.app.dependency_overrides[asset_queries.require_vehicle_read] = lambda: contexto
    main_module.app.dependency_overrides[asset_queries.get_vehicle_configuration_at_service] = (
        _MissingVehicleConfigurationAtService
    )

    response = TestClient(main_module.app).get(ROUTE, params={"instant": INSTANT})

    assert response.status_code == 404
    assert response.json()["reason_code"] == "RECURSO_NAO_ENCONTRADO"
