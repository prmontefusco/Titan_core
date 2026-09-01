from datetime import UTC, datetime
from typing import Any, cast
from uuid import uuid4

from sqlalchemy import Connection

from packages.livestock_application.market_supply_audit import (
    MarketSupplyAggregateQueryAuditPlanner,
    MarketSupplyAggregateQueryAuditRequest,
    MarketSupplyQueryAuditRecord,
    MarketSupplyRevocationState,
)
from packages.livestock_application.market_supply_authorization import (
    MARKET_SUPPLY_AGGREGATE_ASSESSMENT,
    MARKET_SUPPLY_AGGREGATE_FIELD_SCOPE,
    MarketSupplyAuthorizationAssessment,
    MarketSupplyAuthorizationReason,
    MarketSupplyAuthorizationResult,
)
from packages.livestock_application.market_supply_privacy import (
    AggregationPrivacyAssessment,
    AggregationPrivacyDecision,
    AggregationPrivacyReason,
    AggregationQueryFingerprint,
    DisclosureDecision,
    DisclosureDecisionState,
)
from packages.livestock_infrastructure.persistence.market_supply_query_audit_repository import (
    TransactionalMarketSupplyQueryAuditRepository,
)
from packages.shared_kernel import OrganizationId, TypedId

NOW = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)


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


def _record() -> MarketSupplyQueryAuditRecord:
    requester = OrganizationId.new()
    beneficiary = OrganizationId.new()
    query = AggregationQueryFingerprint(
        requester_organization_id=requester,
        beneficiary_organization_id=beneficiary,
        access_purpose=MARKET_SUPPLY_AGGREGATE_ASSESSMENT,
        policy_context_digest="population:sha256:context",
        filter_fingerprint="region=macro-a",
        result_subject_count=42,
        requested_at=NOW,
    )
    request = MarketSupplyAggregateQueryAuditRequest(
        audit_owner_organization_id=requester,
        requester_organization_id=requester,
        beneficiary_organization_id=beneficiary,
        policy_id=TypedId.new("policy"),
        access_purpose=MARKET_SUPPLY_AGGREGATE_ASSESSMENT,
        field_scope_profile=MARKET_SUPPLY_AGGREGATE_FIELD_SCOPE,
        query_fingerprint=query,
        recorded_at=NOW,
        authorization=MarketSupplyAuthorizationAssessment(
            result=MarketSupplyAuthorizationResult.PERMITTED,
            reason=MarketSupplyAuthorizationReason.PERMITTED,
            access_purpose=MARKET_SUPPLY_AGGREGATE_ASSESSMENT,
            field_scope_profile=MARKET_SUPPLY_AGGREGATE_FIELD_SCOPE,
        ),
        privacy=AggregationPrivacyAssessment(
            decision=AggregationPrivacyDecision.PERMITTED,
            reasons=(AggregationPrivacyReason.PERMITTED,),
            policy_version=1,
        ),
        grant_id=uuid4(),
    )
    envelope = MarketSupplyAggregateQueryAuditPlanner().plan(request)
    return MarketSupplyQueryAuditRecord.from_envelope(
        audit_id=TypedId.new("market_supply_query_audit"),
        envelope=envelope,
        policy_version=1,
        privacy_profile_id="market-supply-aggregate-test",
        authorization_context_digest="authorization:sha256:test",
        candidate_population_digest="population:sha256:context",
        population_digest="population:sha256:internal",
        reference_time=NOW,
        knowledge_cutoff=NOW,
        requested_at=NOW,
        disclosure_decision=DisclosureDecision(
            state=DisclosureDecisionState.ALLOW,
            reason_codes=("PERMITTED",),
            privacy_policy_version=1,
            query_fingerprint=query,
            candidate_population_digest="population:sha256:context",
            evaluated_at=NOW,
        ),
        result_digest="result:sha256:released",
        revocation_state=MarketSupplyRevocationState.NOT_REVOKED,
        correlation_id=TypedId.new("correlation"),
        idempotency_reference="idempotency-key:test",
        semantic_request_digest="request:sha256:test",
    )


def test_transactional_repository_append_writes_minimized_audit_row() -> None:
    connection = _Connection()
    repository = TransactionalMarketSupplyQueryAuditRepository(
        cast(Connection, connection),
    )
    record = _record()

    repository.append(record)

    assert connection.params is not None
    assert connection.params["audit_id"] == record.audit_id.value
    assert connection.params["record_owner_organization_id"] == (
        record.audit_owner_organization_id.value
    )
    assert connection.params["query_fingerprint_digest"]
    assert connection.params["policy_context_digest"] == (
        record.query_fingerprint.policy_context_digest
    )
    assert connection.params["decision_reason_codes"] == '["PERMITTED"]'
    assert connection.params["record_digest"] == record.record_digest()
    assert "animal_id" not in connection.params
    assert "evidence_payload" not in connection.params


def test_transactional_repository_find_related_returns_only_fingerprints() -> None:
    connection = _Connection()
    repository = TransactionalMarketSupplyQueryAuditRepository(
        cast(Connection, connection),
    )
    record = _record()
    repository.append(record)
    assert connection.params is not None
    connection.rows = [type("Row", (), connection.params)]

    fingerprints = repository.find_related_query_fingerprints(
        requester_organization_id=record.requester_organization_id,
        beneficiary_organization_id=record.beneficiary_organization_id,
        access_purpose=record.access_purpose,
        policy_context_digest=record.query_fingerprint.policy_context_digest,
    )

    assert fingerprints == (record.query_fingerprint,)
