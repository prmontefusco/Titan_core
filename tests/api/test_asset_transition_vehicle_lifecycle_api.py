"""Contrato HTTP de `TransitionVehicleLifecycle` — Titan Asset A5."""

import importlib
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Protocol

import pytest
from fastapi.testclient import TestClient
from pytest import MonkeyPatch

import apps.api.main as main_module
from apps.api.asset import commands as asset_commands
from apps.api.authentication import require_authenticated_principal
from apps.api.livestock_dependencies import ORGANIZATION_HEADER, request_connection
from packages.asset_application.authorization import VEHICLE_TRANSITION
from packages.asset_application.vehicle_service import VehicleNaoEncontrado
from packages.asset_domain.vehicle import (
    AssetOwnership,
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


def _fake_connection() -> object:
    return SimpleNamespace()


def _override_command_dependencies(service: object, contexto: OrganizationContext) -> None:
    main_module.app.dependency_overrides[asset_commands.require_vehicle_transition] = lambda: (
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
