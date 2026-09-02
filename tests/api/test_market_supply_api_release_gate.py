"""API release-gate tests for Market Supply F3.5 route exposure."""

import importlib
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from pytest import MonkeyPatch

import apps.api.main as main_module
from apps.api import livestock_market_supply as market_supply_api
from packages.core_domain import AuthenticatedPrincipal, OrganizationContext, PrincipalType
from packages.livestock_application.authorization import MARKET_SUPPLY_AGGREGATE_ASSESS
from packages.shared_kernel import OrganizationId, TypedId

ROUTE = "/v1/livestock/market-supply/aggregate-assessments"


@pytest.fixture(autouse=True)
def _restore_default_app(monkeypatch: MonkeyPatch) -> Iterator[None]:
    yield
    main_module.app.dependency_overrides.clear()
    monkeypatch.delenv("TITAN_MARKET_SUPPLY_AGGREGATE_API_ENABLED", raising=False)
    importlib.reload(main_module)


def _paths() -> set[str]:
    return set(main_module.app.openapi()["paths"])


def _context() -> OrganizationContext:
    organization_id = OrganizationId.new()
    now = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
    return OrganizationContext(
        organization_id=organization_id,
        authenticated_principal=AuthenticatedPrincipal(
            issuer="https://issuer.example.test",
            subject="market-supply-test-user",
            principal_type=PrincipalType.USER,
            authenticated_at=now,
            client_id="market-supply-test",
            technical_scopes=frozenset({"openid"}),
        ),
        user_id=TypedId.new("user"),
        actor_id=TypedId.new("actor"),
        membership_id=TypedId.new("membership"),
        role_ids=(TypedId.new("role"),),
        permission_codes=frozenset({MARKET_SUPPLY_AGGREGATE_ASSESS}),
        validated_at=now,
    )


def _valid_body() -> dict[str, object]:
    return {
        "policy_id": "00000000-0000-0000-0000-000000000001",
        "policy_version": 1,
        "purpose": "MARKET_SUPPLY_AGGREGATE_ASSESSMENT",
        "quantity": 8000,
        "commercial_window": {
            "from": "2026-09-01T00:00:00Z",
            "until": "2026-10-15T00:00:00Z",
        },
        "reference_time": "2026-08-31T00:00:00Z",
        "knowledge_cutoff": "2026-08-31T00:00:00Z",
        "candidate_criteria": {
            "subject_type": "animal",
            "required_tags": [],
        },
    }


def _configure_privacy_profile(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("TITAN_MARKET_SUPPLY_PRIVACY_PROFILE_ID", "market-supply-test")
    monkeypatch.setenv("TITAN_MARKET_SUPPLY_PRIVACY_POLICY_VERSION", "1")
    monkeypatch.setenv("TITAN_MARKET_SUPPLY_PRIVACY_MINIMUM_ORGANIZATIONS", "1")
    monkeypatch.setenv("TITAN_MARKET_SUPPLY_PRIVACY_MINIMUM_PROPERTIES", "1")
    monkeypatch.setenv("TITAN_MARKET_SUPPLY_PRIVACY_MINIMUM_SUBJECTS", "1")
    monkeypatch.setenv("TITAN_MARKET_SUPPLY_PRIVACY_MAX_FILTER_COUNT_WITHOUT_REVIEW", "10")
    monkeypatch.setenv("TITAN_MARKET_SUPPLY_PRIVACY_REPEATED_QUERY_WINDOW_SECONDS", "60")


def test_market_supply_aggregate_route_is_absent_by_default(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.delenv("TITAN_MARKET_SUPPLY_AGGREGATE_API_ENABLED", raising=False)
    importlib.reload(main_module)

    assert ROUTE not in _paths()


def test_market_supply_aggregate_route_is_feature_flagged_and_protected(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("TITAN_MARKET_SUPPLY_AGGREGATE_API_ENABLED", "true")
    importlib.reload(main_module)

    assert ROUTE in _paths()

    response = TestClient(main_module.app).post(
        ROUTE,
        headers={"Idempotency-Key": "market-supply-test-key"},
        json=_valid_body(),
    )

    assert response.status_code == 401


def test_market_supply_aggregate_route_fails_closed_without_privacy_profile(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("TITAN_MARKET_SUPPLY_AGGREGATE_API_ENABLED", "true")
    importlib.reload(main_module)
    main_module.app.dependency_overrides[
        market_supply_api.require_market_supply_aggregate_assess
    ] = _context

    response = TestClient(main_module.app).post(
        ROUTE,
        headers={"Idempotency-Key": "market-supply-test-key"},
        json=_valid_body(),
    )

    assert response.status_code == 503
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["reason_code"] == "MARKET_SUPPLY_PRIVACY_PROFILE_NAO_CONFIGURADO"


def test_market_supply_aggregate_route_fails_closed_until_pipeline_is_enabled(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("TITAN_MARKET_SUPPLY_AGGREGATE_API_ENABLED", "true")
    _configure_privacy_profile(monkeypatch)
    importlib.reload(main_module)
    main_module.app.dependency_overrides[
        market_supply_api.require_market_supply_aggregate_assess
    ] = _context

    response = TestClient(main_module.app).post(
        ROUTE,
        headers={"Idempotency-Key": "market-supply-test-key"},
        json=_valid_body(),
    )

    assert response.status_code == 503
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["reason_code"] == "MARKET_SUPPLY_PIPELINE_NAO_HABILITADO"


def test_market_supply_aggregate_route_requires_idempotency_key_after_auth(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("TITAN_MARKET_SUPPLY_AGGREGATE_API_ENABLED", "true")
    importlib.reload(main_module)
    main_module.app.dependency_overrides[
        market_supply_api.require_market_supply_aggregate_assess
    ] = _context

    response = TestClient(main_module.app).post(ROUTE, json=_valid_body())

    assert response.status_code == 422


def test_market_supply_aggregate_route_requires_utc_temporal_coordinates(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("TITAN_MARKET_SUPPLY_AGGREGATE_API_ENABLED", "true")
    importlib.reload(main_module)
    main_module.app.dependency_overrides[
        market_supply_api.require_market_supply_aggregate_assess
    ] = _context
    body = _valid_body()
    body["reference_time"] = "2026-08-31T00:00:00-04:00"

    response = TestClient(main_module.app).post(
        ROUTE,
        headers={"Idempotency-Key": "market-supply-test-key"},
        json=body,
    )

    assert response.status_code == 422
    assert response.json()["reason_code"] == "TEMPO_NAO_UTC"


def test_market_supply_aggregate_route_rejects_invalid_request_context(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("TITAN_MARKET_SUPPLY_AGGREGATE_API_ENABLED", "true")
    importlib.reload(main_module)
    main_module.app.dependency_overrides[
        market_supply_api.require_market_supply_aggregate_assess
    ] = _context
    body = _valid_body()
    body["commercial_window"] = {
        "from": "2026-10-15T00:00:00Z",
        "until": "2026-09-01T00:00:00Z",
    }

    response = TestClient(main_module.app).post(
        ROUTE,
        headers={"Idempotency-Key": "market-supply-test-key"},
        json=body,
    )

    assert response.status_code == 422
    assert response.json()["reason_code"] == "MARKET_SUPPLY_REQUEST_INVALIDA"
