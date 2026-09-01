from datetime import UTC, datetime
from typing import cast
from uuid import uuid4

import pytest

from packages.livestock_application.market_supply_audit import (
    InMemoryMarketSupplyQueryAuditRepository,
    MarketSupplyAggregateQueryAuditPlanner,
    MarketSupplyAggregateQueryAuditRequest,
    MarketSupplyAuditExternalDisposition,
    MarketSupplyAuditOutcome,
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
from packages.shared_kernel import OrganizationId, TypedId

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)
_DEFAULT_PRIVACY = object()


def _authorization(
    *,
    result: MarketSupplyAuthorizationResult = MarketSupplyAuthorizationResult.PERMITTED,
    reason: MarketSupplyAuthorizationReason = MarketSupplyAuthorizationReason.PERMITTED,
) -> MarketSupplyAuthorizationAssessment:
    return MarketSupplyAuthorizationAssessment(
        result=result,
        reason=reason,
        access_purpose=MARKET_SUPPLY_AGGREGATE_ASSESSMENT,
        field_scope_profile=MARKET_SUPPLY_AGGREGATE_FIELD_SCOPE,
    )


def _privacy(
    *,
    decision: AggregationPrivacyDecision = AggregationPrivacyDecision.PERMITTED,
    reasons: tuple[AggregationPrivacyReason, ...] = (AggregationPrivacyReason.PERMITTED,),
) -> AggregationPrivacyAssessment:
    return AggregationPrivacyAssessment(
        decision=decision,
        reasons=reasons,
        policy_version=1,
    )


def _request(
    *,
    requester: OrganizationId | None = None,
    beneficiary: OrganizationId | None = None,
    policy_id: TypedId | None = None,
    authorization: MarketSupplyAuthorizationAssessment | None = None,
    privacy: AggregationPrivacyAssessment | None | object = _DEFAULT_PRIVACY,
) -> MarketSupplyAggregateQueryAuditRequest:
    requester_id = requester or OrganizationId.new()
    beneficiary_id = beneficiary or OrganizationId.new()
    privacy_assessment = _privacy() if privacy is _DEFAULT_PRIVACY else privacy
    return MarketSupplyAggregateQueryAuditRequest(
        audit_owner_organization_id=OrganizationId.new(),
        requester_organization_id=requester_id,
        beneficiary_organization_id=beneficiary_id,
        policy_id=policy_id or TypedId.new("policy"),
        access_purpose=MARKET_SUPPLY_AGGREGATE_ASSESSMENT,
        field_scope_profile=MARKET_SUPPLY_AGGREGATE_FIELD_SCOPE,
        query_fingerprint=AggregationQueryFingerprint(
            requester_organization_id=requester_id,
            beneficiary_organization_id=beneficiary_id,
            access_purpose=MARKET_SUPPLY_AGGREGATE_ASSESSMENT,
            policy_context_digest="policy:v1:reference:2026-08-28",
            filter_fingerprint="region=macro-a",
            result_subject_count=42,
            requested_at=NOW,
        ),
        recorded_at=NOW,
        authorization=authorization or _authorization(),
        privacy=cast(AggregationPrivacyAssessment | None, privacy_assessment),
        grant_id=uuid4(),
    )


def _disclosure(
    query_fingerprint: AggregationQueryFingerprint,
    *,
    candidate_population_digest: str = "population:sha256:abc",
    state: DisclosureDecisionState = DisclosureDecisionState.ALLOW,
    reasons: tuple[str, ...] = ("PERMITTED",),
) -> DisclosureDecision:
    return DisclosureDecision(
        state=state,
        reason_codes=reasons,
        privacy_policy_version=1,
        query_fingerprint=query_fingerprint,
        candidate_population_digest=candidate_population_digest,
        evaluated_at=NOW,
    )


def _audit_record(
    *,
    request: MarketSupplyAggregateQueryAuditRequest | None = None,
    result_digest: str | None = "result:sha256:released",
    population_digest: str | None = "population:sha256:included",
) -> MarketSupplyQueryAuditRecord:
    audit_request = request or _request()
    envelope = MarketSupplyAggregateQueryAuditPlanner().plan(audit_request)
    return MarketSupplyQueryAuditRecord.from_envelope(
        audit_id=TypedId.new("market_supply_query_audit"),
        envelope=envelope,
        policy_version=3,
        privacy_profile_id="market-supply-aggregate-test",
        authorization_context_digest="authorization:sha256:abc",
        candidate_population_digest="population:sha256:abc",
        reference_time=NOW,
        knowledge_cutoff=NOW,
        requested_at=NOW,
        disclosure_decision=_disclosure(audit_request.query_fingerprint),
        result_digest=result_digest,
        revocation_state=MarketSupplyRevocationState.NOT_REVOKED,
        correlation_id=TypedId.new("correlation"),
        idempotency_reference="idempotency-key:test",
        semantic_request_digest="request:sha256:abc",
        population_digest=population_digest,
    )


def test_denied_authorization_produces_uniform_not_released_envelope() -> None:
    request = _request(
        authorization=_authorization(
            result=MarketSupplyAuthorizationResult.DENIED,
            reason=MarketSupplyAuthorizationReason.MISSING_GRANT,
        ),
        privacy=None,
    )

    envelope = MarketSupplyAggregateQueryAuditPlanner().plan(request)

    assert envelope.outcome is MarketSupplyAuditOutcome.DENIED_BY_AUTHORIZATION
    assert (
        envelope.external_disposition is MarketSupplyAuditExternalDisposition.UNIFORM_NOT_RELEASED
    )
    assert envelope.authorization_reason == "MISSING_GRANT"
    assert envelope.privacy_reasons == ()


@pytest.mark.parametrize(
    ("reason", "expected_outcome"),
    [
        (
            MarketSupplyAuthorizationReason.PURPOSE_MISMATCH,
            MarketSupplyAuditOutcome.PURPOSE_MISMATCH,
        ),
        (MarketSupplyAuthorizationReason.REVOKED_GRANT, MarketSupplyAuditOutcome.GRANT_REVOKED),
    ],
)
def test_authorization_failures_keep_specific_internal_outcome_but_uniform_public_disposition(
    reason: MarketSupplyAuthorizationReason,
    expected_outcome: MarketSupplyAuditOutcome,
) -> None:
    request = _request(
        authorization=_authorization(
            result=MarketSupplyAuthorizationResult.DENIED,
            reason=reason,
        ),
        privacy=None,
    )

    envelope = MarketSupplyAggregateQueryAuditPlanner().plan(request)

    assert envelope.outcome is expected_outcome
    assert (
        envelope.external_disposition is MarketSupplyAuditExternalDisposition.UNIFORM_NOT_RELEASED
    )
    assert envelope.authorization_reason == reason.value


def test_privacy_suppression_preserves_internal_reason_without_release() -> None:
    request = _request(
        privacy=_privacy(
            decision=AggregationPrivacyDecision.SUPPRESSED,
            reasons=(AggregationPrivacyReason.DIFFERENCING_RISK,),
        ),
    )

    envelope = MarketSupplyAggregateQueryAuditPlanner().plan(request)

    assert envelope.outcome is MarketSupplyAuditOutcome.SUPPRESSED_BY_PRIVACY
    assert (
        envelope.external_disposition is MarketSupplyAuditExternalDisposition.UNIFORM_NOT_RELEASED
    )
    assert envelope.authorization_reason == "PERMITTED"
    assert envelope.privacy_reasons == ("DIFFERENCING_RISK",)


def test_release_requires_permitted_authorization_and_privacy() -> None:
    envelope = MarketSupplyAggregateQueryAuditPlanner().plan(_request())

    assert envelope.outcome is MarketSupplyAuditOutcome.RELEASED
    assert envelope.external_disposition is MarketSupplyAuditExternalDisposition.RELEASE_AGGREGATE
    assert envelope.authorization_reason == "PERMITTED"
    assert envelope.privacy_reasons == ("PERMITTED",)


def test_privacy_assessment_is_required_after_authorization_permits() -> None:
    with pytest.raises(ValueError, match="privacy assessment"):
        MarketSupplyAggregateQueryAuditPlanner().plan(_request(privacy=None))


def test_envelope_rejects_query_fingerprint_for_another_requester() -> None:
    request = _request()
    with pytest.raises(ValueError, match="requester"):
        MarketSupplyAggregateQueryAuditPlanner().plan(
            MarketSupplyAggregateQueryAuditRequest(
                audit_owner_organization_id=request.audit_owner_organization_id,
                requester_organization_id=OrganizationId.new(),
                beneficiary_organization_id=request.beneficiary_organization_id,
                policy_id=request.policy_id,
                access_purpose=request.access_purpose,
                field_scope_profile=request.field_scope_profile,
                query_fingerprint=request.query_fingerprint,
                recorded_at=request.recorded_at,
                authorization=request.authorization,
                privacy=request.privacy,
                grant_id=request.grant_id,
            ),
        )


def test_envelope_requires_utc_recorded_at() -> None:
    request = _request()
    with pytest.raises(ValueError, match="recorded_at"):
        MarketSupplyAggregateQueryAuditPlanner().plan(
            MarketSupplyAggregateQueryAuditRequest(
                audit_owner_organization_id=request.audit_owner_organization_id,
                requester_organization_id=request.requester_organization_id,
                beneficiary_organization_id=request.beneficiary_organization_id,
                policy_id=request.policy_id,
                access_purpose=request.access_purpose,
                field_scope_profile=request.field_scope_profile,
                query_fingerprint=request.query_fingerprint,
                recorded_at=datetime(2026, 8, 28, 12, 0),
                authorization=request.authorization,
                privacy=request.privacy,
                grant_id=request.grant_id,
            ),
        )


def test_query_audit_record_links_envelope_disclosure_and_population_digest() -> None:
    request = _request()
    record = _audit_record(request=request)

    assert record.outcome is MarketSupplyAuditOutcome.RELEASED
    assert record.disclosure_state is DisclosureDecisionState.ALLOW
    assert record.candidate_population_digest == "population:sha256:abc"
    assert record.population_digest == "population:sha256:included"
    assert record.query_fingerprint == request.query_fingerprint
    assert record.reference_time == NOW
    assert record.knowledge_cutoff == NOW
    assert record.record_digest()


def test_query_audit_record_rejects_divergent_disclosure_population_digest() -> None:
    request = _request()
    envelope = MarketSupplyAggregateQueryAuditPlanner().plan(request)

    with pytest.raises(ValueError, match="population digest"):
        MarketSupplyQueryAuditRecord.from_envelope(
            audit_id=TypedId.new("market_supply_query_audit"),
            envelope=envelope,
            policy_version=1,
            privacy_profile_id="market-supply-aggregate-test",
            authorization_context_digest="authorization:sha256:abc",
            candidate_population_digest="population:sha256:abc",
            reference_time=NOW,
            knowledge_cutoff=NOW,
            requested_at=NOW,
            disclosure_decision=_disclosure(
                request.query_fingerprint,
                candidate_population_digest="population:sha256:different",
            ),
            result_digest="result:sha256:released",
            revocation_state=MarketSupplyRevocationState.NOT_REVOKED,
            correlation_id=TypedId.new("correlation"),
            idempotency_reference="idempotency-key:test",
            semantic_request_digest="request:sha256:abc",
        )


def test_query_audit_record_requires_result_digest_for_released_result() -> None:
    with pytest.raises(ValueError, match="result_digest"):
        _audit_record(result_digest=None)


def test_query_audit_repository_is_append_only() -> None:
    repository = InMemoryMarketSupplyQueryAuditRepository()
    record = _audit_record()

    repository.append(record)

    assert repository.get(record.audit_id) == record
    with pytest.raises(ValueError, match="append-only"):
        repository.append(record)


def test_query_audit_repository_finds_related_history_without_payloads() -> None:
    repository = InMemoryMarketSupplyQueryAuditRepository()
    request = _request()
    related = _audit_record(request=request)
    unrelated_request = _request(requester=OrganizationId.new())
    unrelated = _audit_record(request=unrelated_request)

    repository.append(related)
    repository.append(unrelated)

    records = repository.find_related(
        requester_organization_id=request.requester_organization_id,
        beneficiary_organization_id=request.beneficiary_organization_id,
        access_purpose=request.access_purpose,
        policy_context_digest=request.query_fingerprint.policy_context_digest,
    )

    assert records == (related,)


def test_query_audit_repository_exposes_related_fingerprints_for_disclosure_history() -> None:
    repository = InMemoryMarketSupplyQueryAuditRepository()
    request = _request()
    related = _audit_record(request=request)
    repository.append(related)

    fingerprints = repository.find_related_query_fingerprints(
        requester_organization_id=request.requester_organization_id,
        beneficiary_organization_id=request.beneficiary_organization_id,
        access_purpose=request.access_purpose,
        policy_context_digest=request.query_fingerprint.policy_context_digest,
    )

    assert fingerprints == (request.query_fingerprint,)
