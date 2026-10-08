"""Contrato HTTP de `AssertPartApplicability` — Titan Asset A5."""

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
from packages.asset_application.authorization import APPLICABILITY_ASSERT, APPLICABILITY_WITHDRAW
from packages.asset_application.event_recorder import AssetOperationContext
from packages.asset_domain.applicability import Applicability, ApplicabilityTarget
from packages.core_application import IdempotencyExecution, OptimisticConcurrencyConflict
from packages.core_domain import AuthenticatedPrincipal, CanonicalPayload, OrganizationContext
from packages.core_domain.organization_context import PrincipalType
from packages.shared_kernel import OrganizationId, TypedId

ROUTE = "/v1/asset/part-applicability/assertions"
APPLICABILITY_ID = "00000000-0000-0000-0000-000000001005"
WITHDRAW_ROUTE = f"/v1/asset/part-applicability/{APPLICABILITY_ID}/withdraw"
NOW = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)
PART_ID = "00000000-0000-0000-0000-000000001001"
REVISION_ID = "00000000-0000-0000-0000-000000001002"
MODEL_ID = "00000000-0000-0000-0000-000000001003"
EVIDENCE_ID = "00000000-0000-0000-0000-000000001004"


@pytest.fixture(autouse=True)
def _restore_app() -> Iterator[None]:
    yield
    main_module.app.dependency_overrides.clear()
    importlib.reload(main_module)


def _context(
    permissions: frozenset[str] = frozenset({APPLICABILITY_ASSERT}),
) -> OrganizationContext:
    return OrganizationContext(
        organization_id=OrganizationId.new(),
        authenticated_principal=AuthenticatedPrincipal(
            issuer="https://issuer.example.test",
            subject="applicability-test-user",
            principal_type=PrincipalType.USER,
            authenticated_at=NOW,
            client_id="applicability-test",
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
        "part_id": PART_ID,
        "part_revision_id": REVISION_ID,
        "model_id": MODEL_ID,
        "serial_from": "1000",
        "serial_to": "2000",
        "valid_from": "2026-10-08T00:00:00Z",
        "evidence_id": EVIDENCE_ID,
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


class _Service:
    stale = False

    def assert_applicability(
        self,
        context: AssetOperationContext,
        *,
        part_ref: TypedId,
        part_revision_ref: TypedId,
        target: ApplicabilityTarget,
        evidence_ref: TypedId,
        asserted_at: datetime,
        asserted_by: TypedId,
    ) -> Applicability:
        return Applicability(
            applicability_id=TypedId.parse("applicability", "00000000-0000-0000-0000-000000001005"),
            organization_id=context.organization_id,
            part_ref=part_ref,
            part_revision_ref=part_revision_ref,
            target=target,
            evidence_ref=evidence_ref,
            asserted_at=asserted_at,
            asserted_by=asserted_by,
        )

    def withdraw_applicability(
        self,
        context: AssetOperationContext,
        applicability_id: TypedId,
        *,
        reason: str,
        withdrawn_at: datetime,
        expected_version: int | None,
    ) -> Applicability:
        if self.stale:
            raise OptimisticConcurrencyConflict()
        assert expected_version == 1
        applicability = Applicability(
            applicability_id=applicability_id,
            organization_id=context.organization_id,
            part_ref=TypedId.parse("part", PART_ID),
            part_revision_ref=TypedId.parse("part_revision", REVISION_ID),
            target=ApplicabilityTarget(
                model_ref=TypedId.parse("vehicle_model", MODEL_ID),
                variant_ref=None,
                serial_from="1000",
                serial_to="2000",
                valid_from=NOW,
                valid_until=None,
            ),
            evidence_ref=TypedId.parse("evidence", EVIDENCE_ID),
            asserted_at=NOW,
            asserted_by=context.actor_reference.target_id,
        )
        return applicability.withdraw(reason=reason, withdrawn_at=withdrawn_at)


def _override(context: OrganizationContext, service: _Service | None = None) -> None:
    main_module.app.dependency_overrides[asset_commands.require_applicability_assert] = lambda: (
        context
    )
    main_module.app.dependency_overrides[asset_commands.require_applicability_withdraw] = lambda: (
        context
    )
    main_module.app.dependency_overrides[asset_commands.get_applicability_service] = lambda: (
        service or _Service()
    )
    main_module.app.dependency_overrides[asset_commands.get_idempotency_service] = _Idempotency


def test_route_is_registered() -> None:
    assert ROUTE in main_module.app.openapi()["paths"]


def test_assert_part_applicability_requires_authentication() -> None:
    response = TestClient(main_module.app).post(
        ROUTE, json=_body(), headers={"Idempotency-Key": "applicability-auth"}
    )
    assert response.status_code == 401


def test_assert_part_applicability_rejects_missing_permission(monkeypatch: MonkeyPatch) -> None:
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
            "Idempotency-Key": "applicability-permission",
        },
    )
    assert response.status_code == 403
    assert response.json()["reason_code"] == "PERMISSAO_AUSENTE"


def test_assert_part_applicability_returns_evidence_backed_assertion() -> None:
    context = _context()
    _override(context)
    response = TestClient(main_module.app).post(
        ROUTE, json=_body(), headers={"Idempotency-Key": "applicability-success"}
    )
    assert response.status_code == 201
    assert response.json()["part_ref"] == PART_ID
    assert response.json()["part_revision_ref"] == REVISION_ID
    assert response.json()["model_ref"] == MODEL_ID
    assert response.json()["evidence_ref"] == EVIDENCE_ID
    assert response.json()["state"] == "ASSERTED"
    assert response.json()["version"] == 1


def test_assert_part_applicability_requires_evidence() -> None:
    context = _context()
    _override(context)
    body = _body()
    del body["evidence_id"]
    response = TestClient(main_module.app).post(
        ROUTE, json=body, headers={"Idempotency-Key": "applicability-no-evidence"}
    )
    assert response.status_code == 422


def test_assert_part_applicability_rejects_invalid_effectivity() -> None:
    context = _context()
    _override(context)
    response = TestClient(main_module.app).post(
        ROUTE,
        json=_body(valid_until="2026-10-07T00:00:00Z"),
        headers={"Idempotency-Key": "applicability-effectivity"},
    )
    assert response.status_code == 409


def test_withdraw_part_applicability_requires_authentication() -> None:
    response = TestClient(main_module.app).post(
        WITHDRAW_ROUTE,
        json={"expected_version": 1, "reason": "Correção fictícia."},
        headers={"Idempotency-Key": "applicability-withdraw-auth"},
    )
    assert response.status_code == 401


def test_withdraw_part_applicability_rejects_missing_permission(
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
        WITHDRAW_ROUTE,
        json={"expected_version": 1, "reason": "Correção fictícia."},
        headers={
            ORGANIZATION_HEADER: str(context.organization_id.value),
            "Idempotency-Key": "applicability-withdraw-permission",
        },
    )
    assert response.status_code == 403
    assert response.json()["reason_code"] == "PERMISSAO_AUSENTE"


def test_withdraw_part_applicability_returns_withdrawn_state() -> None:
    context = _context(frozenset({APPLICABILITY_WITHDRAW}))
    _override(context)
    response = TestClient(main_module.app).post(
        WITHDRAW_ROUTE,
        json={"expected_version": 1, "reason": "Aplicabilidade lançada por engano."},
        headers={"Idempotency-Key": "applicability-withdraw-success"},
    )
    assert response.status_code == 200
    assert response.json()["state"] == "WITHDRAWN"
    assert response.json()["version"] == 2


def test_withdraw_part_applicability_rejects_stale_version() -> None:
    context = _context(frozenset({APPLICABILITY_WITHDRAW}))
    service = _Service()
    service.stale = True
    _override(context, service)
    response = TestClient(main_module.app).post(
        WITHDRAW_ROUTE,
        json={"expected_version": 1, "reason": "Correção fictícia."},
        headers={"Idempotency-Key": "applicability-withdraw-stale"},
    )
    assert response.status_code == 409
    assert response.json()["reason_code"] == OptimisticConcurrencyConflict.code
