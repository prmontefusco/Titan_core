"""Testes do `ContractSLASummaryService` — Titan Asset A6."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from packages.asset_application.contract_sla_summary import (
    ContractSLAOperationalSignal,
    ContractSLASummaryRepositoryPort,
    ContractSLASummaryService,
    ContractSLASummarySnapshot,
    SLIContractSummaryNaoEncontrado,
)
from packages.asset_domain.sustainment_contract import (
    SLA,
    ContractVersion,
    KnownValidInterval,
    SLIContract,
)
from packages.asset_domain.work_order import (
    ContractContext,
    FailureRecord,
    PriorityScore,
    WorkOrder,
    WorkOrderState,
)
from packages.shared_kernel import OrganizationId, TypedId

OCCURRED_AT = datetime(2026, 9, 11, tzinfo=UTC)


class InMemoryContractSLASummaryRepository(ContractSLASummaryRepositoryPort):
    def __init__(self, snapshots: tuple[ContractSLASummarySnapshot, ...]) -> None:
        self.snapshots = snapshots
        self.calls: list[tuple[TypedId, datetime | None]] = []

    def get_summary_snapshot(
        self, *, contract_ref: TypedId, as_of: datetime | None = None
    ) -> ContractSLASummarySnapshot | None:
        self.calls.append((contract_ref, as_of))
        for snapshot in self.snapshots:
            if snapshot.contract.contract_id == contract_ref:
                return snapshot
        return None


def _contract() -> SLIContract:
    version = ContractVersion(
        version_no=1,
        effective=KnownValidInterval(valid_from=OCCURRED_AT, known_at=OCCURRED_AT),
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
    )
    contract = SLIContract(
        contract_id=TypedId.new("sli_contract"),
        organization_id=OrganizationId.new(),
        customer_ref=TypedId.new("customer"),
    )
    return contract.issue_version(version)


def _work_order(
    contract: SLIContract,
    *,
    vehicle_ref: TypedId,
    state: WorkOrderState,
    score: int | None = 10,
) -> WorkOrder:
    priority = None if score is None else PriorityScore(score=score, breakdown={"sla": score})
    return WorkOrder(
        work_order_id=TypedId.new("work_order"),
        organization_id=contract.organization_id,
        vehicle_ref=vehicle_ref,
        site_ref=TypedId.new("customer_site"),
        contract_context=ContractContext(
            contract_ref=contract.contract_id,
            contract_version_no=1,
            resolved_at=OCCURRED_AT,
        ),
        failure=FailureRecord(mode="Falha", reported_at=OCCURRED_AT),
        state=state,
        priority=priority,
    )


def test_contract_sla_summary_reports_contract_sla_and_counts_open_work_orders() -> None:
    contract = _contract()
    first_vehicle = TypedId.new("vehicle")
    second_vehicle = TypedId.new("vehicle")
    waiting_material = _work_order(
        contract,
        vehicle_ref=first_vehicle,
        state=WorkOrderState.WAITING_MATERIAL,
        score=90,
    )
    open_low_priority = _work_order(
        contract,
        vehicle_ref=second_vehicle,
        state=WorkOrderState.PLANNED,
        score=20,
    )
    terminal = replace(
        open_low_priority,
        work_order_id=TypedId.new("work_order"),
        state=WorkOrderState.COMPLETED,
    )
    repository = InMemoryContractSLASummaryRepository(
        (
            ContractSLASummarySnapshot(
                contract=contract,
                covered_vehicle_refs=(first_vehicle, second_vehicle),
                open_work_orders=(open_low_priority, waiting_material, terminal),
                as_of=OCCURRED_AT,
            ),
        )
    )
    service = ContractSLASummaryService(repository)

    summary = service.get_contract_sla_summary(contract_ref=contract.contract_id)

    assert repository.calls == [(contract.contract_id, None)]
    assert summary.contract_ref == contract.contract_id
    assert summary.contract_version_no == 1
    assert summary.covered_vehicle_count == 2
    assert summary.open_work_order_count == 2
    assert summary.waiting_material_count == 1
    assert summary.sla_risk_count == 1
    assert summary.response_sla_duration_seconds == 7200
    assert summary.repair_sla_duration_seconds == 28800
    assert [line.work_order_id for line in summary.lines] == [
        waiting_material.work_order_id,
        open_low_priority.work_order_id,
    ]
    assert ContractSLAOperationalSignal.WAITING_MATERIAL in summary.lines[0].signals
    assert ContractSLAOperationalSignal.HIGH_PRIORITY in summary.lines[0].signals


def test_contract_sla_summary_filters_foreign_contract_work_orders() -> None:
    contract = _contract()
    foreign_contract = _contract()
    vehicle_ref = TypedId.new("vehicle")
    selected = _work_order(
        contract,
        vehicle_ref=vehicle_ref,
        state=WorkOrderState.WAITING_AUTHORIZATION,
        score=None,
    )
    foreign = _work_order(
        foreign_contract,
        vehicle_ref=TypedId.new("vehicle"),
        state=WorkOrderState.WAITING_MATERIAL,
        score=100,
    )
    service = ContractSLASummaryService(
        InMemoryContractSLASummaryRepository(
            (
                ContractSLASummarySnapshot(
                    contract=contract,
                    covered_vehicle_refs=(vehicle_ref,),
                    open_work_orders=(selected, foreign),
                    as_of=OCCURRED_AT,
                ),
            )
        )
    )

    summary = service.get_contract_sla_summary(contract_ref=contract.contract_id)

    assert summary.open_work_order_count == 1
    assert summary.waiting_authorization_count == 1
    assert summary.waiting_material_count == 0
    assert summary.sla_risk_count == 0
    assert summary.lines[0].work_order_id == selected.work_order_id
    assert ContractSLAOperationalSignal.WITHOUT_PRIORITY in summary.lines[0].signals


def test_contract_sla_summary_raises_when_contract_snapshot_is_missing() -> None:
    service = ContractSLASummaryService(InMemoryContractSLASummaryRepository(()))

    with pytest.raises(SLIContractSummaryNaoEncontrado):
        service.get_contract_sla_summary(contract_ref=TypedId.new("sli_contract"))
