"""Contrato HTTP de `GetContractContextForVehicle` — Titan Asset A5."""

import importlib
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pytest import MonkeyPatch

import apps.api.main as main_module
from apps.api.asset import queries as asset_queries
from apps.api.authentication import require_authenticated_principal
from apps.api.livestock_dependencies import ORGANIZATION_HEADER, request_connection
from packages.asset_application.authorization import CONTRACT_READ
from packages.asset_application.contract_context_query import (
    ContractContextAmbiguo,
    ContractContextForVehicle,
    ContractContextNaoEncontrado,
)
from packages.asset_domain.sustainment_contract import (
    SLA,
    ContractScope,
    ContractVersion,
    CoverageLine,
    KnownValidInterval,
    ServiceLimits,
    SLIContract,
)
from packages.asset_domain.vehicle import AssetOwnership, Vehicle, VehicleIdentifiers
from packages.core_domain import AuthenticatedPrincipal, OrganizationContext, PrincipalType
from packages.shared_kernel import OrganizationId, TypedId

VEHICLE_ID = "00000000-0000-0000-0000-000000000401"
CONTRACT_ID = "00000000-0000-0000-0000-000000000501"
PART_ID = "00000000-0000-0000-0000-000000000811"
INSTANT = "2026-10-03T12:00:00Z"
ROUTE = f"/v1/asset/vehicles/{VEHICLE_ID}/contract-context"
OCCURRED_AT = datetime(2026, 10, 3, 12, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _restore_default_app() -> Iterator[None]:
    yield
    main_module.app.dependency_overrides.clear()
    importlib.reload(main_module)


def _context(permissions: frozenset[str] = frozenset({CONTRACT_READ})) -> OrganizationContext:
    return OrganizationContext(
        organization_id=OrganizationId.new(),
        authenticated_principal=AuthenticatedPrincipal(
            issuer="https://issuer.example.test",
            subject="asset-contract-context-test-user",
            principal_type=PrincipalType.USER,
            authenticated_at=OCCURRED_AT,
            client_id="asset-contract-context-test",
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
        model_ref=TypedId.parse("vehicle_model", "00000000-0000-0000-0000-000000000801"),
        identifiers=VehicleIdentifiers(serial_number="SN-001"),
        ownership=AssetOwnership.COMPANY,
        created_at=OCCURRED_AT,
    )


def _contract_and_version(line: CoverageLine) -> tuple[SLIContract, ContractVersion]:
    version = ContractVersion(
        version_no=2,
        effective=KnownValidInterval(valid_from=OCCURRED_AT, known_at=OCCURRED_AT),
        coverage_lines=(line,),
        response_sla=SLA(
            duration=timedelta(hours=2),
            clock_start_event="work_order_opened",
            clock_stop_event="technician_allocated",
        ),
        repair_sla=SLA(
            duration=timedelta(hours=8),
            clock_start_event="work_started",
            clock_stop_event="technically_completed",
        ),
        availability_target_percentage=Decimal("97.5"),
        service_limits=ServiceLimits(max_services_per_period=3, period_days=30),
    )
    contract = SLIContract(
        contract_id=TypedId.parse("sli_contract", CONTRACT_ID),
        organization_id=OrganizationId.new(),
        customer_ref=TypedId.new("customer"),
    ).issue_version(
        ContractVersion(
            version_no=1,
            effective=KnownValidInterval(
                valid_from=datetime(2026, 1, 1, tzinfo=UTC),
                known_at=datetime(2026, 1, 1, tzinfo=UTC),
            ),
        )
    )
    return contract.issue_version(version), version


class _FakeContractContextQueryService:
    seen_vehicle_id: TypedId | None = None
    seen_instant: datetime | None = None

    def get_context_for_vehicle(
        self, *, vehicle_id: TypedId, instant: datetime
    ) -> ContractContextForVehicle:
        self.seen_vehicle_id = vehicle_id
        self.seen_instant = instant
        line = CoverageLine(
            scope=ContractScope.VEHICLE,
            scope_value=str(vehicle_id.value),
            covered_services=("preventiva",),
            covered_parts=(TypedId.parse("part", PART_ID),),
            labor_rules="horário comercial",
            travel_rules="até 50km",
        )
        contract, version = _contract_and_version(line)
        return ContractContextForVehicle(
            vehicle=_vehicle(vehicle_id),
            contract=contract,
            contract_version=version,
            coverage_line=line,
            resolved_at=instant,
        )


class _MissingContractContextQueryService:
    def get_context_for_vehicle(
        self, *, vehicle_id: TypedId, instant: datetime
    ) -> ContractContextForVehicle:
        raise ContractContextNaoEncontrado(
            f"Vehicle '{vehicle_id.value}' sem contrato em {instant.isoformat()}."
        )


class _AmbiguousContractContextQueryService:
    def get_context_for_vehicle(
        self, *, vehicle_id: TypedId, instant: datetime
    ) -> ContractContextForVehicle:
        raise ContractContextAmbiguo(
            f"Vehicle '{vehicle_id.value}' com cobertura ambígua em {instant.isoformat()}."
        )


def _fake_connection() -> object:
    return SimpleNamespace()


def test_contract_context_route_is_registered_in_openapi() -> None:
    paths = set(main_module.app.openapi()["paths"])

    assert "/v1/asset/vehicles/{vehicle_id}/contract-context" in paths


def test_contract_context_requires_authentication() -> None:
    response = TestClient(main_module.app).get(ROUTE, params={"instant": INSTANT})

    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")


def test_contract_context_rejects_missing_permission(monkeypatch: MonkeyPatch) -> None:
    contexto = _context(permissions=frozenset())
    main_module.app.dependency_overrides[require_authenticated_principal] = lambda: (
        contexto.authenticated_principal
    )
    main_module.app.dependency_overrides[request_connection] = _fake_connection
    main_module.app.dependency_overrides[asset_queries.get_contract_context_query_service] = (
        _FakeContractContextQueryService
    )

    monkeypatch.setattr(
        "apps.api.livestock_dependencies.resolve_organization_context",
        lambda *_args, **_kwargs: contexto,
    )

    response = TestClient(main_module.app).get(
        ROUTE,
        params={"instant": INSTANT},
        headers={ORGANIZATION_HEADER: str(contexto.organization_id.value)},
    )

    assert response.status_code == 403
    assert response.json()["reason_code"] == "PERMISSAO_AUSENTE"


def test_contract_context_returns_resolved_contract_version_and_coverage() -> None:
    contexto = _context()
    service = _FakeContractContextQueryService()
    main_module.app.dependency_overrides[asset_queries.require_contract_read] = lambda: contexto
    main_module.app.dependency_overrides[asset_queries.get_contract_context_query_service] = (
        lambda: service
    )

    response = TestClient(main_module.app).get(ROUTE, params={"instant": INSTANT})

    assert response.status_code == 200
    assert service.seen_vehicle_id == TypedId.parse("vehicle", VEHICLE_ID)
    assert service.seen_instant == OCCURRED_AT
    assert response.json() == {
        "vehicle_id": VEHICLE_ID,
        "contract_ref": CONTRACT_ID,
        "contract_version_no": 2,
        "resolved_at": INSTANT,
        "coverage": {
            "scope": "VEHICLE",
            "scope_value": VEHICLE_ID,
            "covered_services": ["preventiva"],
            "covered_parts": [PART_ID],
            "excluded_parts": [],
            "labor_rules": "horário comercial",
            "travel_rules": "até 50km",
        },
        "response_sla_duration_seconds": 7200,
        "repair_sla_duration_seconds": 28800,
        "availability_target_percentage": "97.5",
        "service_limits": {"max_services_per_period": 3, "period_days": 30},
    }


def test_contract_context_rejects_invalid_identifier() -> None:
    contexto = _context()
    main_module.app.dependency_overrides[asset_queries.require_contract_read] = lambda: contexto
    main_module.app.dependency_overrides[asset_queries.get_contract_context_query_service] = (
        _FakeContractContextQueryService
    )

    response = TestClient(main_module.app).get(
        "/v1/asset/vehicles/nao-e-uuid/contract-context",
        params={"instant": INSTANT},
    )

    assert response.status_code == 422
    assert response.json()["reason_code"] == "IDENTIFICADOR_INVALIDO"


def test_contract_context_rejects_non_utc_instant() -> None:
    contexto = _context()
    main_module.app.dependency_overrides[asset_queries.require_contract_read] = lambda: contexto
    main_module.app.dependency_overrides[asset_queries.get_contract_context_query_service] = (
        _FakeContractContextQueryService
    )

    response = TestClient(main_module.app).get(
        ROUTE,
        params={"instant": "2026-10-03T08:00:00-04:00"},
    )

    assert response.status_code == 422
    assert response.json()["reason_code"] == "DATA_INVALIDA"


def test_contract_context_returns_404_when_missing() -> None:
    contexto = _context()
    main_module.app.dependency_overrides[asset_queries.require_contract_read] = lambda: contexto
    main_module.app.dependency_overrides[asset_queries.get_contract_context_query_service] = (
        _MissingContractContextQueryService
    )

    response = TestClient(main_module.app).get(ROUTE, params={"instant": INSTANT})

    assert response.status_code == 404
    assert response.json()["reason_code"] == "RECURSO_NAO_ENCONTRADO"


def test_contract_context_returns_409_when_ambiguous() -> None:
    contexto = _context()
    main_module.app.dependency_overrides[asset_queries.require_contract_read] = lambda: contexto
    main_module.app.dependency_overrides[asset_queries.get_contract_context_query_service] = (
        _AmbiguousContractContextQueryService
    )

    response = TestClient(main_module.app).get(ROUTE, params={"instant": INSTANT})

    assert response.status_code == 409
    assert response.json()["reason_code"] == "COBERTURA_AMBIGUA"
