"""Testes da query `GetWorkOrder` — Titan Asset A5."""

from datetime import UTC, datetime

import pytest

from packages.asset_application.work_order_query import (
    WorkOrderDetailNaoEncontrado,
    WorkOrderQueryRepositoryPort,
    WorkOrderQueryService,
)
from packages.asset_domain.work_order import ContractContext, FailureRecord, WorkOrder
from packages.shared_kernel import OrganizationId, TypedId

OCCURRED_AT = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)


class InMemoryWorkOrderQueryRepository(WorkOrderQueryRepositoryPort):
    def __init__(self, items: tuple[WorkOrder, ...]) -> None:
        self.items = {item.work_order_id: item for item in items}

    def get_by_id(self, work_order_id: TypedId) -> WorkOrder | None:
        return self.items.get(work_order_id)


def _work_order() -> WorkOrder:
    return WorkOrder(
        work_order_id=TypedId.new("work_order"),
        organization_id=OrganizationId.new(),
        vehicle_ref=TypedId.new("vehicle"),
        site_ref=TypedId.new("customer_site"),
        contract_context=ContractContext(
            contract_ref=TypedId.new("sli_contract"),
            contract_version_no=1,
            resolved_at=OCCURRED_AT,
        ),
        failure=FailureRecord(mode="Falha hidráulica", reported_at=OCCURRED_AT),
    )


def test_work_order_query_returns_aggregate() -> None:
    work_order = _work_order()
    service = WorkOrderQueryService(InMemoryWorkOrderQueryRepository((work_order,)))

    assert service.get_work_order(work_order.work_order_id) == work_order


def test_work_order_query_raises_when_missing() -> None:
    service = WorkOrderQueryService(InMemoryWorkOrderQueryRepository(()))

    with pytest.raises(WorkOrderDetailNaoEncontrado):
        service.get_work_order(TypedId.new("work_order"))
