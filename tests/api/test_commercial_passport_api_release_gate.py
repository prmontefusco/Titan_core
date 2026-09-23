"""API release-gate tests for Commercial Passport F6."""

import importlib
from collections.abc import Iterator
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from pytest import MonkeyPatch

import apps.api.main as main_module
from apps.api import livestock_commercial_passport as commercial_passport_api
from apps.api.authentication import require_authenticated_principal
from apps.api.livestock_dependencies import ORGANIZATION_HEADER, request_connection
from packages.core_domain import AuthenticatedPrincipal, OrganizationContext, PrincipalType
from packages.livestock_application.authorization import DOSSIER_LER, PROPERTY_LER
from packages.livestock_application.commercial_passport import (
    CommercialOpportunity,
    CommercialOpportunityKind,
    CommercialPassport,
    CommercialPassportContext,
    CommercialPassportFormalIssuance,
    CommercialPassportRequirementDimension,
    CommercialPassportRequirementStatus,
    CommercialRequirementAssessment,
    PopulationEligibilitySummary,
    PropertyCommercialPassportIssuancePort,
    PropertyCommercialPassportOpportunityInput,
    PropertyCommercialPassportProjectionPort,
    PropertyCommercialPassportService,
)
from packages.shared_kernel import OrganizationId, TypedId

PROPERTY_ID = "00000000-0000-0000-0000-000000000001"
GET_ROUTE = f"/v1/livestock/properties/{PROPERTY_ID}/commercial-passport"
ISSUE_ROUTE = f"/v1/livestock/properties/{PROPERTY_ID}/commercial-passport/issue"
FORBIDDEN_POPULATION_TRACE_KEYS = frozenset(
    {
        "animal_id",
        "animal_ids",
        "membership_id",
        "membership_ids",
        "candidate_animal_id",
        "candidate_animal_ids",
    }
)
FORBIDDEN_UNAUTHENTICATED_KEYS = frozenset(
    {
        "property_id",
        "commercial_passport",
        "opportunities",
        "property_readiness",
        "population_eligibility",
        "gap_analysis",
        "evidence_vault",
        "dossier_id",
        "verification_bundle_id",
        "population_snapshot_digest",
        "selection_criteria_digest",
    }
)


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


def _fake_connection() -> object:
    return object()


def _enable_valid_commercial_passport_pipeline(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("TITAN_COMMERCIAL_PASSPORT_PIPELINE_ENABLED", "true")
    monkeypatch.setenv("TITAN_COMMERCIAL_PASSPORT_OPPORTUNITY_CODE", "market-test")
    monkeypatch.setenv("TITAN_COMMERCIAL_PASSPORT_OPPORTUNITY_NAME", "Mercado teste")
    monkeypatch.setenv("TITAN_COMMERCIAL_PASSPORT_OPPORTUNITY_KIND", "MARKET")
    monkeypatch.setenv("TITAN_COMMERCIAL_PASSPORT_PURPOSE", "market-test")
    monkeypatch.setenv(
        "TITAN_COMMERCIAL_PASSPORT_POLICY_ID",
        "30000000-0000-0000-0000-000000000001",
    )
    monkeypatch.setenv("TITAN_COMMERCIAL_PASSPORT_POLICY_VERSION", "1")


def _assert_no_forbidden_population_trace_keys(
    value: object,
    *,
    path: str = "population_eligibility",
) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            assert key not in FORBIDDEN_POPULATION_TRACE_KEYS, (
                "Commercial Passport population_eligibility must remain aggregate-only; "
                f"found individual identifier field at {child_path}"
            )
            _assert_no_forbidden_population_trace_keys(child, path=child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_no_forbidden_population_trace_keys(child, path=f"{path}[{index}]")


def _assert_no_unauthenticated_commercial_passport_disclosure(
    value: object,
    *,
    path: str = "body",
) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            assert key not in FORBIDDEN_UNAUTHENTICATED_KEYS, (
                "Commercial Passport unauthenticated responses must not disclose "
                f"commercial passport fields; found {child_path}"
            )
            _assert_no_unauthenticated_commercial_passport_disclosure(child, path=child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_no_unauthenticated_commercial_passport_disclosure(
                child,
                path=f"{path}[{index}]",
            )


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


class _PopulationProjectionPipelineStub(PropertyCommercialPassportProjectionPort):
    def build_property_passport(
        self,
        *,
        context: CommercialPassportContext,
    ) -> CommercialPassport:
        return PropertyCommercialPassportService().build(
            context=context,
            opportunities=(
                PropertyCommercialPassportOpportunityInput(
                    opportunity=CommercialOpportunity(
                        code="market-test",
                        kind=CommercialOpportunityKind.MARKET,
                        name="Mercado teste",
                        purpose="market-test",
                        policy_id=TypedId.parse(
                            "policy",
                            "30000000-0000-0000-0000-000000000001",
                        ),
                        policy_version=1,
                    ),
                    requirements=(
                        CommercialRequirementAssessment(
                            requirement_code="market-test:market-readiness-material",
                            label="Market readiness material",
                            dimension=CommercialPassportRequirementDimension.PROPERTY_READINESS,
                            status=CommercialPassportRequirementStatus.SATISFIED,
                            reason="MarketReadiness report is available.",
                            reason_codes=("MARKET_READINESS_REPORT_AVAILABLE",),
                        ),
                    ),
                    population_eligibility=PopulationEligibilitySummary(
                        subject_type="animal",
                        counts_by_status={
                            "READY": 1,
                            "NOT_READY": 0,
                            "CONDITIONED": 0,
                            "INDETERMINATE": 0,
                            "REASSESSMENT_REQUIRED": 0,
                            "NOT_EVALUATED": 2,
                        },
                        limitations=("derived from MarketReadiness; not a Decision",),
                        source_report_reference="market-readiness-report:test",
                    ),
                ),
            ),
        )


class _IssuancePipelineStub(PropertyCommercialPassportIssuancePort):
    seen_context: CommercialPassportContext | None = None
    seen_audience: str | None = None

    def issue_property_passport(
        self,
        *,
        context: CommercialPassportContext,
        audience: str,
        issued_at: datetime,
    ) -> CommercialPassportFormalIssuance:
        self.seen_context = context
        self.seen_audience = audience
        return cast(
            CommercialPassportFormalIssuance,
            SimpleNamespace(
                dossier=SimpleNamespace(
                    dossier_id=TypedId.parse(
                        "dossier",
                        "10000000-0000-0000-0000-000000000001",
                    ),
                    dossier_hash="dossier-hash",
                ),
                verification_bundle=SimpleNamespace(
                    manifest=SimpleNamespace(
                        bundle_id=TypedId.parse(
                            "verification_bundle",
                            "20000000-0000-0000-0000-000000000001",
                        ),
                        manifest_digest="manifest-digest",
                    ),
                ),
            ),
        )


def test_commercial_passport_routes_are_absent_by_default(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.delenv("TITAN_COMMERCIAL_PASSPORT_API_ENABLED", raising=False)
    importlib.reload(main_module)

    assert "/v1/livestock/properties/{property_id}/commercial-passport" not in _paths()
    assert "/v1/livestock/properties/{property_id}/commercial-passport/issue" not in _paths()

    client = TestClient(main_module.app)
    for response in (
        client.get(GET_ROUTE, params=_valid_query()),
        client.post(ISSUE_ROUTE, json=_valid_issue_body()),
    ):
        assert response.status_code == 404
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["pragma"] == "no-cache"
        assert response.headers["content-type"].startswith("application/problem+json")
        _assert_no_unauthenticated_commercial_passport_disclosure(response.json())


def test_commercial_passport_routes_are_feature_flagged_and_protected(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("TITAN_COMMERCIAL_PASSPORT_API_ENABLED", "true")
    importlib.reload(main_module)

    assert "/v1/livestock/properties/{property_id}/commercial-passport" in _paths()
    assert "/v1/livestock/properties/{property_id}/commercial-passport/issue" in _paths()

    response = TestClient(main_module.app).get(GET_ROUTE, params=_valid_query())

    assert response.status_code == 401
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"
    assert response.headers["content-type"].startswith("application/problem+json")
    _assert_no_unauthenticated_commercial_passport_disclosure(response.json())


def test_commercial_passport_issue_route_does_not_disclose_without_authentication(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("TITAN_COMMERCIAL_PASSPORT_API_ENABLED", "true")
    importlib.reload(main_module)

    response = TestClient(main_module.app).post(ISSUE_ROUTE, json=_valid_issue_body())

    assert response.status_code == 401
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"
    assert response.headers["content-type"].startswith("application/problem+json")
    _assert_no_unauthenticated_commercial_passport_disclosure(response.json())


def test_commercial_passport_routes_do_not_disclose_without_permission(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("TITAN_COMMERCIAL_PASSPORT_API_ENABLED", "true")
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
        client = TestClient(main_module.app)
        for response in (
            client.get(GET_ROUTE, params=_valid_query()),
            client.post(ISSUE_ROUTE, json=_valid_issue_body()),
        ):
            assert response.status_code == 403
            assert response.headers["cache-control"] == "no-store"
            assert response.headers["pragma"] == "no-cache"
            assert response.headers["content-type"].startswith("application/problem+json")
            assert response.json()["reason_code"] == "PERMISSAO_AUSENTE"
            _assert_no_unauthenticated_commercial_passport_disclosure(response.json())


def test_commercial_passport_routes_require_organization_context_without_cache(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("TITAN_COMMERCIAL_PASSPORT_API_ENABLED", "true")
    importlib.reload(main_module)

    contexto = _context()
    main_module.app.dependency_overrides[require_authenticated_principal] = lambda: (
        contexto.authenticated_principal
    )
    main_module.app.dependency_overrides[request_connection] = _fake_connection

    client = TestClient(main_module.app)
    for response in (
        client.get(GET_ROUTE, params=_valid_query()),
        client.post(ISSUE_ROUTE, json=_valid_issue_body()),
    ):
        assert response.status_code == 400
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["pragma"] == "no-cache"
        assert response.headers["content-type"].startswith("application/problem+json")
        assert response.json()["reason_code"] == "ORGANIZACAO_NAO_INFORMADA"
        _assert_no_unauthenticated_commercial_passport_disclosure(response.json())


def test_commercial_passport_routes_reject_malformed_organization_context_without_cache(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("TITAN_COMMERCIAL_PASSPORT_API_ENABLED", "true")
    importlib.reload(main_module)

    contexto = _context()
    main_module.app.dependency_overrides[require_authenticated_principal] = lambda: (
        contexto.authenticated_principal
    )
    main_module.app.dependency_overrides[request_connection] = _fake_connection

    headers = {ORGANIZATION_HEADER: "nao-e-uuid"}
    client = TestClient(main_module.app)
    for response in (
        client.get(GET_ROUTE, params=_valid_query(), headers=headers),
        client.post(ISSUE_ROUTE, json=_valid_issue_body(), headers=headers),
    ):
        assert response.status_code == 400
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["pragma"] == "no-cache"
        assert response.headers["content-type"].startswith("application/problem+json")
        assert response.json()["reason_code"] == "ORGANIZACAO_INVALIDA"
        _assert_no_unauthenticated_commercial_passport_disclosure(response.json())


def test_commercial_passport_method_errors_are_not_cacheable(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("TITAN_COMMERCIAL_PASSPORT_API_ENABLED", "true")
    importlib.reload(main_module)

    response = TestClient(main_module.app).patch(GET_ROUTE, json={})

    assert response.status_code == 405
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["reason_code"] == "METODO_NAO_PERMITIDO"
    _assert_no_unauthenticated_commercial_passport_disclosure(response.json())


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


def test_dynamic_commercial_passport_dependency_builds_configured_pipeline(
    monkeypatch: MonkeyPatch,
) -> None:
    _enable_valid_commercial_passport_pipeline(monkeypatch)

    pipeline = commercial_passport_api.get_commercial_passport_projection_pipeline()

    assert pipeline is not None


@pytest.mark.parametrize(
    ("env_name", "env_value"),
    (
        ("TITAN_COMMERCIAL_PASSPORT_OPPORTUNITY_CODE", ""),
        ("TITAN_COMMERCIAL_PASSPORT_POLICY_ID", "nao-e-uuid"),
        ("TITAN_COMMERCIAL_PASSPORT_POLICY_VERSION", "versao-invalida"),
        ("TITAN_COMMERCIAL_PASSPORT_OPPORTUNITY_KIND", "TIPO_INEXISTENTE"),
    ),
)
def test_dynamic_commercial_passport_dependency_fails_closed_with_invalid_configuration(
    monkeypatch: MonkeyPatch,
    env_name: str,
    env_value: str,
) -> None:
    _enable_valid_commercial_passport_pipeline(monkeypatch)
    monkeypatch.setenv(env_name, env_value)

    pipeline = commercial_passport_api.get_commercial_passport_projection_pipeline()

    assert pipeline is None


def test_dynamic_commercial_passport_route_fails_closed_with_partial_pipeline_configuration(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("TITAN_COMMERCIAL_PASSPORT_API_ENABLED", "true")
    monkeypatch.setenv("TITAN_COMMERCIAL_PASSPORT_PIPELINE_ENABLED", "true")
    monkeypatch.setenv("TITAN_COMMERCIAL_PASSPORT_OPPORTUNITY_CODE", "market-test")
    importlib.reload(main_module)
    main_module.app.dependency_overrides[
        commercial_passport_api.require_commercial_passport_read
    ] = lambda: _context()

    response = TestClient(main_module.app).get(GET_ROUTE, params=_valid_query())

    assert response.status_code == 503
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["reason_code"] == "COMMERCIAL_PASSPORT_PIPELINE_NAO_HABILITADO"


def test_dynamic_commercial_passport_route_returns_population_summary_from_pipeline(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("TITAN_COMMERCIAL_PASSPORT_API_ENABLED", "true")
    importlib.reload(main_module)
    main_module.app.dependency_overrides[
        commercial_passport_api.require_commercial_passport_read
    ] = lambda: _context()
    main_module.app.dependency_overrides[
        commercial_passport_api.get_commercial_passport_projection_pipeline
    ] = lambda: _PopulationProjectionPipelineStub()

    response = TestClient(main_module.app).get(GET_ROUTE, params=_valid_query())

    assert response.status_code == 200
    payload = response.json()
    assert payload["property_id"] == PROPERTY_ID
    opportunity = payload["opportunities"][0]
    assert opportunity["opportunity"]["code"] == "market-test"
    assert opportunity["opportunity"]["policy_id"] == "30000000-0000-0000-0000-000000000001"
    requirement = opportunity["property_readiness"]["requirements"][0]
    assert requirement["status"] == "SATISFIED"
    assert requirement["reason_codes"] == ["MARKET_READINESS_REPORT_AVAILABLE"]
    assert opportunity["population_eligibility"]["total_count"] == 3
    assert opportunity["population_eligibility"]["counts_by_status"]["READY"] == 1
    assert opportunity["population_eligibility"]["counts_by_status"]["NOT_EVALUATED"] == 2
    assert set(opportunity["population_eligibility"]) == {
        "subject_type",
        "counts_by_status",
        "total_count",
        "source_report_reference",
        "population_snapshot_digest",
        "selection_criteria_digest",
        "commercial_window",
        "limitations",
    }
    _assert_no_forbidden_population_trace_keys(opportunity["population_eligibility"])
    assert "FORMAL_ISSUANCE_REQUIRES_DOSSIER_OR_VERIFICATION_BUNDLE" in payload["limitations"]


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


def test_issue_commercial_passport_route_returns_formal_issuance_envelope(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("TITAN_COMMERCIAL_PASSPORT_API_ENABLED", "true")
    importlib.reload(main_module)
    contexto = _context()
    pipeline = _IssuancePipelineStub()
    main_module.app.dependency_overrides[
        commercial_passport_api.require_commercial_passport_issue
    ] = lambda: contexto
    main_module.app.dependency_overrides[
        commercial_passport_api.get_commercial_passport_issuance_pipeline
    ] = lambda: pipeline

    response = TestClient(main_module.app).post(ISSUE_ROUTE, json=_valid_issue_body())

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    payload = response.json()
    assert payload["property_id"] == PROPERTY_ID
    assert payload["dossier_id"] == "10000000-0000-0000-0000-000000000001"
    assert payload["dossier_hash"] == "dossier-hash"
    assert payload["verification_bundle_id"] == "20000000-0000-0000-0000-000000000001"
    assert payload["verification_manifest_digest"] == "manifest-digest"
    assert payload["audience"] == "internal-audit"
    assert pipeline.seen_context is not None
    assert pipeline.seen_context.organization_id == contexto.organization_id
    assert pipeline.seen_audience == "internal-audit"


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
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["reason_code"] == "TEMPO_NAO_UTC"
    _assert_no_unauthenticated_commercial_passport_disclosure(response.json())


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
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["reason_code"] == "COMMERCIAL_PASSPORT_REQUEST_INVALIDA"
    _assert_no_unauthenticated_commercial_passport_disclosure(response.json())


def test_commercial_passport_contract_validation_errors_are_not_cacheable(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("TITAN_COMMERCIAL_PASSPORT_API_ENABLED", "true")
    importlib.reload(main_module)
    main_module.app.dependency_overrides[
        commercial_passport_api.require_commercial_passport_read
    ] = lambda: _context()

    query = _valid_query()
    del query["knowledge_cutoff"]
    response = TestClient(main_module.app).get(GET_ROUTE, params=query)

    assert response.status_code == 422
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["reason_code"] == "ENTRADA_INVALIDA"
    _assert_no_unauthenticated_commercial_passport_disclosure(response.json())
