"""Testes do `ApplicabilityService` — Titan Asset (A4)."""

from datetime import UTC, datetime

import pytest

from packages.asset_application.applicability_service import (
    ApplicabilityNaoEncontrada,
    ApplicabilityRepositoryPort,
    ApplicabilityService,
)
from packages.asset_application.event_recorder import AssetEventRecorder, AssetOperationContext
from packages.asset_domain.applicability import (
    Applicability,
    ApplicabilityState,
    ApplicabilityTarget,
)
from packages.asset_domain.events import APPLICABILITY_ASSERTED, APPLICABILITY_WITHDRAWN
from packages.core_application import OptimisticConcurrencyConflict
from packages.shared_kernel import TypedId
from tests.asset_support import FakeEventLog

VALID_FROM = datetime(2026, 1, 1, tzinfo=UTC)


class InMemoryApplicabilityRepository(ApplicabilityRepositoryPort):
    def __init__(self) -> None:
        self.items: dict[str, Applicability] = {}

    def save(self, applicability: Applicability) -> None:
        self.items[applicability.applicability_id.value.hex] = applicability

    def update(self, applicability: Applicability) -> None:
        self.items[applicability.applicability_id.value.hex] = applicability

    def get_by_id(self, applicability_id: TypedId) -> Applicability | None:
        return self.items.get(applicability_id.value.hex)


def _assert(service: ApplicabilityService, context: AssetOperationContext) -> Applicability:
    return service.assert_applicability(
        context,
        part_ref=TypedId.new("part"),
        part_revision_ref=TypedId.new("part_revision"),
        target=ApplicabilityTarget(
            model_ref=TypedId.new("vehicle_model"),
            variant_ref=None,
            serial_from="1000",
            serial_to=None,
            valid_from=VALID_FROM,
            valid_until=None,
        ),
        evidence_ref=TypedId.new("evidence"),
        asserted_at=VALID_FROM,
        asserted_by=TypedId.new("user"),
    )


def test_assert_applicability(
    recorder: AssetEventRecorder, context: AssetOperationContext, event_log: FakeEventLog
) -> None:
    service = ApplicabilityService(
        repository=InMemoryApplicabilityRepository(), recorder=recorder, event_reader=event_log
    )
    applicability = _assert(service, context)

    assert applicability.state is ApplicabilityState.ASSERTED
    assert service.get_applicability(applicability.applicability_id) == applicability
    event_log.only(APPLICABILITY_ASSERTED)


def test_withdraw_applicability(
    recorder: AssetEventRecorder, context: AssetOperationContext, event_log: FakeEventLog
) -> None:
    service = ApplicabilityService(
        repository=InMemoryApplicabilityRepository(), recorder=recorder, event_reader=event_log
    )
    applicability = _assert(service, context)

    withdrawn = service.withdraw_applicability(
        context,
        applicability.applicability_id,
        reason="Substituída por revisão B.",
        withdrawn_at=datetime(2026, 6, 1, tzinfo=UTC),
    )
    assert withdrawn.state is ApplicabilityState.WITHDRAWN
    withdrawn_event = event_log.only(APPLICABILITY_WITHDRAWN)
    assert withdrawn_event.causation_id == event_log.only(APPLICABILITY_ASSERTED).event_id


def test_withdraw_unknown_applicability_raises(
    recorder: AssetEventRecorder, context: AssetOperationContext, event_log: FakeEventLog
) -> None:
    service = ApplicabilityService(
        repository=InMemoryApplicabilityRepository(), recorder=recorder, event_reader=event_log
    )
    with pytest.raises(ApplicabilityNaoEncontrada):
        service.withdraw_applicability(
            context,
            TypedId.new("applicability"),
            reason="motivo",
            withdrawn_at=VALID_FROM,
        )


def test_withdraw_rejects_stale_expected_version(
    recorder: AssetEventRecorder, context: AssetOperationContext, event_log: FakeEventLog
) -> None:
    service = ApplicabilityService(
        repository=InMemoryApplicabilityRepository(), recorder=recorder, event_reader=event_log
    )
    applicability = _assert(service, context)

    with pytest.raises(OptimisticConcurrencyConflict):
        service.withdraw_applicability(
            context,
            applicability.applicability_id,
            reason="Correção fictícia.",
            withdrawn_at=datetime(2026, 6, 1, tzinfo=UTC),
            expected_version=applicability.version + 1,
        )

    assert service.get_applicability(applicability.applicability_id) == applicability
    assert event_log.of_type(APPLICABILITY_WITHDRAWN) == []
