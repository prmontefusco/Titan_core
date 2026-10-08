"""Contratos HTTP de comandos de `Vehicle` — Titan Asset A5."""

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
from packages.asset_application.authorization import VEHICLE_RECORD_METER, VEHICLE_TRANSITION
from packages.asset_application.vehicle_service import VehicleNaoEncontrado
from packages.asset_domain.vehicle import (
    AssetOwnership,
    MeterKind,
    MeterReading,
    Vehicle,
    VehicleIdentifiers,
    VehicleLifecycleState,
)
from packages.core_application import IdempotencyExecution, OptimisticConcurrencyConflict
from packages.core_domain import AuthenticatedPrincipal, CanonicalPayload, OrganizationContext
from packages.core_domain.organization_context import PrincipalType
from packages.shared_kernel import OrganizationId, TypedId

VEHICLE_ID = "00000000-0000-0000-0000-000000000401"
ROUTE = f"/v1/asset/vehicles/{VEHICLE_ID}/transition-lifecycle"
METER_ROUTE = f"/v1/asset/vehicles/{VEHICLE_ID}/meter-readings"
OCCURRED_AT = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _restore_default_app() -> Iterator[None]:
    yield
    main_module.app.dependency_overrides.clear()
    importlib.reload(main_module)


def _context(
    permissions: frozenset[str] = frozenset({VEHICLE_TRANSITION}),
) -> OrganizationContext:
    return OrganizationContext(
        organization_id=OrganizationId.new(),
        authenticated_principal=AuthenticatedPrincipal(
            issuer="https://issuer.example.test",
            subject="asset-vehicle-transition-test-user",
            principal_type=PrincipalType.USER,
            authenticated_at=OCCURRED_AT,
            client_id="asset-vehicle-transition-test",
            technical_scopes=frozenset({"openid"}),
        ),
        user_id=TypedId.new("user"),
        actor_id=TypedId.new("actor"),
        membership_id=TypedId.new("membership"),
        role_ids=(TypedId.new("role"),),
        permission_codes=permissions,
        validated_at=OCCURRED_AT,
    )


def _vehicle(*, version: int = 2) -> Vehicle:
    return Vehicle(
        vehicle_id=TypedId.parse("vehicle", VEHICLE_ID),
        organization_id=OrganizationId.new(),
        model_ref=TypedId.new("vehicle_model"),
        identifiers=VehicleIdentifiers(serial_number="SN-TRANSITION-001"),
        ownership=AssetOwnership.COMPANY,
        lifecycle_state=VehicleLifecycleState.DEGRADED,
        version=version,
        created_at=OCCURRED_AT,
    )


class _RequestWithOperation(Protocol):
    operation: str


class _ImmediateIdempotencyService:
    seen_operation: str | None = None

    def execute(
        self,
        request: _RequestWithOperation,
        handler: Callable[[], CanonicalPayload],
    ) -> IdempotencyExecution:
        self.seen_operation = request.operation
        payload = handler()
        return IdempotencyExecution(payload.schema, payload.version, payload.canonical_bytes, False)


class _VehicleService:
    seen: tuple[TypedId, VehicleLifecycleState, str | None, int | None] | None = None

    def transition_lifecycle(
        self,
        _context: object,
        vehicle_id: TypedId,
        *,
        new_state: VehicleLifecycleState,
        reason: str | None,
        expected_version: int | None,
        occurred_at: datetime,
    ) -> Vehicle:
        self.seen = (vehicle_id, new_state, reason, expected_version)
        return _vehicle(version=expected_version + 1 if expected_version is not None else 2)


class _MissingVehicleService(_VehicleService):
    def transition_lifecycle(self, *args: object, **kwargs: object) -> Vehicle:
        raise VehicleNaoEncontrado("Vehicle não encontrado.")


class _StaleVehicleService(_VehicleService):
    def transition_lifecycle(self, *args: object, **kwargs: object) -> Vehicle:
        raise OptimisticConcurrencyConflict()


class _MeterVehicleService:
    seen: tuple[TypedId, MeterKind, Decimal, datetime, str, int | None] | None = None

    def record_meter_reading(
        self,
        _context: object,
        vehicle_id: TypedId,
        *,
        kind: MeterKind,
        value: Decimal,
        observed_at: datetime,
        recorded_at: datetime,
        source: str,
        expected_version: int | None,
    ) -> Vehicle:
        self.seen = (vehicle_id, kind, value, observed_at, source, expected_version)
        vehicle = _vehicle(version=expected_version or 1)
        return vehicle.record_meter_reading(
            MeterReading(
                reading_id=TypedId.new("vehicle_meter_reading"),
                kind=kind,
                value=value,
                observed_at=observed_at,
                recorded_at=recorded_at,
                source=source,
            )
        )


class _StaleMeterVehicleService(_MeterVehicleService):
    def record_meter_reading(self, *args: object, **kwargs: object) -> Vehicle:
        raise OptimisticConcurrencyConflict()


def _fake_connection() -> object:
    return SimpleNamespace()


def _override_command_dependencies(service: object, contexto: OrganizationContext) -> None:
    main_module.app.dependency_overrides[asset_commands.require_vehicle_transition] = lambda: (
        contexto
    )
    main_module.app.dependency_overrides[asset_commands.require_vehicle_record_meter] = lambda: (
        contexto
    )
    main_module.app.dependency_overrides[asset_commands.get_vehicle_service] = lambda: service
    main_module.app.dependency_overrides[asset_commands.get_idempotency_service] = (
        _ImmediateIdempotencyService
    )


def test_route_is_registered_in_openapi() -> None:
    assert ROUTE.replace(VEHICLE_ID, "{vehicle_id}") in main_module.app.openapi()["paths"]


def test_transition_requires_authentication() -> None:
    response = TestClient(main_module.app).post(
        ROUTE,
        json={"expected_version": 1, "new_state": "DEGRADED", "reason": "falha"},
        headers={"Idempotency-Key": "vehicle-transition-auth"},
    )
    assert response.status_code == 401


def test_transition_rejects_missing_permission(monkeypatch: MonkeyPatch) -> None:
    contexto = _context(permissions=frozenset())
    main_module.app.dependency_overrides[require_authenticated_principal] = lambda: (
        contexto.authenticated_principal
    )
    main_module.app.dependency_overrides[request_connection] = _fake_connection
    monkeypatch.setattr(
        "apps.api.livestock_dependencies.resolve_organization_context",
        lambda *_args, **_kwargs: contexto,
    )

    response = TestClient(main_module.app).post(
        ROUTE,
        json={"expected_version": 1, "new_state": "DEGRADED", "reason": "falha"},
        headers={
            ORGANIZATION_HEADER: str(contexto.organization_id.value),
            "Idempotency-Key": "vehicle-transition-permission",
        },
    )
    assert response.status_code == 403
    assert response.json()["reason_code"] == "PERMISSAO_AUSENTE"


def test_transition_returns_updated_vehicle() -> None:
    contexto = _context()
    service = _VehicleService()
    _override_command_dependencies(service, contexto)

    response = TestClient(main_module.app).post(
        ROUTE,
        json={"expected_version": 1, "new_state": "DEGRADED", "reason": "falha observada"},
        headers={"Idempotency-Key": "vehicle-transition-success"},
    )

    assert response.status_code == 200
    assert response.json()["lifecycle_state"] == "DEGRADED"
    assert response.json()["version"] == 2
    assert service.seen == (
        TypedId.parse("vehicle", VEHICLE_ID),
        VehicleLifecycleState.DEGRADED,
        "falha observada",
        1,
    )


def test_transition_rejects_invalid_vehicle_id() -> None:
    contexto = _context()
    _override_command_dependencies(_VehicleService(), contexto)
    response = TestClient(main_module.app).post(
        "/v1/asset/vehicles/nao-e-uuid/transition-lifecycle",
        json={"expected_version": 1, "new_state": "DEGRADED"},
        headers={"Idempotency-Key": "vehicle-transition-invalid-id"},
    )
    assert response.status_code == 422
    assert response.json()["reason_code"] == "IDENTIFICADOR_INVALIDO"


@pytest.mark.parametrize(
    ("service", "expected_status", "reason_code"),
    [
        (_MissingVehicleService(), 404, "RECURSO_NAO_ENCONTRADO"),
        (_StaleVehicleService(), 409, OptimisticConcurrencyConflict.code),
    ],
)
def test_transition_translates_application_errors(
    service: object, expected_status: int, reason_code: str
) -> None:
    contexto = _context()
    _override_command_dependencies(service, contexto)
    response = TestClient(main_module.app).post(
        ROUTE,
        json={"expected_version": 1, "new_state": "DEGRADED"},
        headers={"Idempotency-Key": f"vehicle-transition-{expected_status}"},
    )
    assert response.status_code == expected_status
    assert response.json()["reason_code"] == reason_code


def _meter_body(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "expected_version": 1,
        "kind": "HOURS",
        "value": "125.5",
        "observed_at": "2026-10-08T12:00:00Z",
        "source": "telemetria",
    }
    body.update(overrides)
    return body


def test_meter_route_is_registered_in_openapi() -> None:
    assert METER_ROUTE.replace(VEHICLE_ID, "{vehicle_id}") in main_module.app.openapi()["paths"]


def test_record_meter_requires_authentication() -> None:
    response = TestClient(main_module.app).post(
        METER_ROUTE,
        json=_meter_body(),
        headers={"Idempotency-Key": "vehicle-meter-auth"},
    )
    assert response.status_code == 401


def test_record_meter_rejects_missing_permission(monkeypatch: MonkeyPatch) -> None:
    contexto = _context(permissions=frozenset())
    main_module.app.dependency_overrides[require_authenticated_principal] = lambda: (
        contexto.authenticated_principal
    )
    main_module.app.dependency_overrides[request_connection] = _fake_connection
    monkeypatch.setattr(
        "apps.api.livestock_dependencies.resolve_organization_context",
        lambda *_args, **_kwargs: contexto,
    )
    response = TestClient(main_module.app).post(
        METER_ROUTE,
        json=_meter_body(),
        headers={
            ORGANIZATION_HEADER: str(contexto.organization_id.value),
            "Idempotency-Key": "vehicle-meter-permission",
        },
    )
    assert response.status_code == 403
    assert response.json()["reason_code"] == "PERMISSAO_AUSENTE"


def test_record_meter_returns_updated_vehicle() -> None:
    contexto = _context(permissions=frozenset({VEHICLE_RECORD_METER}))
    service = _MeterVehicleService()
    _override_command_dependencies(service, contexto)
    response = TestClient(main_module.app).post(
        METER_ROUTE,
        json=_meter_body(),
        headers={"Idempotency-Key": "vehicle-meter-success"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["version"] == 2
    assert payload["meter_readings"][0]["kind"] == "HOURS"
    assert payload["meter_readings"][0]["value"] == "125.5"
    assert service.seen == (
        TypedId.parse("vehicle", VEHICLE_ID),
        MeterKind.HOURS,
        Decimal("125.5"),
        OCCURRED_AT,
        "telemetria",
        1,
    )


def test_record_meter_rejects_non_utc_observed_at() -> None:
    contexto = _context(permissions=frozenset({VEHICLE_RECORD_METER}))
    _override_command_dependencies(_MeterVehicleService(), contexto)
    response = TestClient(main_module.app).post(
        METER_ROUTE,
        json=_meter_body(observed_at="2026-10-08T12:00:00"),
        headers={"Idempotency-Key": "vehicle-meter-non-utc"},
    )
    assert response.status_code == 422
    assert response.json()["reason_code"] == "DATA_INVALIDA"


def test_record_meter_rejects_stale_version() -> None:
    contexto = _context(permissions=frozenset({VEHICLE_RECORD_METER}))
    _override_command_dependencies(_StaleMeterVehicleService(), contexto)
    response = TestClient(main_module.app).post(
        METER_ROUTE,
        json=_meter_body(),
        headers={"Idempotency-Key": "vehicle-meter-stale"},
    )
    assert response.status_code == 409
    assert response.json()["reason_code"] == OptimisticConcurrencyConflict.code
