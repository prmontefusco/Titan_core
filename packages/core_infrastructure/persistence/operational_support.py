"""Leitura derivada e tenant-safe do resumo operacional do fluxo assincrono."""

from dataclasses import dataclass
from datetime import UTC

from sqlalchemy import Connection, text

from packages.core_application.operational_support import (
    OperationalDiagnosticCondition,
    OperationalSupportSummary,
)
from packages.shared_kernel import OrganizationId


@dataclass(frozen=True, slots=True)
class OperationalSupportRepository:
    connection: Connection

    def __post_init__(self) -> None:
        if not isinstance(self.connection, Connection) or not self.connection.in_transaction():
            raise RuntimeError("OperationalSupportRepository exige transacao ativa.")

    def build_summary(self) -> OperationalSupportSummary:
        row = self.connection.execute(
            text(
                """
                WITH org AS (
                    SELECT
                        NULLIF(current_setting('titan.organization_id', true), '')::uuid AS org_id
                ),
                outbox AS (
                    SELECT
                        COUNT(*) FILTER (
                            WHERE s.status IS NULL OR s.status <> 'ACEITA_PELO_BROKER'
                        ) AS total_pending_outbox,
                        COUNT(*) FILTER (
                            WHERE s.status = 'CLAIMED' AND s.lease_expires_at >= CURRENT_TIMESTAMP
                        ) AS active_claims,
                        COUNT(*) FILTER (
                            WHERE s.status = 'CLAIMED' AND s.lease_expires_at < CURRENT_TIMESTAMP
                        ) AS expired_claims,
                        COUNT(*) FILTER (
                            WHERE s.status = 'RESULTADO_DESCONHECIDO'
                        ) AS unknown_results_total,
                        COUNT(*) FILTER (
                            WHERE s.status = 'RESULTADO_DESCONHECIDO'
                              AND s.last_reason = 'LEASE_EXPIRADA'
                        ) AS unknown_results_reconcilable,
                        EXTRACT(
                            EPOCH FROM (
                                CURRENT_TIMESTAMP - MIN(m.recorded_at) FILTER (
                                    WHERE s.status IS NULL OR s.status <> 'ACEITA_PELO_BROKER'
                                )
                            )
                        )::float AS oldest_pending_age_seconds,
                        EXTRACT(
                            EPOCH FROM (
                                CURRENT_TIMESTAMP - MIN(s.last_result_at) FILTER (
                                    WHERE s.status = 'RESULTADO_DESCONHECIDO'
                                )
                            )
                        )::float AS oldest_unknown_age_seconds,
                        MAX(s.last_result_at) FILTER (
                            WHERE s.last_reason = 'LEASE_EXPIRADA'
                        ) AS last_reconciliation_at
                    FROM core_audit.outbox_messages AS m
                    LEFT JOIN core_audit.outbox_publication_state AS s
                        ON s.message_id = m.message_id
                    JOIN org ON org.org_id = m.record_owner_organization_id
                ),
                inbox AS (
                    SELECT
                        COUNT(*) FILTER (
                            WHERE handling_result IN ('DUPLICATE_RECOVERED', 'CONFLICT_DETECTED')
                        ) AS duplicate_deliveries_detected,
                        COUNT(*) FILTER (
                            WHERE handling_result = 'DUPLICATE_RECOVERED'
                        ) AS duplicate_recoveries_completed
                    FROM core_messaging.inbox_delivery_attempts AS a
                    JOIN org ON org.org_id = a.record_owner_organization_id
                ),
                quarantines AS (
                    SELECT
                        (
                            SELECT COUNT(*)
                            FROM core_messaging.inbox_messages AS m
                            JOIN org ON org.org_id = m.record_owner_organization_id
                            WHERE m.status = 'EM_QUARENTENA'
                        ) +
                        (
                            SELECT COUNT(*)
                            FROM core_messaging.untrusted_message_quarantine AS q
                            JOIN org ON org.org_id::text = q.alleged_organization
                        ) AS quarantined_messages
                ),
                conflicts AS (
                    SELECT COUNT(*) AS conflicting_duplicates
                    FROM core_messaging.inbox_conflicts AS c
                    JOIN org ON org.org_id = c.record_owner_organization_id
                )
                SELECT
                    org.org_id,
                    outbox.total_pending_outbox,
                    outbox.active_claims,
                    outbox.expired_claims,
                    outbox.unknown_results_total,
                    outbox.unknown_results_reconcilable,
                    outbox.oldest_pending_age_seconds,
                    outbox.oldest_unknown_age_seconds,
                    outbox.last_reconciliation_at,
                    inbox.duplicate_deliveries_detected,
                    inbox.duplicate_recoveries_completed,
                    quarantines.quarantined_messages,
                    conflicts.conflicting_duplicates,
                    CURRENT_TIMESTAMP AS observed_at
                FROM org, outbox, inbox, quarantines, conflicts
                """
            )
        ).one()

        organization_id = OrganizationId(row.org_id)
        unknown_total = int(row.unknown_results_total or 0)
        unknown_reconcilable = int(row.unknown_results_reconcilable or 0)
        unknown_human = max(unknown_total - unknown_reconcilable, 0)
        conflicting_duplicates = int(row.conflicting_duplicates or 0)
        if conflicting_duplicates > 0:
            condition = OperationalDiagnosticCondition.INCONSISTENT
            recommended_action = "INVESTIGATE"
            automatic_retry_allowed = False
            reason_code = "DIAGNOSTIC_CONFLICT_DETECTED"
        elif unknown_total > 0:
            condition = OperationalDiagnosticCondition.INDETERMINATE
            recommended_action = "RECONCILE"
            automatic_retry_allowed = False
            reason_code = "EXTERNAL_EFFECT_MAY_HAVE_OCCURRED"
        else:
            condition = OperationalDiagnosticCondition.NORMAL
            recommended_action = None
            automatic_retry_allowed = False
            reason_code = None

        observed_at = (
            row.observed_at.replace(tzinfo=UTC)
            if row.observed_at.tzinfo is None
            else row.observed_at
        )
        last_reconciliation_at = row.last_reconciliation_at
        if last_reconciliation_at is not None and last_reconciliation_at.tzinfo is None:
            last_reconciliation_at = last_reconciliation_at.replace(tzinfo=UTC)

        return OperationalSupportSummary(
            organization_id=organization_id,
            observed_at=observed_at,
            scope="organization",
            filters=(),
            diagnostic_condition=condition,
            total_pending_outbox=int(row.total_pending_outbox or 0),
            active_claims=int(row.active_claims or 0),
            expired_claims=int(row.expired_claims or 0),
            unknown_results_total=unknown_total,
            unknown_results_reconcilable=unknown_reconcilable,
            unknown_results_human_intervention=unknown_human,
            quarantined_messages=int(row.quarantined_messages or 0),
            duplicate_deliveries_detected=int(row.duplicate_deliveries_detected or 0),
            duplicate_recoveries_completed=int(row.duplicate_recoveries_completed or 0),
            oldest_pending_age_seconds=(
                float(row.oldest_pending_age_seconds)
                if row.oldest_pending_age_seconds is not None
                else None
            ),
            oldest_unknown_age_seconds=(
                float(row.oldest_unknown_age_seconds)
                if row.oldest_unknown_age_seconds is not None
                else None
            ),
            last_reconciliation_at=last_reconciliation_at,
            recommended_action=recommended_action,
            automatic_retry_allowed=automatic_retry_allowed,
            reason_code=reason_code,
        )
