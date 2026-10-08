"""Contrato HTTP de `AddPartRevision` — Titan Asset A5."""

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
from packages.asset_application.authorization import PART_ADD_REVISION, PART_SUPERSEDE
from packages.asset_application.event_recorder import AssetOperationContext
from packages.asset_domain.part import Part, PartIdentity, PartRevision
from packages.core_application import IdempotencyExecution, OptimisticConcurrencyConflict
from packages.core_domain import AuthenticatedPrincipal, CanonicalPayload, OrganizationContext
from packages.core_domain.organization_context import PrincipalType
from packages.shared_kernel import OrganizationId, TypedId

PART_ID = "00000000-0000-0000-0000-000000000801"
ROUTE = f"/v1/asset/parts/{PART_ID}/revisions"
SUPERSEDE_ROUTE = f"{ROUTE}/supersede"
NOW = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _restore_app() -> Iterator[None]:
    yield
    main_module.app.dependency_overrides.clear()
    importlib.reload(main_module)


def _context(permissions: frozenset[str] = frozenset({PART_ADD_REVISION})) -> OrganizationContext:
    return OrganizationContext(
        organization_id=OrganizationId.new(),
        authenticated_principal=AuthenticatedPrincipal(
            issuer="https://issuer.example.test",
            subject="part-revision-test-user",
            principal_type=PrincipalType.USER,
            authenticated_at=NOW,
            client_id="part-revision-test",
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
        "revision_code": "A",
        "materials": ["Aço fictício"],
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
    stale = False

    def add_part_revision(
        self,
        context: AssetOperationContext,
        part_id: TypedId,
        *,
        revision_code: str,
        spec_ref: TypedId | None,
        drawing_ref: TypedId | None,
        materials: tuple[str, ...],
        expected_version: int | None,
        occurred_at: datetime,
    ) -> Part:
        del occurred_at
        if self.stale:
            raise OptimisticConcurrencyConflict()
        assert expected_version == 1
        revision = PartRevision(
            revision_id=TypedId.parse("part_revision", "00000000-0000-0000-0000-000000000802"),
            revision_code=revision_code,
            spec_ref=spec_ref,
            drawing_ref=drawing_ref,
            materials=materials,
        )
        return Part(
            part_id=part_id,
            organization_id=context.organization_id,
            identity=PartIdentity(
                part_number="PN-A5-001",
                description="Filtro hidráulico fictício",
                manufacturer="Titan Test",
            ),
            revisions=(revision,),
            version=2,
            created_at=NOW,
        )

    def supersede_part_revision(
        self,
        context: AssetOperationContext,
        part_id: TypedId,
        *,
        predecessor_revision_id: TypedId,
        successor_revision_id: TypedId,
        reason: str,
        expected_version: int | None,
        occurred_at: datetime,
    ) -> Part:
        del occurred_at
        if self.stale:
            raise OptimisticConcurrencyConflict()
        assert expected_version == 3
        part = Part(
            part_id=part_id,
            organization_id=context.organization_id,
            identity=PartIdentity(
                part_number="PN-A5-001",
                description="Filtro hidráulico fictício",
                manufacturer="Titan Test",
            ),
            revisions=(
                PartRevision(revision_id=predecessor_revision_id, revision_code="A"),
                PartRevision(revision_id=successor_revision_id, revision_code="B"),
            ),
            version=3,
            created_at=NOW,
        )
        return part.supersede_revision(
            predecessor_revision_id=predecessor_revision_id,
            successor_revision_id=successor_revision_id,
            reason=reason,
        )


def _override(service: _PartService, context: OrganizationContext) -> None:
    main_module.app.dependency_overrides[asset_commands.require_part_add_revision] = lambda: context
    main_module.app.dependency_overrides[asset_commands.require_part_supersede] = lambda: context
    main_module.app.dependency_overrides[asset_commands.get_part_service] = lambda: service
    main_module.app.dependency_overrides[asset_commands.get_idempotency_service] = _Idempotency


def test_route_is_registered() -> None:
    assert "/v1/asset/parts/{part_id}/revisions" in main_module.app.openapi()["paths"]


def test_add_part_revision_requires_authentication() -> None:
    response = TestClient(main_module.app).post(
        ROUTE, json=_body(), headers={"Idempotency-Key": "part-revision-auth"}
    )
    assert response.status_code == 401


def test_add_part_revision_rejects_missing_permission(monkeypatch: MonkeyPatch) -> None:
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
            "Idempotency-Key": "part-revision-permission",
        },
    )
    assert response.status_code == 403
    assert response.json()["reason_code"] == "PERMISSAO_AUSENTE"


def test_add_part_revision_returns_updated_part() -> None:
    context = _context()
    _override(_PartService(), context)
    response = TestClient(main_module.app).post(
        ROUTE, json=_body(), headers={"Idempotency-Key": "part-revision-success"}
    )
    assert response.status_code == 200
    assert response.json()["version"] == 2
    assert response.json()["revisions"] == [
        {
            "revision_id": "00000000-0000-0000-0000-000000000802",
            "revision_code": "A",
            "lifecycle_state": "ACTIVE",
            "spec_ref": None,
            "drawing_ref": None,
            "materials": ["Aço fictício"],
        }
    ]


def test_add_part_revision_rejects_invalid_part_id() -> None:
    context = _context()
    _override(_PartService(), context)
    response = TestClient(main_module.app).post(
        "/v1/asset/parts/not-a-uuid/revisions",
        json=_body(),
        headers={"Idempotency-Key": "part-revision-invalid-id"},
    )
    assert response.status_code == 422


def test_add_part_revision_rejects_stale_version() -> None:
    context = _context()
    service = _PartService()
    service.stale = True
    _override(service, context)
    response = TestClient(main_module.app).post(
        ROUTE, json=_body(), headers={"Idempotency-Key": "part-revision-stale"}
    )
    assert response.status_code == 409
    assert response.json()["reason_code"] == OptimisticConcurrencyConflict.code


def _supersede_body(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "expected_version": 3,
        "predecessor_revision_id": "00000000-0000-0000-0000-000000000802",
        "successor_revision_id": "00000000-0000-0000-0000-000000000803",
        "reason": "Revisão B substitui a revisão A.",
    }
    body.update(overrides)
    return body


def test_supersede_part_revision_requires_authentication() -> None:
    response = TestClient(main_module.app).post(
        SUPERSEDE_ROUTE,
        json=_supersede_body(),
        headers={"Idempotency-Key": "part-supersede-auth"},
    )
    assert response.status_code == 401


def test_supersede_part_revision_rejects_missing_permission(monkeypatch: MonkeyPatch) -> None:
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
        SUPERSEDE_ROUTE,
        json=_supersede_body(),
        headers={
            ORGANIZATION_HEADER: str(context.organization_id.value),
            "Idempotency-Key": "part-supersede-permission",
        },
    )
    assert response.status_code == 403
    assert response.json()["reason_code"] == "PERMISSAO_AUSENTE"


def test_supersede_part_revision_returns_updated_part() -> None:
    context = _context(frozenset({PART_SUPERSEDE}))
    _override(_PartService(), context)
    response = TestClient(main_module.app).post(
        SUPERSEDE_ROUTE,
        json=_supersede_body(),
        headers={"Idempotency-Key": "part-supersede-success"},
    )
    assert response.status_code == 200
    assert response.json()["version"] == 4
    states = {
        revision["revision_code"]: revision["lifecycle_state"]
        for revision in response.json()["revisions"]
    }
    assert states == {"A": "SUPERSEDED", "B": "ACTIVE"}


def test_supersede_part_revision_rejects_stale_version() -> None:
    context = _context(frozenset({PART_SUPERSEDE}))
    service = _PartService()
    service.stale = True
    _override(service, context)
    response = TestClient(main_module.app).post(
        SUPERSEDE_ROUTE,
        json=_supersede_body(),
        headers={"Idempotency-Key": "part-supersede-stale"},
    )
    assert response.status_code == 409
    assert response.json()["reason_code"] == OptimisticConcurrencyConflict.code
