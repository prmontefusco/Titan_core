"""API release-gate and integration contract tests for Market Optionality AI Explanation route."""

import importlib
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from pytest import MonkeyPatch

import apps.api.main as main_module
from apps.api import (
    livestock_market_optionality_explanation as explanation_api,
)
from apps.api.authentication import require_authenticated_principal
from apps.api.livestock_dependencies import request_connection
from packages.core_domain import (
    AuthenticatedPrincipal,
    OrganizationContext,
    PrincipalType,
)
from packages.livestock_application.authorization import MARKET_OPTION_EXPLAIN
from packages.livestock_application.market_optionality import (
    AnimalMarketOptionExplanationResponse,
    MarketOptionExplanationReleaseDisposition,
    MarketOptionReversibility,
    MarketOptionState,
)
from packages.livestock_domain.animal import Animal, AnimalSex
from packages.shared_kernel import OrganizationId, TypedId

ROUTE_TEMPLATE = "/v1/livestock/animals/{animal_id}/market-optionality/explanation"
ANIMAL_ID = "00000000-0000-0000-0000-000000000001"
ROUTE = ROUTE_TEMPLATE.format(animal_id=ANIMAL_ID)


def _make_animal(organization_id: OrganizationId, animal_id_str: str = ANIMAL_ID) -> Animal:
    return Animal(
        animal_id=TypedId("animal", UUID(animal_id_str)),
        organization_id=organization_id,
        birth_property_id=TypedId.new("rural_property"),
        sex=AnimalSex.MALE,
    )


@pytest.fixture(autouse=True)
def _restore_default_app(monkeypatch: MonkeyPatch) -> Iterator[None]:
    yield
    main_module.app.dependency_overrides.clear()
    monkeypatch.delenv("TITAN_MARKET_OPTIONALITY_AI_EXPLANATION_API_ENABLED", raising=False)
    importlib.reload(main_module)


def _paths() -> set[str]:
    return set(main_module.app.openapi()["paths"])


def _context(
    organization_id: OrganizationId | None = None,
    permissions: frozenset[str] = frozenset({MARKET_OPTION_EXPLAIN}),
) -> OrganizationContext:
    org_id = organization_id or OrganizationId.new()
    now = datetime(2026, 9, 8, 12, 0, tzinfo=UTC)
    return OrganizationContext(
        organization_id=org_id,
        authenticated_principal=AuthenticatedPrincipal(
            issuer="https://issuer.example.test",
            subject="market-optionality-test-user",
            principal_type=PrincipalType.USER,
            authenticated_at=now,
            client_id="market-optionality-test",
            technical_scopes=frozenset({"openid"}),
        ),
        user_id=TypedId.new("user"),
        actor_id=TypedId.new("actor"),
        membership_id=TypedId.new("membership"),
        role_ids=(TypedId.new("role"),),
        permission_codes=permissions,
        validated_at=now,
    )


def _valid_body() -> dict[str, Any]:
    return {
        "policy_id": "00000000-0000-0000-0000-000000000002",
        "policy_version": 1,
        "market_purpose": "EXPORT_EU",
        "reference_time": "2026-09-08T00:00:00Z",
        "knowledge_cutoff": "2026-09-08T00:00:00Z",
    }


def _fake_connection() -> object:
    return object()


def test_market_optionality_ai_explanation_route_is_absent_by_default(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.delenv("TITAN_MARKET_OPTIONALITY_AI_EXPLANATION_API_ENABLED", raising=False)
    importlib.reload(main_module)

    assert "/v1/livestock/animals/{animal_id}/market-optionality/explanation" not in _paths()


def test_market_optionality_ai_explanation_route_is_feature_flagged_and_protected(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("TITAN_MARKET_OPTIONALITY_AI_EXPLANATION_API_ENABLED", "true")
    importlib.reload(main_module)

    assert "/v1/livestock/animals/{animal_id}/market-optionality/explanation" in _paths()

    response = TestClient(main_module.app).post(ROUTE, json=_valid_body())
    assert response.status_code == 401


def test_market_optionality_ai_explanation_route_rejects_without_permission(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("TITAN_MARKET_OPTIONALITY_AI_EXPLANATION_API_ENABLED", "true")
    importlib.reload(main_module)

    context_without_permission = _context(permissions=frozenset())
    main_module.app.dependency_overrides[require_authenticated_principal] = lambda: (
        context_without_permission.authenticated_principal
    )
    main_module.app.dependency_overrides[request_connection] = _fake_connection

    with patch(
        "apps.api.livestock_dependencies.resolve_organization_context",
        return_value=context_without_permission,
    ):
        response = TestClient(main_module.app).post(ROUTE, json=_valid_body())
        assert response.status_code == 403
        assert response.json()["reason_code"] == "PERMISSAO_AUSENTE"


def test_market_optionality_ai_explanation_route_rejects_non_utc_dates(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("TITAN_MARKET_OPTIONALITY_AI_EXPLANATION_API_ENABLED", "true")
    importlib.reload(main_module)

    ctx = _context()
    main_module.app.dependency_overrides[explanation_api.require_market_option_explain] = lambda: (
        ctx
    )
    main_module.app.dependency_overrides[request_connection] = _fake_connection

    animal = _make_animal(ctx.organization_id)

    mock_animal_repo = MagicMock()
    mock_animal_repo.get_by_id.return_value = animal

    with patch(
        "apps.api.livestock_market_optionality_explanation.TransactionalAnimalRepository",
        return_value=mock_animal_repo,
    ):
        body1 = _valid_body()
        body1["reference_time"] = "2026-09-08T00:00:00-03:00"
        r1 = TestClient(main_module.app).post(ROUTE, json=body1)
        assert r1.status_code == 422
        assert r1.json()["reason_code"] == "DATA_INVALIDA"
        assert "reference_time deve estar em UTC" in r1.json()["detail"]

        body2 = _valid_body()
        body2["knowledge_cutoff"] = "2026-09-08T00:00:00-03:00"
        r2 = TestClient(main_module.app).post(ROUTE, json=body2)
        assert r2.status_code == 422
        assert r2.json()["reason_code"] == "DATA_INVALIDA"
        assert "knowledge_cutoff deve estar em UTC" in r2.json()["detail"]

        body3 = _valid_body()
        body3["reference_time"] = "2026-09-08T10:00:00Z"
        body3["knowledge_cutoff"] = "2026-09-08T08:00:00Z"
        r3 = TestClient(main_module.app).post(ROUTE, json=body3)
        assert r3.status_code == 422
        assert r3.json()["reason_code"] == "DATA_INVALIDA"
        assert "knowledge_cutoff não pode ser anterior a reference_time" in r3.json()["detail"]


def test_market_optionality_ai_explanation_route_returns_404_when_animal_missing_or_other_org(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("TITAN_MARKET_OPTIONALITY_AI_EXPLANATION_API_ENABLED", "true")
    importlib.reload(main_module)

    ctx = _context()
    main_module.app.dependency_overrides[explanation_api.require_market_option_explain] = lambda: (
        ctx
    )
    main_module.app.dependency_overrides[request_connection] = _fake_connection

    mock_animal_repo = MagicMock()
    mock_animal_repo.get_by_id.return_value = None

    with patch(
        "apps.api.livestock_market_optionality_explanation.TransactionalAnimalRepository",
        return_value=mock_animal_repo,
    ):
        r1 = TestClient(main_module.app).post(ROUTE, json=_valid_body())
        assert r1.status_code == 404
        assert r1.json()["reason_code"] == "RECURSO_NAO_ENCONTRADO"
        assert r1.json()["detail"] == "Animal não encontrado nesta organização."

    other_org = OrganizationId.new()
    foreign_animal = _make_animal(other_org)
    mock_animal_repo.get_by_id.return_value = foreign_animal

    with patch(
        "apps.api.livestock_market_optionality_explanation.TransactionalAnimalRepository",
        return_value=mock_animal_repo,
    ):
        r2 = TestClient(main_module.app).post(ROUTE, json=_valid_body())
        assert r2.status_code == 404
        assert r2.json()["reason_code"] == "RECURSO_NAO_ENCONTRADO"
        assert r2.json()["detail"] == "Animal não encontrado nesta organização."


def test_market_optionality_ai_explanation_route_returns_200_with_fallback_and_anti_cache_headers(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("TITAN_MARKET_OPTIONALITY_AI_EXPLANATION_API_ENABLED", "true")
    importlib.reload(main_module)

    ctx = _context()
    main_module.app.dependency_overrides[explanation_api.require_market_option_explain] = lambda: (
        ctx
    )
    main_module.app.dependency_overrides[request_connection] = _fake_connection

    animal_id = TypedId("animal", UUID(ANIMAL_ID))
    animal = _make_animal(ctx.organization_id)

    mock_animal_repo = MagicMock()
    mock_animal_repo.get_by_id.return_value = animal

    fake_response = AnimalMarketOptionExplanationResponse(
        subject_id=animal_id,
        market_purpose="EXPORT_EU",
        policy_id=TypedId("policy", UUID("00000000-0000-0000-0000-000000000002")),
        policy_version=1,
        reference_time=datetime(2026, 9, 8, 0, 0, tzinfo=UTC),
        knowledge_cutoff=datetime(2026, 9, 8, 0, 0, tzinfo=UTC),
        canonical_state=MarketOptionState.OPTION_AT_RISK,
        reversibility=MarketOptionReversibility.POTENTIALLY_RESOLVABLE,
        release_disposition=MarketOptionExplanationReleaseDisposition.NOT_RELEASED,
        explanation_text=None,
        canonical_fallback={
            "state": "OPTION_AT_RISK",
            "reversibility": "POTENTIALLY_RESOLVABLE",
        },
        audit_id=None,
    )

    mock_orchestrator = MagicMock()
    mock_orchestrator.explain_for_animal.return_value = fake_response

    with patch(
        "apps.api.livestock_market_optionality_explanation.TransactionalAnimalRepository",
        return_value=mock_animal_repo,
    ):
        with patch(
            "apps.api.livestock_market_optionality_explanation._build_orchestrator",
            return_value=mock_orchestrator,
        ):
            res = TestClient(main_module.app).post(ROUTE, json=_valid_body())

    assert res.status_code == 200
    assert res.headers["cache-control"] == "no-store"
    assert res.headers["pragma"] == "no-cache"

    data = res.json()
    assert data["subject_id"] == ANIMAL_ID
    assert data["canonical_state"] == "OPTION_AT_RISK"
    assert data["reversibility"] == "POTENTIALLY_RESOLVABLE"
    assert data["release_disposition"] == "NOT_RELEASED"
    assert data["explanation_text"] is None
    assert data["canonical_fallback"] == {
        "state": "OPTION_AT_RISK",
        "reversibility": "POTENTIALLY_RESOLVABLE",
    }
    assert data["audit_id"] is None


def test_market_optionality_ai_explanation_route_returns_200_with_approved_release(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("TITAN_MARKET_OPTIONALITY_AI_EXPLANATION_API_ENABLED", "true")
    importlib.reload(main_module)

    ctx = _context()
    main_module.app.dependency_overrides[explanation_api.require_market_option_explain] = lambda: (
        ctx
    )
    main_module.app.dependency_overrides[request_connection] = _fake_connection

    animal_id = TypedId("animal", UUID(ANIMAL_ID))
    animal = _make_animal(ctx.organization_id)

    mock_animal_repo = MagicMock()
    mock_animal_repo.get_by_id.return_value = animal

    audit_id = TypedId.new("audit")
    fake_response = AnimalMarketOptionExplanationResponse(
        subject_id=animal_id,
        market_purpose="EXPORT_EU",
        policy_id=TypedId("policy", UUID("00000000-0000-0000-0000-000000000002")),
        policy_version=1,
        reference_time=datetime(2026, 9, 8, 0, 0, tzinfo=UTC),
        knowledge_cutoff=datetime(2026, 9, 8, 0, 0, tzinfo=UTC),
        canonical_state=MarketOptionState.OPTION_OPEN,
        reversibility=MarketOptionReversibility.NOT_APPLICABLE,
        release_disposition=MarketOptionExplanationReleaseDisposition.RELEASE_APPROVED,
        explanation_text="O animal cumpre os requisitos para exportação.",
        canonical_fallback={"state": "OPTION_OPEN"},
        audit_id=audit_id,
    )

    mock_orchestrator = MagicMock()
    mock_orchestrator.explain_for_animal.return_value = fake_response

    with patch(
        "apps.api.livestock_market_optionality_explanation.TransactionalAnimalRepository",
        return_value=mock_animal_repo,
    ):
        with patch(
            "apps.api.livestock_market_optionality_explanation._build_orchestrator",
            return_value=mock_orchestrator,
        ):
            res = TestClient(main_module.app).post(ROUTE, json=_valid_body())

    assert res.status_code == 200
    assert res.headers["cache-control"] == "no-store"
    assert res.headers["pragma"] == "no-cache"

    data = res.json()
    assert data["subject_id"] == ANIMAL_ID
    assert data["canonical_state"] == "OPTION_OPEN"
    assert data["release_disposition"] == "RELEASE_APPROVED"
    assert data["explanation_text"] == "O animal cumpre os requisitos para exportação."
    assert data["audit_id"] == str(audit_id.value)
