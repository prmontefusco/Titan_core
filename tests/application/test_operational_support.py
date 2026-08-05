from datetime import UTC, datetime
from unittest.mock import MagicMock

from packages.core_application.operational_support import (
    OperationalDiagnosticCondition,
    OperationalSupportRepositoryPort,
    OperationalSupportService,
    OperationalSupportSummary,
)
from packages.shared_kernel import OrganizationId


def test_operational_support_service_returns_derived_summary() -> None:
    summary = OperationalSupportSummary(
        organization_id=OrganizationId.new(),
        observed_at=datetime.now(UTC),
        scope="organization",
        filters=(),
        diagnostic_condition=OperationalDiagnosticCondition.INDETERMINATE,
        total_pending_outbox=3,
        active_claims=1,
        expired_claims=0,
        unknown_results_total=1,
        unknown_results_reconcilable=0,
        unknown_results_human_intervention=1,
        quarantined_messages=2,
        duplicate_deliveries_detected=1,
        duplicate_recoveries_completed=0,
        oldest_pending_age_seconds=30.0,
        oldest_unknown_age_seconds=25.0,
        last_reconciliation_at=None,
        recommended_action="RECONCILE",
        automatic_retry_allowed=False,
        reason_code="EXTERNAL_EFFECT_MAY_HAVE_OCCURRED",
    )
    repository = MagicMock(spec=OperationalSupportRepositoryPort)
    repository.build_summary.return_value = summary

    result = OperationalSupportService(repository=repository).summary()

    assert result is summary
    assert result.diagnostic_condition is OperationalDiagnosticCondition.INDETERMINATE
