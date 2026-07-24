"""Fixtures comuns aos testes de serviços da vertical (Passo 10.1a)."""

from datetime import UTC, datetime

import pytest

from packages.livestock_application.event_recorder import (
    LivestockEventRecorder,
    LivestockOperationContext,
)
from packages.shared_kernel import FixedClock, OrganizationId
from tests.livestock_support import (
    FakeDecisionRepository,
    FakeEvaluationRepository,
    FakeEventLog,
    operation_context,
)

__all__ = ["FakeDecisionRepository", "FakeEvaluationRepository", "FakeEventLog", "RECORDED_AT"]

RECORDED_AT = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)


@pytest.fixture
def event_log() -> FakeEventLog:
    return FakeEventLog()


@pytest.fixture
def recorder(event_log: FakeEventLog) -> LivestockEventRecorder:
    return LivestockEventRecorder(event_log=event_log, clock=FixedClock(RECORDED_AT))


@pytest.fixture
def organization_id() -> OrganizationId:
    return OrganizationId.new()


@pytest.fixture
def context(organization_id: OrganizationId) -> LivestockOperationContext:
    return operation_context(organization_id)
