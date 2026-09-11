"""Testes do `SLIContractService` — Titan Asset (A4)."""

from datetime import UTC, datetime

from packages.asset_application.event_recorder import AssetEventRecorder, AssetOperationContext
from packages.asset_application.sustainment_contract_service import (
    SLIContractRepositoryPort,
    SLIContractService,
)
from packages.asset_domain.events import (
    SUSTAINMENT_CONTRACT_REGISTERED,
    SUSTAINMENT_CONTRACT_VERSION_ISSUED,
)
from packages.asset_domain.sustainment_contract import (
    ContractScope,
    ContractVersion,
    CoverageLine,
    KnownValidInterval,
    SLIContract,
)
from packages.shared_kernel import TypedId
from tests.asset_support import FakeEventLog

OCCURRED_AT = datetime(2026, 9, 11, tzinfo=UTC)


class InMemorySLIContractRepository(SLIContractRepositoryPort):
    def __init__(self) -> None:
        self.contracts: dict[str, SLIContract] = {}

    def save(self, contract: SLIContract) -> None:
        self.contracts[contract.contract_id.value.hex] = contract

    def update(self, contract: SLIContract) -> None:
        self.contracts[contract.contract_id.value.hex] = contract

    def get_by_id(self, contract_id: TypedId) -> SLIContract | None:
        return self.contracts.get(contract_id.value.hex)


def test_register_contract(
    recorder: AssetEventRecorder, context: AssetOperationContext, event_log: FakeEventLog
) -> None:
    service = SLIContractService(repository=InMemorySLIContractRepository(), recorder=recorder)
    contract = service.register_contract(
        context, customer_ref=TypedId.new("customer"), occurred_at=OCCURRED_AT
    )
    assert contract.organization_id == context.organization_id
    assert service.get_contract(contract.contract_id) == contract
    event_log.only(SUSTAINMENT_CONTRACT_REGISTERED)


def test_issue_first_version(
    recorder: AssetEventRecorder, context: AssetOperationContext, event_log: FakeEventLog
) -> None:
    service = SLIContractService(repository=InMemorySLIContractRepository(), recorder=recorder)
    contract = service.register_contract(
        context, customer_ref=TypedId.new("customer"), occurred_at=OCCURRED_AT
    )

    version_1 = ContractVersion(
        version_no=1,
        effective=KnownValidInterval(
            valid_from=datetime(2026, 1, 1, tzinfo=UTC), known_at=datetime(2026, 1, 1, tzinfo=UTC)
        ),
        coverage_lines=(CoverageLine(scope=ContractScope.VEHICLE, scope_value="VEH-001"),),
    )
    updated = service.issue_contract_version(
        context, contract.contract_id, version=version_1, occurred_at=OCCURRED_AT
    )
    assert updated.current_version_no == 1
    event = event_log.only(SUSTAINMENT_CONTRACT_VERSION_ISSUED)
    assert event.aggregate_version == 2


def test_amend_contract_issues_second_version_with_amendment_ref(
    recorder: AssetEventRecorder, context: AssetOperationContext, event_log: FakeEventLog
) -> None:
    service = SLIContractService(repository=InMemorySLIContractRepository(), recorder=recorder)
    contract = service.register_contract(
        context, customer_ref=TypedId.new("customer"), occurred_at=OCCURRED_AT
    )
    version_1 = ContractVersion(
        version_no=1,
        effective=KnownValidInterval(
            valid_from=datetime(2026, 1, 1, tzinfo=UTC), known_at=datetime(2026, 1, 1, tzinfo=UTC)
        ),
    )
    service.issue_contract_version(
        context, contract.contract_id, version=version_1, occurred_at=OCCURRED_AT
    )

    amendment_ref = TypedId.new("contract_amendment")
    version_2 = ContractVersion(
        version_no=2,
        effective=KnownValidInterval(
            valid_from=datetime(2026, 6, 1, tzinfo=UTC), known_at=datetime(2026, 6, 1, tzinfo=UTC)
        ),
        amendment_ref=amendment_ref,
    )
    amended = service.issue_contract_version(
        context, contract.contract_id, version=version_2, occurred_at=OCCURRED_AT
    )
    assert amended.current_version_no == 2
    assert amended.versions[-1].amendment_ref == amendment_ref
    assert len(event_log.of_type(SUSTAINMENT_CONTRACT_VERSION_ISSUED)) == 2
