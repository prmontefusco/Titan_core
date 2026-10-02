"""Contrato HTTP de `ResolvePartApplicability` — Titan Asset A5."""

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
from packages.asset_application.authorization import APPLICABILITY_READ
from packages.asset_application.part_applicability_query import (
    PartApplicabilityResolution,
    PartApplicabilityVehicleNaoEncontrado,
)
from packages.asset_domain.applicability import Applicability, ApplicabilityTarget
from packages.asset_domain.vehicle import AssetOwnership, Vehicle, VehicleIdentifiers
from packages.core_domain import AuthenticatedPrincipal, OrganizationContext, PrincipalType
from packages.shared_kernel import OrganizationId, TypedId

PART_ID = "00000000-0000-0000-0000-000000000811"
PART_REVISION_ID = "00000000-0000-0000-0000-000000000812"
VEHICLE_ID = "00000000-0000-0000-0000-000000000401"
MODEL_ID = "00000000-0000-0000-0000-000000000801"
EVIDENCE_ID = "00000000-0000-0000-0000-000000000901"
APPLICABILITY_ID = "00000000-0000-0000-0000-000000000902"
INSTANT = "2026-10-02T12:00:00Z"
ROUTE = "/v1/asset/part-applicability"
OCCURRED_AT = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _restore_default_app() -> Iterator[None]:
    yield
    main_module.app.dependency_overrides.clear()
    importlib.reload(main_module)


def _context(
    permissions: frozenset[str] = frozenset({APPLICABILITY_READ}),
) -> OrganizationContext:
    return OrganizationContext(
        organization_id=OrganizationId.new(),
        authenticated_principal=AuthenticatedPrincipal(
            issuer="https://issuer.example.test",
            subject="asset-part-applicability-test-user",
            principal_type=PrincipalType.USER,
            authenticated_at=OCCURRED_AT,
            client_id="asset-part-applicability-test",
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
    return Vehicle(
        vehicle_id=vehicle_id,
        organization_id=OrganizationId.new(),
        model_ref=TypedId.parse("vehicle_model", MODEL_ID),
        identifiers=VehicleIdentifiers(serial_number="SN-100"),
        ownership=AssetOwnership.COMPANY,
        created_at=OCCURRED_AT,
    )


def _applicability(part_ref: TypedId) -> Applicability:
    return Applicability(
        applicability_id=TypedId.parse("applicability", APPLICABILITY_ID),
        organization_id=OrganizationId.new(),
        part_ref=part_ref,
        part_revision_ref=TypedId.parse("part_revision", PART_REVISION_ID),
        target=ApplicabilityTarget(
            model_ref=TypedId.parse("vehicle_model", MODEL_ID),
            variant_ref=None,
            serial_from="SN-001",
            serial_to="SN-999",
            valid_from=OCCURRED_AT,
            valid_until=None,
        ),
        evidence_ref=TypedId.parse("evidence", EVIDENCE_ID),
        asserted_at=OCCURRED_AT,
        asserted_by=TypedId.parse("user", "00000000-0000-0000-0000-000000000903"),
    )


class _FakePartApplicabilityQueryService:
    seen_part_ref: TypedId | None = None
    seen_vehicle_id: TypedId | None = None
    seen_instant: datetime | None = None

    def resolve(
        self, *, part_ref: TypedId, vehicle_id: TypedId, instant: datetime
    ) -> PartApplicabilityResolution:
        self.seen_part_ref = part_ref
        self.seen_vehicle_id = vehicle_id
        self.seen_instant = instant
        return PartApplicabilityResolution(
            part_ref=part_ref,
            vehicle=_vehicle(vehicle_id),
            instant=instant,
            assertions=(_applicability(part_ref),),
        )


class _MissingVehiclePartApplicabilityQueryService:
    def resolve(
        self, *, part_ref: TypedId, vehicle_id: TypedId, instant: datetime
    ) -> PartApplicabilityResolution:
        raise PartApplicabilityVehicleNaoEncontrado(f"Vehicle '{vehicle_id.value}' não encontrado.")


def _fake_connection() -> object:
    return SimpleNamespace()


def _params(
    *,
    part_id: str = PART_ID,
    vehicle_id: str = VEHICLE_ID,
    instant: str = INSTANT,
) -> dict[str, str]:
    return {"part_id": part_id, "vehicle_id": vehicle_id, "instant": instant}


def test_part_applicability_route_is_registered_in_openapi() -> None:
    paths = set(main_module.app.openapi()["paths"])

    assert "/v1/asset/part-applicability" in paths


def test_part_applicability_requires_authentication() -> None:
    response = TestClient(main_module.app).get(ROUTE, params=_params())

    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")


def test_part_applicability_rejects_missing_permission(monkeypatch: MonkeyPatch) -> None:
    contexto = _context(permissions=frozenset())
    main_module.app.dependency_overrides[require_authenticated_principal] = lambda: (
        contexto.authenticated_principal
    )
    main_module.app.dependency_overrides[request_connection] = _fake_connection
    main_module.app.dependency_overrides[asset_queries.get_part_applicability_query_service] = (
        _FakePartApplicabilityQueryService
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


def test_part_applicability_returns_assertions_with_evidence() -> None:
    contexto = _context()
    service = _FakePartApplicabilityQueryService()
    main_module.app.dependency_overrides[asset_queries.require_applicability_read] = lambda: (
        contexto
    )
    main_module.app.dependency_overrides[asset_queries.get_part_applicability_query_service] = (
        lambda: service
    )

    response = TestClient(main_module.app).get(ROUTE, params=_params())

    assert response.status_code == 200
    assert service.seen_part_ref == TypedId.parse("part", PART_ID)
    assert service.seen_vehicle_id == TypedId.parse("vehicle", VEHICLE_ID)
    assert service.seen_instant == OCCURRED_AT
    payload = response.json()
    assert payload["part_ref"] == PART_ID
    assert payload["vehicle_id"] == VEHICLE_ID
    assert payload["instant"] == INSTANT
    assert payload["assertions"][0]["applicability_id"] == APPLICABILITY_ID
    assert payload["assertions"][0]["part_revision_ref"] == PART_REVISION_ID
    assert payload["assertions"][0]["evidence_ref"] == EVIDENCE_ID


def test_part_applicability_rejects_invalid_part_identifier() -> None:
    contexto = _context()
    main_module.app.dependency_overrides[asset_queries.require_applicability_read] = lambda: (
        contexto
    )
    main_module.app.dependency_overrides[asset_queries.get_part_applicability_query_service] = (
        _FakePartApplicabilityQueryService
    )

    response = TestClient(main_module.app).get(
        ROUTE,
        params=_params(part_id="nao-e-uuid"),
    )

    assert response.status_code == 422
    assert response.json()["reason_code"] == "IDENTIFICADOR_INVALIDO"


def test_part_applicability_rejects_non_utc_instant() -> None:
    contexto = _context()
    main_module.app.dependency_overrides[asset_queries.require_applicability_read] = lambda: (
        contexto
    )
    main_module.app.dependency_overrides[asset_queries.get_part_applicability_query_service] = (
        _FakePartApplicabilityQueryService
    )

    response = TestClient(main_module.app).get(
        ROUTE,
        params=_params(instant="2026-10-02T08:00:00-04:00"),
    )

    assert response.status_code == 422
    assert response.json()["reason_code"] == "DATA_INVALIDA"


def test_part_applicability_returns_404_when_vehicle_is_missing() -> None:
    contexto = _context()
    main_module.app.dependency_overrides[asset_queries.require_applicability_read] = lambda: (
        contexto
    )
    main_module.app.dependency_overrides[asset_queries.get_part_applicability_query_service] = (
        _MissingVehiclePartApplicabilityQueryService
    )

    response = TestClient(main_module.app).get(ROUTE, params=_params())

    assert response.status_code == 404
    assert response.json()["reason_code"] == "RECURSO_NAO_ENCONTRADO"
