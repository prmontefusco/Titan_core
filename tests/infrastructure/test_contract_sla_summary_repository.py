"""Testes do repositório de leitura `ContractSLASummary` — Titan Asset A6."""

from datetime import UTC, datetime
from uuid import uuid4

from packages.asset_domain.sustainment_contract import (
    ContractScope,
    ContractVersion,
    CoverageLine,
    KnownValidInterval,
)
from packages.asset_domain.work_order import WorkOrderState
from packages.asset_infrastructure.persistence.contract_sla_summary_repository import (
    _covered_vehicle_refs,
    _open_work_orders_for_contract_statement,
    _vehicle_candidates_statement,
    _VehicleCoverageCandidate,
)
from packages.asset_infrastructure.persistence.vehicle_repository import vehicles_table
from packages.asset_infrastructure.persistence.work_order_repository import work_orders_table
from packages.shared_kernel import TypedId

OCCURRED_AT = datetime(2026, 9, 11, tzinfo=UTC)


def _version(*, coverage_lines: tuple[CoverageLine, ...]) -> ContractVersion:
    return ContractVersion(
        version_no=1,
        effective=KnownValidInterval(valid_from=OCCURRED_AT, known_at=OCCURRED_AT),
        coverage_lines=coverage_lines,
    )


def test_covered_vehicle_refs_match_vehicle_site_and_model_scopes_without_duplicates() -> None:
    site_id = uuid4()
    model_id = uuid4()
    direct_vehicle = _VehicleCoverageCandidate(
        vehicle_id=uuid4(), model_id=uuid4(), site_id=uuid4()
    )
    site_vehicle = _VehicleCoverageCandidate(vehicle_id=uuid4(), model_id=uuid4(), site_id=site_id)
    model_vehicle = _VehicleCoverageCandidate(vehicle_id=uuid4(), model_id=model_id, site_id=None)
    version = _version(
        coverage_lines=(
            CoverageLine(scope=ContractScope.VEHICLE, scope_value=str(direct_vehicle.vehicle_id)),
            CoverageLine(scope=ContractScope.SITE, scope_value=str(site_id)),
            CoverageLine(scope=ContractScope.MODEL, scope_value=str(model_id)),
            CoverageLine(scope=ContractScope.MODEL, scope_value=str(model_id)),
        )
    )

    covered = _covered_vehicle_refs((direct_vehicle, site_vehicle, model_vehicle), version)

    assert covered == (
        TypedId(entity_type="vehicle", value=direct_vehicle.vehicle_id),
        TypedId(entity_type="vehicle", value=site_vehicle.vehicle_id),
        TypedId(entity_type="vehicle", value=model_vehicle.vehicle_id),
    )


def test_covered_vehicle_refs_returns_empty_without_active_version() -> None:
    candidate = _VehicleCoverageCandidate(vehicle_id=uuid4(), model_id=uuid4(), site_id=None)

    assert _covered_vehicle_refs((candidate,), None) == ()


def test_vehicle_candidates_statement_selects_required_vehicle_fields() -> None:
    statement = _vehicle_candidates_statement()

    sql = str(statement)
    assert vehicles_table.c.vehicle_id.name in sql
    assert vehicles_table.c.model_id.name in sql
    assert vehicles_table.c.site_id.name in sql


def test_open_work_orders_for_contract_statement_filters_terminal_states() -> None:
    contract_ref = TypedId.new("sli_contract")

    statement = _open_work_orders_for_contract_statement(contract_ref)

    compiled_sql = str(statement.compile(compile_kwargs={"literal_binds": True}))
    assert contract_ref.value in statement.compile().params.values()
    assert work_orders_table.c.contract_ref_id.name in str(statement.whereclause)
    assert WorkOrderState.COMPLETED.value in compiled_sql
    assert WorkOrderState.CANCELLED.value in compiled_sql
