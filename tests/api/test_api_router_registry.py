"""Contratos do registro aditivo de routers HTTP."""

import importlib
from collections.abc import Iterator

import pytest
from pytest import MonkeyPatch

import apps.api.main as main_module


@pytest.fixture(autouse=True)
def _restore_default_app(monkeypatch: MonkeyPatch) -> Iterator[None]:
    yield
    monkeypatch.delenv("TITAN_MARKET_SUPPLY_AGGREGATE_API_ENABLED", raising=False)
    monkeypatch.delenv("TITAN_MARKET_OPTIONALITY_AI_EXPLANATION_API_ENABLED", raising=False)
    monkeypatch.delenv("TITAN_COMMERCIAL_PASSPORT_API_ENABLED", raising=False)
    importlib.reload(main_module)


def _paths() -> set[str]:
    return set(main_module.app.openapi()["paths"])


def test_registry_keeps_existing_always_on_livestock_routes() -> None:
    importlib.reload(main_module)

    paths = _paths()

    assert "/v1/livestock/animals" in paths
    assert "/v1/livestock/treatments" in paths
    assert "/v1/livestock/properties/{property_id}" in paths
    assert "/v1/livestock/transformations/slaughter" in paths
    assert "/v1/livestock/entity-type-requests" in paths


def test_registry_preserves_feature_flagged_routes(monkeypatch: MonkeyPatch) -> None:
    importlib.reload(main_module)

    default_paths = _paths()
    assert "/v1/livestock/market-supply/aggregate-assessments" not in default_paths
    assert "/v1/livestock/animals/{animal_id}/market-optionality/explanation" not in default_paths
    assert "/v1/livestock/properties/{property_id}/commercial-passport" not in default_paths

    monkeypatch.setenv("TITAN_MARKET_SUPPLY_AGGREGATE_API_ENABLED", "true")
    monkeypatch.setenv("TITAN_MARKET_OPTIONALITY_AI_EXPLANATION_API_ENABLED", "true")
    monkeypatch.setenv("TITAN_COMMERCIAL_PASSPORT_API_ENABLED", "true")
    importlib.reload(main_module)

    flagged_paths = _paths()
    assert "/v1/livestock/market-supply/aggregate-assessments" in flagged_paths
    assert "/v1/livestock/animals/{animal_id}/market-optionality/explanation" in flagged_paths
    assert "/v1/livestock/properties/{property_id}/commercial-passport" in flagged_paths
