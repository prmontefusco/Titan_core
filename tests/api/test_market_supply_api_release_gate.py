"""API release-gate tests for Market Supply F3.5 route exposure."""

import importlib
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from pytest import MonkeyPatch

import apps.api.main as main_module

ROUTE = "/v1/livestock/market-supply/aggregate-assessments"


@pytest.fixture(autouse=True)
def _restore_default_app(monkeypatch: MonkeyPatch) -> Iterator[None]:
    yield
    monkeypatch.delenv("TITAN_MARKET_SUPPLY_AGGREGATE_API_ENABLED", raising=False)
    importlib.reload(main_module)


def _paths() -> set[str]:
    return set(main_module.app.openapi()["paths"])


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
        json={
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
        },
    )

    assert response.status_code == 401
