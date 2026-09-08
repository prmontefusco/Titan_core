from datetime import UTC, datetime, timedelta
from typing import Any, cast

from sqlalchemy import Connection

from packages.livestock_application.market_optionality import (
    InMemoryMarketOptionExplanationAuditRepository,
    MarketOptionAssessmentService,
    MarketOptionExplanationAuditRecord,
    MarketOptionExplanationPipelineService,
)
from packages.livestock_infrastructure.persistence.ai_explanation_audit_repository import (
    TransactionalAIExplanationAuditRepository,
)
from packages.shared_kernel import TypedId
from tests.livestock_application.test_market_optionality import (
    PURPOSE,
    _ai_run_context,
    _context_from_artifacts,
)
from tests.livestock_application.test_market_readiness import _artifacts

NOW = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)


class _Result:
    def __init__(self, rows: list[object] | None = None) -> None:
        self._rows = rows or []

    def fetchone(self) -> object | None:
        return self._rows[0] if self._rows else None

    def fetchall(self) -> list[object]:
        return self._rows


class _Connection:
    def __init__(self) -> None:
        self.params: dict[str, Any] | None = None
        self.rows: list[object] = []

    def execute(self, _statement: object, params: dict[str, Any] | None = None) -> _Result:
        self.params = params
        return _Result(self.rows)


def _record() -> MarketOptionExplanationAuditRecord:
    decision, evaluation, policy = _artifacts(purpose=PURPOSE)
    assessment = MarketOptionAssessmentService().assess(
        context=_context_from_artifacts(policy, decision),
        decision=decision,
        evaluation=evaluation,
    )
    result = MarketOptionExplanationPipelineService().explain(
        assessment=assessment,
        run_context=_ai_run_context(policy.organization_id, idempotency_key="idem-secret"),
    )
    return MarketOptionExplanationAuditRecord.from_result(
        audit_id=TypedId.new("ai_explanation_audit"),
        result=result,
        requested_at=NOW,
        evaluated_at=NOW + timedelta(seconds=1),
        correlation_id=TypedId.new("correlation"),
    )


def test_transactional_ai_explanation_audit_append_writes_minimized_row() -> None:
    connection = _Connection()
    repository = TransactionalAIExplanationAuditRepository(cast(Connection, connection))
    record = _record()

    repository.append(record)

    assert connection.params is not None
    assert connection.params["audit_id"] == record.audit_id.value
    assert connection.params["record_owner_organization_id"] == (
        record.record_owner_organization_id.value
    )
    assert connection.params["source_reference_audit_references"]
    assert connection.params["released_output_digest"] == record.released_output_digest
    assert connection.params["record_digest"] == record.record_digest()
    assert "idem-secret" not in repr(connection.params)
    assert "raw_prompt" not in connection.params
    assert "raw_provider_output" not in connection.params
    assert "animal_id" not in connection.params
    assert "evidence_payload" not in connection.params


def test_transactional_ai_explanation_audit_round_trip_from_row() -> None:
    connection = _Connection()
    repository = TransactionalAIExplanationAuditRepository(cast(Connection, connection))
    record = _record()
    repository.append(record)
    assert connection.params is not None
    connection.rows = [type("Row", (), connection.params)]

    persisted = repository.get(record.audit_id)

    assert persisted == record


def test_transactional_ai_explanation_audit_owner_scoped_queries() -> None:
    connection = _Connection()
    repository = TransactionalAIExplanationAuditRepository(cast(Connection, connection))
    record = _record()
    repository.append(record)
    assert connection.params is not None
    connection.rows = [type("Row", (), connection.params)]

    by_correlation = repository.find_by_correlation_id(
        record_owner_organization_id=record.record_owner_organization_id,
        correlation_id=record.correlation_id,
    )
    assert by_correlation == (record,)
    assert connection.params["record_owner_organization_id"] == (
        record.record_owner_organization_id.value
    )

    assert record.idempotency_reference is not None
    by_idempotency = repository.find_by_idempotency_reference(
        record_owner_organization_id=record.record_owner_organization_id,
        idempotency_reference=record.idempotency_reference,
    )
    assert by_idempotency == (record,)
    assert connection.params["idempotency_reference"] == record.idempotency_reference


def test_transactional_ai_explanation_audit_satisfies_application_port() -> None:
    application_repository: InMemoryMarketOptionExplanationAuditRepository
    application_repository = InMemoryMarketOptionExplanationAuditRepository()
    transactional_repository = TransactionalAIExplanationAuditRepository(
        cast(Connection, _Connection())
    )

    assert hasattr(application_repository, "find_by_correlation_id")
    assert hasattr(transactional_repository, "find_by_correlation_id")
    assert hasattr(application_repository, "find_by_idempotency_reference")
    assert hasattr(transactional_repository, "find_by_idempotency_reference")
