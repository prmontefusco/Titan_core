"""Testes do entitlement de SLI via Decision governada do Core."""

from datetime import UTC, datetime

import pytest

from packages.asset_application.entitlement_service import (
    EntitlementDecisionInvalida,
    EntitlementDecisionPort,
    EntitlementExceptionDecisionPort,
    EntitlementOutcome,
    EntitlementRequest,
    EntitlementResolution,
    EntitlementService,
)
from packages.asset_application.event_recorder import AssetEventRecorder, AssetOperationContext
from packages.asset_domain.events import SUSTAINMENT_ENTITLEMENT_RESOLVED
from packages.shared_kernel import TypedId
from tests.asset_support import FakeEventLog

OCCURRED_AT = datetime(2026, 9, 11, tzinfo=UTC)


class FakeDecisionPort(EntitlementDecisionPort):
    def __init__(self, resolution: EntitlementResolution) -> None:
        self.resolution = resolution
        self.requests: list[EntitlementRequest] = []

    def resolve(self, request: EntitlementRequest) -> EntitlementResolution:
        self.requests.append(request)
        return self.resolution


class FakeExceptionDecisionPort(EntitlementExceptionDecisionPort):
    def __init__(self, resolution: EntitlementResolution) -> None:
        self.resolution = resolution

    def authorize_exception(
        self,
        *,
        denied_resolution: EntitlementResolution,
        reason: str,
        decided_at: datetime,
    ) -> EntitlementResolution:
        return self.resolution


def _request(*, vehicle_ref: TypedId, subject_ref: TypedId) -> EntitlementRequest:
    return EntitlementRequest(
        vehicle_ref=vehicle_ref,
        subject_ref=subject_ref,
        contract_ref=TypedId.new("sli_contract"),
        contract_version_no=1,
        instant=OCCURRED_AT,
        quantity="2",
    )


def _resolution(
    *,
    vehicle_ref: TypedId,
    subject_ref: TypedId,
    outcome: EntitlementOutcome = EntitlementOutcome.GRANTED,
) -> EntitlementResolution:
    return EntitlementResolution(
        vehicle_ref=vehicle_ref,
        subject_ref=subject_ref,
        instant=OCCURRED_AT,
        decision_ref=TypedId.new("decision"),
        outcome=outcome,
        breakdown="Decision do Core preservou regra, fatos e contrato.",
    )


def test_resolve_entitlement_records_core_decision(
    recorder: AssetEventRecorder, context: AssetOperationContext, event_log: FakeEventLog
) -> None:
    vehicle_ref = TypedId.new("vehicle")
    subject_ref = TypedId.new("part")
    resolution = _resolution(vehicle_ref=vehicle_ref, subject_ref=subject_ref)
    decision_port = FakeDecisionPort(resolution)
    service = EntitlementService(
        decision_port=decision_port,
        exception_decision_port=FakeExceptionDecisionPort(resolution),
        recorder=recorder,
    )

    returned = service.resolve_entitlement(
        context,
        _request(vehicle_ref=vehicle_ref, subject_ref=subject_ref),
        occurred_at=OCCURRED_AT,
    )

    assert returned is resolution
    assert len(decision_port.requests) == 1
    event = event_log.only(SUSTAINMENT_ENTITLEMENT_RESOLVED)
    assert event.aggregate_reference.target_id == vehicle_ref


def test_resolve_entitlement_rejects_mismatched_core_decision(
    recorder: AssetEventRecorder, context: AssetOperationContext
) -> None:
    vehicle_ref = TypedId.new("vehicle")
    subject_ref = TypedId.new("part")
    service = EntitlementService(
        decision_port=FakeDecisionPort(
            _resolution(vehicle_ref=TypedId.new("vehicle"), subject_ref=subject_ref)
        ),
        exception_decision_port=FakeExceptionDecisionPort(
            _resolution(vehicle_ref=vehicle_ref, subject_ref=subject_ref)
        ),
        recorder=recorder,
    )

    with pytest.raises(EntitlementDecisionInvalida):
        service.resolve_entitlement(
            context,
            _request(vehicle_ref=vehicle_ref, subject_ref=subject_ref),
            occurred_at=OCCURRED_AT,
        )


def test_authorize_exception_requires_denied_original_decision(
    recorder: AssetEventRecorder, context: AssetOperationContext
) -> None:
    vehicle_ref = TypedId.new("vehicle")
    subject_ref = TypedId.new("part")
    granted = _resolution(vehicle_ref=vehicle_ref, subject_ref=subject_ref)
    service = EntitlementService(
        decision_port=FakeDecisionPort(granted),
        exception_decision_port=FakeExceptionDecisionPort(
            _resolution(
                vehicle_ref=vehicle_ref,
                subject_ref=subject_ref,
                outcome=EntitlementOutcome.GRANTED_WITH_EXCEPTION,
            )
        ),
        recorder=recorder,
    )

    with pytest.raises(EntitlementDecisionInvalida):
        service.authorize_entitlement_exception(
            context,
            granted,
            reason="Gestor aprovou excecao.",
            occurred_at=OCCURRED_AT,
        )
