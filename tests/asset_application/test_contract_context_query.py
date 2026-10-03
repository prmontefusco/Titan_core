"""Testes da query `GetContractContextForVehicle` — Titan Asset A5."""

from datetime import UTC, datetime, timedelta

import pytest

from packages.asset_application.contract_context_query import (
    ContractContextAmbiguo,
    ContractContextNaoEncontrado,
    ContractContextQueryService,
    ContractContextRepositoryPort,
    ContractContextVehicleRepositoryPort,
)
from packages.asset_domain.sustainment_contract import (
    SLA,
    ContractScope,
    ContractVersion,
    CoverageLine,
    KnownValidInterval,
    SLIContract,
)
from packages.asset_domain.vehicle import AssetOwnership, Vehicle, VehicleIdentifiers
from packages.shared_kernel import OrganizationId, TypedId

OCCURRED_AT = datetime(2026, 10, 3, 12, 0, tzinfo=UTC)


class InMemoryVehicleRepository(ContractContextVehicleRepositoryPort):
    def __init__(self, items: tuple[Vehicle, ...]) -> None:
        self.items = {item.vehicle_id: item for item in items}

    def get_by_id(self, vehicle_id: TypedId) -> Vehicle | None:
        return self.items.get(vehicle_id)


class InMemoryContractRepository(ContractContextRepositoryPort):
    def __init__(self, items: tuple[SLIContract, ...]) -> None:
        self.items = items

    def list_all(self) -> tuple[SLIContract, ...]:
        return self.items


def _vehicle(*, model_ref: TypedId | None = None) -> Vehicle:
    return Vehicle(
        vehicle_id=TypedId.new("vehicle"),
        organization_id=OrganizationId.new(),
        model_ref=model_ref or TypedId.new("vehicle_model"),
        identifiers=VehicleIdentifiers(serial_number="SN-001"),
        ownership=AssetOwnership.COMPANY,
        created_at=OCCURRED_AT,
    )


def _contract(line: CoverageLine, *, valid_from: datetime = OCCURRED_AT) -> SLIContract:
    version = ContractVersion(
        version_no=1,
        effective=KnownValidInterval(valid_from=valid_from, known_at=valid_from),
        coverage_lines=(line,),
        response_sla=SLA(
            duration=timedelta(hours=2),
            clock_start_event="work_order_opened",
            clock_stop_event="technician_allocated",
        ),
    )
    contract = SLIContract(
        contract_id=TypedId.new("sli_contract"),
        organization_id=OrganizationId.new(),
        customer_ref=TypedId.new("customer"),
    )
    return contract.issue_version(version)


def test_contract_context_for_vehicle_resolves_vehicle_specific_coverage() -> None:
    vehicle = _vehicle()
    line = CoverageLine(scope=ContractScope.VEHICLE, scope_value=str(vehicle.vehicle_id.value))
    contract = _contract(line)
    service = ContractContextQueryService(
        vehicle_repository=InMemoryVehicleRepository((vehicle,)),
        contract_repository=InMemoryContractRepository((contract,)),
    )

    result = service.get_context_for_vehicle(vehicle_id=vehicle.vehicle_id, instant=OCCURRED_AT)

    assert result.vehicle == vehicle
    assert result.contract == contract
    assert result.contract_version.version_no == 1
    assert result.coverage_line == line
    assert result.response_sla_duration_seconds == 7200


def test_contract_context_for_vehicle_resolves_model_coverage() -> None:
    model_ref = TypedId.new("vehicle_model")
    vehicle = _vehicle(model_ref=model_ref)
    contract = _contract(CoverageLine(scope=ContractScope.MODEL, scope_value=str(model_ref.value)))
    service = ContractContextQueryService(
        vehicle_repository=InMemoryVehicleRepository((vehicle,)),
        contract_repository=InMemoryContractRepository((contract,)),
    )

    result = service.get_context_for_vehicle(vehicle_id=vehicle.vehicle_id, instant=OCCURRED_AT)

    assert result.contract == contract


def test_contract_context_for_vehicle_rejects_missing_coverage() -> None:
    vehicle = _vehicle()
    service = ContractContextQueryService(
        vehicle_repository=InMemoryVehicleRepository((vehicle,)),
        contract_repository=InMemoryContractRepository(()),
    )

    with pytest.raises(ContractContextNaoEncontrado):
        service.get_context_for_vehicle(vehicle_id=vehicle.vehicle_id, instant=OCCURRED_AT)


def test_contract_context_for_vehicle_rejects_ambiguous_coverage() -> None:
    vehicle = _vehicle()
    line = CoverageLine(scope=ContractScope.VEHICLE, scope_value=str(vehicle.vehicle_id.value))
    service = ContractContextQueryService(
        vehicle_repository=InMemoryVehicleRepository((vehicle,)),
        contract_repository=InMemoryContractRepository((_contract(line), _contract(line))),
    )

    with pytest.raises(ContractContextAmbiguo):
        service.get_context_for_vehicle(vehicle_id=vehicle.vehicle_id, instant=OCCURRED_AT)
