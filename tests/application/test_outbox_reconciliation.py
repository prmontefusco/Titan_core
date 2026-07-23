"""Testes unitarios do servico de reconciliacao operacional da Outbox (ADR-0006/Passo 4.9A)."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

from packages.core_application.outbox import (
    OutboxHealthSummary,
    OutboxReconciliationReport,
    OutboxReconciliationRepositoryPort,
    OutboxReconciliationService,
)


def test_outbox_reconciliation_service_runs_sweep_and_produces_report() -> None:
    now = datetime.now(UTC)
    summary1 = OutboxHealthSummary(
        total_pending=2,
        active_claims=1,
        expired_claims=1,
        accepted_by_broker=5,
        unknown_results=0,
        rejected_by_broker=0,
        oldest_pending_age_seconds=120.0,
        oldest_expired_claim_age_seconds=30.0,
        read_at=now,
    )
    summary2 = OutboxHealthSummary(
        total_pending=2,
        active_claims=0,
        expired_claims=0,
        accepted_by_broker=5,
        unknown_results=1,
        rejected_by_broker=0,
        oldest_pending_age_seconds=120.0,
        oldest_expired_claim_age_seconds=None,
        read_at=now,
    )

    repo = MagicMock(spec=OutboxReconciliationRepositoryPort)
    repo.get_health_summary.side_effect = [summary1, summary2]
    repo.release_expired_claims.return_value = 1

    service = OutboxReconciliationService(repository=repo)
    report = service.run()

    assert isinstance(report, OutboxReconciliationReport)
    assert report.summary_before.expired_claims == 1
    assert report.released_claims_count == 1
    assert report.summary_after.expired_claims == 0
    assert report.summary_after.unknown_results == 1
