"""Contrato HTTP de `ChangeInterchangeabilityGroup` — Titan Asset A5."""

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
from packages.asset_application.authorization import PART_EDIT_INTERCHANGE
from packages.asset_application.event_recorder import AssetOperationContext
from packages.asset_domain.part import InterchangeabilityGroup
from packages.core_application import IdempotencyExecution, OptimisticConcurrencyConflict
from packages.core_domain import AuthenticatedPrincipal, CanonicalPayload, OrganizationContext
from packages.core_domain.organization_context import PrincipalType
from packages.shared_kernel import OrganizationId, TypedId

GROUP_ID = "00000000-0000-0000-0000-000000000901"
REVISION_ID = "00000000-0000-0000-0000-000000000902"
ROUTE = f"/v1/asset/interchangeability-groups/{GROUP_ID}/members/change"
NOW = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _restore_app() -> Iterator[None]:
    yield
    main_module.app.dependency_overrides.clear()
    importlib.reload(main_module)


def _context(
    permissions: frozenset[str] = frozenset({PART_EDIT_INTERCHANGE}),
) -> OrganizationContext:
    return OrganizationContext(
        organization_id=OrganizationId.new(),
        authenticated_principal=AuthenticatedPrincipal(
            issuer="https://issuer.example.test",
            subject="interchange-test-user",
            principal_type=PrincipalType.USER,
            authenticated_at=NOW,
            client_id="interchange-test",
            technical_scopes=frozenset({"openid"}),
        ),
        user_id=TypedId.new("user"),
        actor_id=TypedId.new("actor"),
        membership_id=TypedId.new("membership"),
        role_ids=(TypedId.new("role"),),
        permission_codes=permissions,
        validated_at=NOW,
    )


class _Request(Protocol):
    operation: str


class _Idempotency:
    def execute(
        self, request: _Request, handler: Callable[[], CanonicalPayload]
    ) -> IdempotencyExecution:
        payload = handler()
        return IdempotencyExecution(payload.schema, payload.version, payload.canonical_bytes, False)


class _Service:
    stale = False

    def add_member(
        self,
        context: AssetOperationContext,
        group_id: TypedId,
        *,
        revision_ref: TypedId,
        expected_version: int | None,
        occurred_at: datetime,
    ) -> InterchangeabilityGroup:
        del occurred_at
        if self.stale:
            raise OptimisticConcurrencyConflict()
        assert expected_version == 0
        return InterchangeabilityGroup(
            group_id=group_id,
            organization_id=context.organization_id,
            member_part_revisions=(revision_ref,),
        )

    def remove_member(
        self,
        context: AssetOperationContext,
        group_id: TypedId,
        *,
        revision_ref: TypedId,
        expected_version: int | None,
        occurred_at: datetime,
    ) -> InterchangeabilityGroup:
        del occurred_at
        assert expected_version == 1
        return InterchangeabilityGroup(
            group_id=group_id,
            organization_id=context.organization_id,
            member_part_revisions=(revision_ref,),
        ).remove_member(revision_ref)


def _override(service: _Service, context: OrganizationContext) -> None:
    main_module.app.dependency_overrides[asset_commands.require_part_edit_interchange] = lambda: (
        context
    )
    main_module.app.dependency_overrides[asset_commands.get_interchangeability_group_service] = (
        lambda: service
    )
    main_module.app.dependency_overrides[asset_commands.get_idempotency_service] = _Idempotency


def _body(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "expected_version": 0,
        "revision_id": REVISION_ID,
        "change": "ADDED",
    }
    body.update(overrides)
    return body


def test_route_is_registered() -> None:
    path = "/v1/asset/interchangeability-groups/{group_id}/members/change"
    assert path in main_module.app.openapi()["paths"]


def test_change_interchangeability_group_requires_authentication() -> None:
    response = TestClient(main_module.app).post(
        ROUTE, json=_body(), headers={"Idempotency-Key": "interchange-auth"}
    )
    assert response.status_code == 401


def test_change_interchangeability_group_rejects_missing_permission(
    monkeypatch: MonkeyPatch,
) -> None:
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
            "Idempotency-Key": "interchange-permission",
        },
    )
    assert response.status_code == 403
    assert response.json()["reason_code"] == "PERMISSAO_AUSENTE"


def test_change_interchangeability_group_adds_member() -> None:
    context = _context()
    _override(_Service(), context)
    response = TestClient(main_module.app).post(
        ROUTE, json=_body(), headers={"Idempotency-Key": "interchange-add"}
    )
    assert response.status_code == 200
    assert response.json() == {
        "group_id": GROUP_ID,
        "member_part_revisions": [REVISION_ID],
        "version": 1,
    }


def test_change_interchangeability_group_removes_member() -> None:
    context = _context()
    _override(_Service(), context)
    response = TestClient(main_module.app).post(
        ROUTE,
        json=_body(expected_version=1, change="REMOVED"),
        headers={"Idempotency-Key": "interchange-remove"},
    )
    assert response.status_code == 200
    assert response.json()["member_part_revisions"] == []
    assert response.json()["version"] == 2


def test_change_interchangeability_group_rejects_stale_version() -> None:
    context = _context()
    service = _Service()
    service.stale = True
    _override(service, context)
    response = TestClient(main_module.app).post(
        ROUTE, json=_body(), headers={"Idempotency-Key": "interchange-stale"}
    )
    assert response.status_code == 409
    assert response.json()["reason_code"] == OptimisticConcurrencyConflict.code
