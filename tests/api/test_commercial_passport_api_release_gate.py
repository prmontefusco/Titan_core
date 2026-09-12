"""API release-gate tests for Commercial Passport F6."""

import importlib
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from pytest import MonkeyPatch

import apps.api.main as main_module
from apps.api import livestock_commercial_passport as commercial_passport_api
from packages.core_domain import AuthenticatedPrincipal, OrganizationContext, PrincipalType
from packages.livestock_application.authorization import DOSSIER_LER, PROPERTY_LER
from packages.livestock_application.commercial_passport import (
    CommercialOpportunity,
    CommercialOpportunityKind,
    CommercialPassport,
    CommercialPassportContext,
    CommercialPassportRequirementDimension,
    CommercialPassportRequirementStatus,
    CommercialRequirementAssessment,
    PropertyCommercialPassportOpportunityInput,
    PropertyCommercialPassportProjectionPort,
    PropertyCommercialPassportService,
)
from packages.shared_kernel import OrganizationId, TypedId

PROPERTY_ID = "00000000-0000-0000-0000-000000000001"
GET_ROUTE = f"/v1/livestock/properties/{PROPERTY_ID}/commercial-passport"
ISSUE_ROUTE = f"/v1/livestock/properties/{PROPERTY_ID}/commercial-passport/issue"


@pytest.fixture(autouse=True)
def _restore_default_app(monkeypatch: MonkeyPatch) -> Iterator[None]:
    yield
    main_module.app.dependency_overrides.clear()
    monkeypatch.delenv("TITAN_COMMERCIAL_PASSPORT_API_ENABLED", raising=False)
    importlib.reload(main_module)


def _paths() -> set[str]:
    return set(main_module.app.openapi()["paths"])


def _context(
    permissions: frozenset[str] = frozenset({PROPERTY_LER, DOSSIER_LER}),
) -> OrganizationContext:
    now = datetime(2026, 9, 11, 12, 0, tzinfo=UTC)
    return OrganizationContext(
        organization_id=OrganizationId.new(),
        authenticated_principal=AuthenticatedPrincipal(
            issuer="https://issuer.example.test",
            subject="commercial-passport-test-user",
            principal_type=PrincipalType.USER,
            authenticated_at=now,
            client_id="commercial-passport-test",
            technical_scopes=frozenset({"openid"}),
        ),
        user_id=TypedId.new("user"),
        actor_id=TypedId.new("actor"),
        membership_id=TypedId.new("membership"),
        role_ids=(TypedId.new("role"),),
        permission_codes=permissions,
        validated_at=now,
    )


def _valid_query() -> dict[str, str]:
    return {
        "reference_time": "2026-09-11T00:00:00Z",
        "knowledge_cutoff": "2026-09-11T00:00:00Z",
    }


def _valid_issue_body() -> dict[str, object]:
    return {
        "reference_time": "2026-09-11T00:00:00Z",
        "knowledge_cutoff": "2026-09-11T00:00:00Z",
        "audience": "internal-audit",
    }


class _ProjectionPipelineStub(PropertyCommercialPassportProjectionPort):
    seen_context: CommercialPassportContext | None = None

    def build_property_passport(
        self,
        *,
        context: CommercialPassportContext,
    ) -> CommercialPassport:
        self.seen_context = context
        return PropertyCommercialPassportService().build(
            context=context,
            opportunities=(
                PropertyCommercialPassportOpportunityInput(
                    opportunity=CommercialOpportunity(
                        code="eu",
                        kind=CommercialOpportunityKind.ECONOMIC_BLOCK,
                        name="European Union",
                        purpose="export-eu",
                        policy_id=TypedId.new("policy"),
                        policy_version=3,
                    ),
                    requirements=(
                        CommercialRequirementAssessment(
                            requirement_code="traceability",
                            label="Traceability",
                            dimension=CommercialPassportRequirementDimension.PROPERTY_READINESS,
                            status=CommercialPassportRequirementStatus.SATISFIED,
                            reason="Evidence is available.",
                            reason_codes=("TRACEABILITY_OK",),
                        ),
                        CommercialRequirementAssessment(
                            requirement_code="environmental-evidence",
                            label="Environmental evidence",
                            dimension=CommercialPassportRequirementDimension.PROPERTY_READINESS,
                            status=CommercialPassportRequirementStatus.MISSING,
                            reason="Required evidence was not supplied.",
                            reason_codes=("MISSING_EVIDENCE",),
                        ),
                    ),
                ),
            ),
        )


def test_commercial_passport_routes_are_absent_by_default(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.delenv("TITAN_COMMERCIAL_PASSPORT_API_ENABLED", raising=False)
    importlib.reload(main_module)

    assert "/v1/livestock/properties/{property_id}/commercial-passport" not in _paths()
    assert "/v1/livestock/properties/{property_id}/commercial-passport/issue" not in _paths()


def test_commercial_passport_routes_are_feature_flagged_and_protected(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("TITAN_COMMERCIAL_PASSPORT_API_ENABLED", "true")
    importlib.reload(main_module)

    assert "/v1/livestock/properties/{property_id}/commercial-passport" in _paths()
    assert "/v1/livestock/properties/{property_id}/commercial-passport/issue" in _paths()

    response = TestClient(main_module.app).get(GET_ROUTE, params=_valid_query())

    assert response.status_code == 401


def test_dynamic_commercial_passport_route_fails_closed_until_pipeline_is_enabled(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("TITAN_COMMERCIAL_PASSPORT_API_ENABLED", "true")
    importlib.reload(main_module)
    main_module.app.dependency_overrides[
        commercial_passport_api.require_commercial_passport_read
    ] = lambda: _context()

    response = TestClient(main_module.app).get(GET_ROUTE, params=_valid_query())

    assert response.status_code == 503
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["reason_code"] == "COMMERCIAL_PASSPORT_PIPELINE_NAO_HABILITADO"


def test_dynamic_commercial_passport_route_returns_projection_from_pipeline(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("TITAN_COMMERCIAL_PASSPORT_API_ENABLED", "true")
    importlib.reload(main_module)
    contexto = _context()
    pipeline = _ProjectionPipelineStub()
    main_module.app.dependency_overrides[
        commercial_passport_api.require_commercial_passport_read
    ] = lambda: contexto
    main_module.app.dependency_overrides[
        commercial_passport_api.get_commercial_passport_projection_pipeline
    ] = lambda: pipeline

    response = TestClient(main_module.app).get(GET_ROUTE, params=_valid_query())

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    payload = response.json()
    assert payload["property_id"] == PROPERTY_ID
    assert payload["reference_time"] == "2026-09-11T00:00:00+00:00"
    assert payload["knowledge_cutoff"] == "2026-09-11T00:00:00+00:00"
    assert payload["opportunities"][0]["opportunity"]["code"] == "eu"
    assert payload["opportunities"][0]["property_readiness"]["interpretation"] == (
        "PARTIALLY_READY"
    )
    assert payload["opportunities"][0]["property_readiness"]["breakdown"]["derived_ratio"] == {
        "satisfied": 1,
        "applicable": 2,
    }
    assert payload["limitations"] == [
        "PROPERTY_COMMERCIAL_PASSPORT_IS_DYNAMIC_PROJECTION",
        "POPULATION_ELIGIBILITY_IS_SEPARATE_FROM_PROPERTY_READINESS",
        "FORMAL_ISSUANCE_REQUIRES_DOSSIER_OR_VERIFICATION_BUNDLE",
    ]
    assert pipeline.seen_context is not None
    assert pipeline.seen_context.organization_id == contexto.organization_id


def test_issue_commercial_passport_route_fails_closed_until_issuance_is_enabled(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("TITAN_COMMERCIAL_PASSPORT_API_ENABLED", "true")
    importlib.reload(main_module)
    main_module.app.dependency_overrides[
        commercial_passport_api.require_commercial_passport_issue
    ] = lambda: _context()

    response = TestClient(main_module.app).post(ISSUE_ROUTE, json=_valid_issue_body())

    assert response.status_code == 503
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"
    assert response.json()["reason_code"] == "COMMERCIAL_PASSPORT_ISSUANCE_NAO_HABILITADA"


def test_commercial_passport_routes_require_utc_temporal_coordinates(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("TITAN_COMMERCIAL_PASSPORT_API_ENABLED", "true")
    importlib.reload(main_module)
    main_module.app.dependency_overrides[
        commercial_passport_api.require_commercial_passport_read
    ] = lambda: _context()

    query = _valid_query()
    query["reference_time"] = "2026-09-11T00:00:00-04:00"
    response = TestClient(main_module.app).get(GET_ROUTE, params=query)

    assert response.status_code == 422
    assert response.json()["reason_code"] == "TEMPO_NAO_UTC"


def test_commercial_passport_routes_reject_knowledge_cutoff_before_reference_time(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("TITAN_COMMERCIAL_PASSPORT_API_ENABLED", "true")
    importlib.reload(main_module)
    main_module.app.dependency_overrides[
        commercial_passport_api.require_commercial_passport_issue
    ] = lambda: _context()
    body = _valid_issue_body()
    body["reference_time"] = "2026-09-11T10:00:00Z"
    body["knowledge_cutoff"] = "2026-09-11T08:00:00Z"

    response = TestClient(main_module.app).post(ISSUE_ROUTE, json=body)

    assert response.status_code == 422
    assert response.json()["reason_code"] == "COMMERCIAL_PASSPORT_REQUEST_INVALIDA"
