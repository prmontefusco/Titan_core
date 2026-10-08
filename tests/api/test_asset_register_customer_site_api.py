"""Contrato HTTP de `RegisterCustomerSite` — Titan Asset A5."""

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
from packages.asset_application.authorization import SITE_REGISTER
from packages.asset_application.event_recorder import AssetOperationContext
from packages.asset_domain.customer_site import CustomerSite, CustomerSiteKind, SiteContact
from packages.core_application import IdempotencyExecution
from packages.core_domain import AuthenticatedPrincipal, CanonicalPayload, OrganizationContext
from packages.core_domain.organization_context import PrincipalType
from packages.shared_kernel import OrganizationId, TypedId

ROUTE = "/v1/asset/customer-sites"
CUSTOMER_ID = "00000000-0000-0000-0000-000000000701"
OCCURRED_AT = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _restore_default_app() -> Iterator[None]:
    yield
    main_module.app.dependency_overrides.clear()
    importlib.reload(main_module)


def _context(permissions: frozenset[str] = frozenset({SITE_REGISTER})) -> OrganizationContext:
    return OrganizationContext(
        organization_id=OrganizationId.new(),
        authenticated_principal=AuthenticatedPrincipal(
            issuer="https://issuer.example.test",
            subject="asset-site-test-user",
            principal_type=PrincipalType.USER,
            authenticated_at=OCCURRED_AT,
            client_id="asset-site-test",
            technical_scopes=frozenset({"openid"}),
        ),
        user_id=TypedId.new("user"),
        actor_id=TypedId.new("actor"),
        membership_id=TypedId.new("membership"),
        role_ids=(TypedId.new("role"),),
        permission_codes=permissions,
        validated_at=OCCURRED_AT,
    )


def _body(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "customer_id": CUSTOMER_ID,
        "code": "OM-CGB-01",
        "display_name": "Organização de Manutenção Cuiabá",
        "kind": "OM",
        "contacts": [
            {
                "name": "Contato fictício",
                "role": "Planejamento",
                "email": "contato@example.test",
                "phone": None,
            }
        ],
    }
    body.update(overrides)
    return body


class _RequestWithOperation(Protocol):
    operation: str


class _ImmediateIdempotencyService:
    def execute(
        self,
        request: _RequestWithOperation,
        handler: Callable[[], CanonicalPayload],
    ) -> IdempotencyExecution:
        payload = handler()
        return IdempotencyExecution(payload.schema, payload.version, payload.canonical_bytes, False)


class _CustomerSiteService:
    seen: tuple[TypedId, str, str, CustomerSiteKind, tuple[SiteContact, ...]] | None = None

    def register_site(
        self,
        context: AssetOperationContext,
        *,
        customer_ref: TypedId,
        code: str,
        display_name: str,
        kind: CustomerSiteKind,
        contacts: tuple[SiteContact, ...],
        occurred_at: datetime,
    ) -> CustomerSite:
        organization_id = context.organization_id
        self.seen = (customer_ref, code, display_name, kind, contacts)
        return CustomerSite(
            site_id=TypedId.parse("customer_site", "00000000-0000-0000-0000-000000000101"),
            organization_id=organization_id,
            customer_ref=customer_ref,
            code=code,
            display_name=display_name,
            kind=kind,
            contacts=contacts,
        )


def _fake_connection() -> object:
    return SimpleNamespace()


def _override(service: _CustomerSiteService, contexto: OrganizationContext) -> None:
    main_module.app.dependency_overrides[asset_commands.require_site_register] = lambda: contexto
    main_module.app.dependency_overrides[asset_commands.get_customer_site_service] = lambda: service
    main_module.app.dependency_overrides[asset_commands.get_idempotency_service] = (
        _ImmediateIdempotencyService
    )


def test_route_is_registered_in_openapi() -> None:
    assert ROUTE in main_module.app.openapi()["paths"]


def test_register_site_requires_authentication() -> None:
    response = TestClient(main_module.app).post(
        ROUTE,
        json=_body(),
        headers={"Idempotency-Key": "site-auth"},
    )
    assert response.status_code == 401


def test_register_site_rejects_missing_permission(monkeypatch: MonkeyPatch) -> None:
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
        json=_body(),
        headers={
            ORGANIZATION_HEADER: str(contexto.organization_id.value),
            "Idempotency-Key": "site-permission",
        },
    )
    assert response.status_code == 403
    assert response.json()["reason_code"] == "PERMISSAO_AUSENTE"


def test_register_site_returns_created_site() -> None:
    contexto = _context()
    service = _CustomerSiteService()
    _override(service, contexto)
    response = TestClient(main_module.app).post(
        ROUTE,
        json=_body(),
        headers={"Idempotency-Key": "site-success"},
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["customer_ref"] == CUSTOMER_ID
    assert payload["code"] == "OM-CGB-01"
    assert payload["kind"] == "OM"
    assert payload["contacts"][0]["email"] == "contato@example.test"
    assert service.seen is not None


def test_register_site_rejects_invalid_customer_id() -> None:
    contexto = _context()
    _override(_CustomerSiteService(), contexto)
    response = TestClient(main_module.app).post(
        ROUTE,
        json=_body(customer_id="nao-e-uuid"),
        headers={"Idempotency-Key": "site-invalid-customer"},
    )
    assert response.status_code == 422
    assert response.json()["reason_code"] == "IDENTIFICADOR_INVALIDO"
