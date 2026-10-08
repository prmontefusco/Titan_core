"""Contrato HTTP de `RegisterPart` — Titan Asset A5."""

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
from packages.asset_application.authorization import PART_REGISTER
from packages.asset_application.event_recorder import AssetOperationContext
from packages.asset_domain.part import Part, PartIdentity
from packages.core_application import IdempotencyExecution
from packages.core_domain import AuthenticatedPrincipal, CanonicalPayload, OrganizationContext
from packages.core_domain.organization_context import PrincipalType
from packages.shared_kernel import OrganizationId, TypedId

ROUTE = "/v1/asset/parts"
NOW = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _restore_app() -> Iterator[None]:
    yield
    main_module.app.dependency_overrides.clear()
    importlib.reload(main_module)


def _context(permissions: frozenset[str] = frozenset({PART_REGISTER})) -> OrganizationContext:
    return OrganizationContext(
        organization_id=OrganizationId.new(),
        authenticated_principal=AuthenticatedPrincipal(
            issuer="https://issuer.example.test",
            subject="part-test-user",
            principal_type=PrincipalType.USER,
            authenticated_at=NOW,
            client_id="part-test",
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
        "part_number": "PN-A5-001",
        "description": "Filtro hidráulico fictício",
        "manufacturer": "Titan Test",
        "manufacturer_pn": "MFG-001",
        "nsn": None,
        "external_classifications": ["TEST_ONLY"],
    }
    body.update(overrides)
    return body


class _Request(Protocol):
    operation: str


class _Idempotency:
    def execute(
        self, request: _Request, handler: Callable[[], CanonicalPayload]
    ) -> IdempotencyExecution:
        payload = handler()
        return IdempotencyExecution(payload.schema, payload.version, payload.canonical_bytes, False)


class _PartService:
    seen: PartIdentity | None = None

    def register_part(
        self, context: AssetOperationContext, *, identity: PartIdentity, occurred_at: datetime
    ) -> Part:
        self.seen = identity
        return Part(
            part_id=TypedId.parse("part", "00000000-0000-0000-0000-000000000801"),
            organization_id=context.organization_id,
            identity=identity,
            created_at=NOW,
        )


def _override(service: _PartService, context: OrganizationContext) -> None:
    main_module.app.dependency_overrides[asset_commands.require_part_register] = lambda: context
    main_module.app.dependency_overrides[asset_commands.get_part_service] = lambda: service
    main_module.app.dependency_overrides[asset_commands.get_idempotency_service] = _Idempotency


def test_route_is_registered() -> None:
    assert ROUTE in main_module.app.openapi()["paths"]


def test_register_part_requires_authentication() -> None:
    response = TestClient(main_module.app).post(
        ROUTE, json=_body(), headers={"Idempotency-Key": "part-auth"}
    )
    assert response.status_code == 401


def test_register_part_rejects_missing_permission(monkeypatch: MonkeyPatch) -> None:
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
            "Idempotency-Key": "part-permission",
        },
    )
    assert response.status_code == 403
    assert response.json()["reason_code"] == "PERMISSAO_AUSENTE"


def test_register_part_returns_created_part() -> None:
    context = _context()
    service = _PartService()
    _override(service, context)
    response = TestClient(main_module.app).post(
        ROUTE, json=_body(), headers={"Idempotency-Key": "part-success"}
    )
    assert response.status_code == 201
    assert response.json()["part_number"] == "PN-A5-001"
    assert response.json()["external_classifications"] == ["TEST_ONLY"]
    assert response.json()["version"] == 1
    assert service.seen is not None


def test_register_part_rejects_blank_required_field() -> None:
    context = _context()
    _override(_PartService(), context)
    response = TestClient(main_module.app).post(
        ROUTE,
        json=_body(part_number=""),
        headers={"Idempotency-Key": "part-invalid"},
    )
    assert response.status_code == 422
