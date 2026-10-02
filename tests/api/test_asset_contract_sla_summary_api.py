"""Contrato HTTP de `GetContractSLASummary` — Titan Asset A5."""

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
from packages.asset_application.authorization import CONTRACT_READ
from packages.asset_application.contract_sla_summary import (
    ContractSLAOperationalSignal,
    ContractSLASummary,
    ContractSLAWorkOrderLine,
    SLIContractSummaryNaoEncontrado,
)
from packages.asset_domain.work_order import WorkOrderState
from packages.core_domain import AuthenticatedPrincipal, OrganizationContext, PrincipalType
from packages.shared_kernel import OrganizationId, TypedId

CONTRACT_ID = "00000000-0000-0000-0000-000000000701"
AS_OF = "2026-10-02T12:00:00Z"
ROUTE = "/v1/asset/contract-sla-summary"


@pytest.fixture(autouse=True)
def _restore_default_app() -> Iterator[None]:
    yield
    main_module.app.dependency_overrides.clear()
    importlib.reload(main_module)


def _context(permissions: frozenset[str] = frozenset({CONTRACT_READ})) -> OrganizationContext:
    now = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)
    return OrganizationContext(
        organization_id=OrganizationId.new(),
        authenticated_principal=AuthenticatedPrincipal(
            issuer="https://issuer.example.test",
            subject="asset-contract-sla-test-user",
            principal_type=PrincipalType.USER,
            authenticated_at=now,
            client_id="asset-contract-sla-test",
            technical_scopes=frozenset({"openid"}),
        ),
        user_id=TypedId.new("user"),
        actor_id=TypedId.new("actor"),
        membership_id=TypedId.new("membership"),
        role_ids=(TypedId.new("role"),),
        permission_codes=permissions,
        validated_at=now,
    )


class _FakeContractSLASummaryService:
    seen_contract_ref: TypedId | None = None
    seen_as_of: datetime | None = None

    def get_contract_sla_summary(
        self, *, contract_ref: TypedId, as_of: datetime | None = None
    ) -> ContractSLASummary:
        self.seen_contract_ref = contract_ref
        self.seen_as_of = as_of
        line = ContractSLAWorkOrderLine(
            work_order_id=TypedId.parse("work_order", "00000000-0000-0000-0000-000000000301"),
            vehicle_ref=TypedId.parse("vehicle", "00000000-0000-0000-0000-000000000401"),
            state=WorkOrderState.WAITING_AUTHORIZATION,
            priority_score=90,
            signals=(
                ContractSLAOperationalSignal.WAITING_AUTHORIZATION,
                ContractSLAOperationalSignal.HIGH_PRIORITY,
            ),
        )
        return ContractSLASummary(
            contract_ref=contract_ref,
            contract_version_no=2,
            covered_vehicle_count=7,
            open_work_order_count=1,
            waiting_material_count=0,
            waiting_authorization_count=1,
            sla_risk_count=1,
            response_sla_duration_seconds=7200,
            repair_sla_duration_seconds=28800,
            lines=(line,),
        )


class _MissingContractSLASummaryService:
    def get_contract_sla_summary(
        self, *, contract_ref: TypedId, as_of: datetime | None = None
    ) -> ContractSLASummary:
        _ = as_of
        raise SLIContractSummaryNaoEncontrado(f"SLIContract '{contract_ref.value}' não encontrado.")


def _fake_connection() -> object:
    return SimpleNamespace()


def test_contract_sla_summary_route_is_registered_in_openapi() -> None:
    paths = set(main_module.app.openapi()["paths"])

    assert "/v1/asset/contract-sla-summary" in paths


def test_contract_sla_summary_requires_authentication() -> None:
    response = TestClient(main_module.app).get(ROUTE, params={"contract_id": CONTRACT_ID})

    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")


def test_contract_sla_summary_rejects_missing_permission(monkeypatch: MonkeyPatch) -> None:
    contexto = _context(permissions=frozenset())
    main_module.app.dependency_overrides[require_authenticated_principal] = lambda: (
        contexto.authenticated_principal
    )
    main_module.app.dependency_overrides[request_connection] = _fake_connection
    main_module.app.dependency_overrides[asset_queries.get_contract_sla_summary_service] = (
        _FakeContractSLASummaryService
    )

    monkeypatch.setattr(
        "apps.api.livestock_dependencies.resolve_organization_context",
        lambda *_args, **_kwargs: contexto,
    )

    response = TestClient(main_module.app).get(
        ROUTE,
        params={"contract_id": CONTRACT_ID},
        headers={ORGANIZATION_HEADER: str(contexto.organization_id.value)},
    )

    assert response.status_code == 403
    assert response.json()["reason_code"] == "PERMISSAO_AUSENTE"


def test_contract_sla_summary_returns_counts_lines_and_passes_filters() -> None:
    contexto = _context()
    service = _FakeContractSLASummaryService()
    main_module.app.dependency_overrides[asset_queries.require_contract_read] = lambda: contexto
    main_module.app.dependency_overrides[asset_queries.get_contract_sla_summary_service] = lambda: (
        service
    )

    response = TestClient(main_module.app).get(
        ROUTE,
        params={"contract_id": CONTRACT_ID, "as_of": AS_OF},
    )

    assert response.status_code == 200
    assert service.seen_contract_ref == TypedId.parse("sli_contract", CONTRACT_ID)
    assert service.seen_as_of == datetime(2026, 10, 2, 12, 0, tzinfo=UTC)
    payload = response.json()
    assert payload["contract_ref"] == CONTRACT_ID
    assert payload["contract_version_no"] == 2
    assert payload["covered_vehicle_count"] == 7
    assert payload["waiting_authorization_count"] == 1
    assert payload["sla_risk_count"] == 1
    assert payload["response_sla_duration_seconds"] == 7200
    assert payload["repair_sla_duration_seconds"] == 28800
    assert payload["lines"][0] == {
        "work_order_id": "00000000-0000-0000-0000-000000000301",
        "vehicle_ref": "00000000-0000-0000-0000-000000000401",
        "state": "WAITING_AUTHORIZATION",
        "priority_score": 90,
        "signals": ["WAITING_AUTHORIZATION", "HIGH_PRIORITY"],
    }


def test_contract_sla_summary_rejects_invalid_contract_identifier() -> None:
    contexto = _context()
    main_module.app.dependency_overrides[asset_queries.require_contract_read] = lambda: contexto
    main_module.app.dependency_overrides[asset_queries.get_contract_sla_summary_service] = (
        _FakeContractSLASummaryService
    )

    response = TestClient(main_module.app).get(ROUTE, params={"contract_id": "nao-e-uuid"})

    assert response.status_code == 422
    assert response.json()["reason_code"] == "IDENTIFICADOR_INVALIDO"


def test_contract_sla_summary_rejects_non_utc_as_of() -> None:
    contexto = _context()
    main_module.app.dependency_overrides[asset_queries.require_contract_read] = lambda: contexto
    main_module.app.dependency_overrides[asset_queries.get_contract_sla_summary_service] = (
        _FakeContractSLASummaryService
    )

    response = TestClient(main_module.app).get(
        ROUTE,
        params={"contract_id": CONTRACT_ID, "as_of": "2026-10-02T08:00:00-04:00"},
    )

    assert response.status_code == 422
    assert response.json()["reason_code"] == "DATA_INVALIDA"


def test_contract_sla_summary_returns_404_when_contract_is_missing() -> None:
    contexto = _context()
    main_module.app.dependency_overrides[asset_queries.require_contract_read] = lambda: contexto
    main_module.app.dependency_overrides[asset_queries.get_contract_sla_summary_service] = (
        _MissingContractSLASummaryService
    )

    response = TestClient(main_module.app).get(ROUTE, params={"contract_id": CONTRACT_ID})

    assert response.status_code == 404
    assert response.json()["reason_code"] == "RECURSO_NAO_ENCONTRADO"
