"""Projecoes diagnosticas derivadas para suporte operacional do fluxo assincrono."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from packages.shared_kernel import OrganizationId


class OperationalDiagnosticCondition(StrEnum):
    NORMAL = "NORMAL"
    INDETERMINATE = "INDETERMINATE"
    INCONSISTENT = "INCONSISTENT"


@dataclass(frozen=True, slots=True)
class OperationalSupportSummary:
    organization_id: OrganizationId
    observed_at: datetime
    scope: str
    filters: tuple[str, ...]
    diagnostic_condition: OperationalDiagnosticCondition
    total_pending_outbox: int
    active_claims: int
    expired_claims: int
    unknown_results_total: int
    unknown_results_reconcilable: int
    unknown_results_human_intervention: int
    quarantined_messages: int
    duplicate_deliveries_detected: int
    duplicate_recoveries_completed: int
    oldest_pending_age_seconds: float | None
    oldest_unknown_age_seconds: float | None
    last_reconciliation_at: datetime | None
    recommended_action: str | None
    automatic_retry_allowed: bool
    reason_code: str | None


class OperationalSupportRepositoryPort(Protocol):
    def build_summary(self) -> OperationalSupportSummary: ...


@dataclass(frozen=True, slots=True)
class OperationalSupportService:
    repository: OperationalSupportRepositoryPort

    def summary(self) -> OperationalSupportSummary:
        return self.repository.build_summary()
