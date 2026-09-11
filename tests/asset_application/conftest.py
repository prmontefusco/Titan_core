"""Fixtures comuns aos testes de serviços da vertical Asset (A4)."""

from datetime import UTC, datetime

import pytest

from packages.asset_application.event_recorder import AssetEventRecorder, AssetOperationContext
from packages.shared_kernel import FixedClock, OrganizationId
from tests.asset_support import FakeEventLog, operation_context

__all__ = ["FakeEventLog", "RECORDED_AT"]

RECORDED_AT = datetime(2026, 9, 11, 12, 0, tzinfo=UTC)


@pytest.fixture
def event_log() -> FakeEventLog:
    return FakeEventLog()


@pytest.fixture
def recorder(event_log: FakeEventLog) -> AssetEventRecorder:
    return AssetEventRecorder(event_log=event_log, clock=FixedClock(RECORDED_AT))


@pytest.fixture
def organization_id() -> OrganizationId:
    return OrganizationId.new()


@pytest.fixture
def context(organization_id: OrganizationId) -> AssetOperationContext:
    return operation_context(organization_id)
