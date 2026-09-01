from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest

from packages.core_application import IdempotencyConflict, IdempotencyService
from packages.core_application.idempotency import IdempotencyRequest, StoredIdempotencyResult
from packages.core_domain import CanonicalPayload
from packages.core_domain.policy_sharing import AuthorizationGrant
from packages.livestock_application.market_supply_audit import (
    InMemoryMarketSupplyQueryAuditRepository,
    MarketSupplyAggregateQueryAuditEnvelope,
    MarketSupplyAggregateQueryAuditPlanner,
    MarketSupplyAggregateQueryAuditRequest,
    MarketSupplyAuditOutcome,
    MarketSupplyQueryAuditRecord,
    MarketSupplyRevocationState,
)
from packages.livestock_application.market_supply_authorization import (
    MARKET_SUPPLY_AGGREGATE_ASSESSMENT,
    MARKET_SUPPLY_AGGREGATE_FIELD_SCOPE,
    MarketSupplyAuthorizationAssessment,
    MarketSupplyAuthorizationReason,
    MarketSupplyAuthorizationRequest,
    MarketSupplyAuthorizationResult,
)
from packages.livestock_application.market_supply_population import (
    CandidatePopulationCriteria,
    CandidatePopulationResolver,
    CandidatePopulationSnapshot,
    CandidatePopulationSubject,
)
from packages.livestock_application.market_supply_privacy import (
    AggregationGeographicPrecision,
    AggregationPrivacyAssessment,
    AggregationPrivacyDecision,
    AggregationPrivacyInput,
    AggregationPrivacyPolicy,
    AggregationPrivacyReason,
    AggregationQueryFingerprint,
    DisclosureDecision,
    DisclosureDecisionState,
)
from packages.livestock_application.market_supply_request import (
    MarketSupplyIdempotencyGate,
    MarketSupplyRequestIdentity,
)
from packages.livestock_application.market_supply_response import (
    MarketSupplyPublicAggregateResponse,
    MarketSupplyPublicResponseMapper,
    MarketSupplyPublicResponseStatus,
)
from packages.livestock_application.market_supply_workflow import (
    MarketSupplyAggregateGateRequest,
    MarketSupplyAggregateGateWorkflow,
    MarketSupplyAggregateResult,
    MarketSupplyAuditRecordContext,
    MarketSupplyIdempotentAggregateGateWorkflow,
)
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)


class FailingMarketSupplyQueryAuditRepository(InMemoryMarketSupplyQueryAuditRepository):
    def append(self, record: MarketSupplyQueryAuditRecord) -> None:
        raise RuntimeError("audit store unavailable")


class RecordingMarketSupplyPublicResponseMapper(MarketSupplyPublicResponseMapper):
    def __init__(self) -> None:
        self.called = False

    def map_aggregate(
        self,
        *,
        envelope: MarketSupplyAggregateQueryAuditEnvelope,
        aggregate_payload: Mapping[str, Any] | None,
    ) -> MarketSupplyPublicAggregateResponse:
        self.called = True
        return super().map_aggregate(
            envelope=envelope,
            aggregate_payload=aggregate_payload,
        )


class StaticAuthorizationGrantReader:
    def __init__(self, grant: AuthorizationGrant | None) -> None:
        self.grant = grant

    def get_by_id(self, grant_id: UUID) -> AuthorizationGrant | None:
        return self.grant


class InMemoryMarketSupplyIdempotencyStore:
    def __init__(self) -> None:
        self.records: dict[tuple[str, str, str], StoredIdempotencyResult] = {}

    def acquire(self, request: IdempotencyRequest) -> StoredIdempotencyResult | None:
        scope = (request.key, request.purpose, request.operation)
        existing = self.records.get(scope)
        if existing is None:
            self.records[scope] = StoredIdempotencyResult(
                request.intent_digest,
                None,
                None,
                None,
            )
        return existing

    def complete(self, request: IdempotencyRequest, result: CanonicalPayload) -> None:
        self.records[(request.key, request.purpose, request.operation)] = StoredIdempotencyResult(
            request.intent_digest,
            result.schema,
            result.version,
            result.canonical_bytes,
        )


def _authorization_request(
    *,
    owner: OrganizationId | None = None,
    beneficiary: OrganizationId | None = None,
    policy_id: TypedId | None = None,
) -> MarketSupplyAuthorizationRequest:
    return MarketSupplyAuthorizationRequest(
        owner_organization_id=owner or OrganizationId.new(),
        beneficiary_organization_id=beneficiary or OrganizationId.new(),
        policy_id=policy_id or TypedId.new("policy"),
        access_purpose=MARKET_SUPPLY_AGGREGATE_ASSESSMENT,
        field_scope_profile=MARKET_SUPPLY_AGGREGATE_FIELD_SCOPE,
        requested_at=NOW,
    )


def _grant(
    request: MarketSupplyAuthorizationRequest,
    *,
    revoked_at: datetime | None = None,
) -> AuthorizationGrant:
    return AuthorizationGrant(
        grant_id=uuid4(),
        owner_organization_id=request.owner_organization_id,
        beneficiary_organization_id=request.beneficiary_organization_id,
        policy_id=request.policy_id,
        policy_version_id=TypedId.new("rule"),
        access_purpose=request.access_purpose,
        field_scope_profile=request.field_scope_profile,
        valid_from=NOW - timedelta(days=1),
        valid_until=NOW + timedelta(days=1),
        status="ATIVO",
        created_at=NOW - timedelta(days=1),
        created_by="actor:test",
        revoked_at=revoked_at,
    )


def _fingerprint(
    request: MarketSupplyAuthorizationRequest,
    *,
    policy_context_digest: str = "policy:v1:reference:2026-08-28",
    filter_fingerprint: str = "region=macro-a",
    result_subject_count: int = 42,
) -> AggregationQueryFingerprint:
    return AggregationQueryFingerprint(
        requester_organization_id=request.beneficiary_organization_id,
        beneficiary_organization_id=request.beneficiary_organization_id,
        access_purpose=request.access_purpose,
        policy_context_digest=policy_context_digest,
        filter_fingerprint=filter_fingerprint,
        result_subject_count=result_subject_count,
        requested_at=NOW,
    )


def _population_snapshot(
    request: MarketSupplyAuthorizationRequest,
    *,
    included_count: int = 42,
) -> CandidatePopulationSnapshot:
    criteria = CandidatePopulationCriteria(
        organization_id=request.owner_organization_id,
        purpose=request.access_purpose,
        policy_id=request.policy_id,
        policy_version=1,
        reference_time=NOW,
        knowledge_cutoff=NOW,
    )
    subjects = tuple(
        CandidatePopulationSubject(
            subject_id=TypedId.new("animal"),
            organization_id=request.owner_organization_id,
            known_at=NOW,
        )
        for _ in range(included_count)
    )
    return CandidatePopulationResolver().resolve(
        criteria=criteria,
        subjects=subjects,
        resolved_at=NOW,
    )


def _privacy_input(
    query: AggregationQueryFingerprint,
    *,
    subject_count: int = 42,
) -> AggregationPrivacyInput:
    return AggregationPrivacyInput(
        privacy_policy=AggregationPrivacyPolicy(
            policy_version=1,
            minimum_organizations=1,
            minimum_properties=1,
            minimum_subjects=20,
            max_filter_count_without_review=4,
            repeated_query_window=timedelta(hours=6),
        ),
        organization_count=1,
        property_count=1,
        subject_count=subject_count,
        geographic_precision=AggregationGeographicPrecision.REGION,
        filter_count=2,
        rare_attribute_filters=(),
        current_query=query,
    )


def _audit_context(
    snapshot: CandidatePopulationSnapshot,
    *,
    semantic_request_digest: str = "request:sha256:workflow",
) -> MarketSupplyAuditRecordContext:
    universe = snapshot.internal_universe_summary()
    return MarketSupplyAuditRecordContext(
        audit_id=TypedId.new("market_supply_query_audit"),
        policy_version=1,
        privacy_profile_id="market-supply-aggregate-test",
        authorization_context_digest="authorization:sha256:workflow",
        candidate_population_digest=snapshot.snapshot_digest,
        reference_time=NOW,
        knowledge_cutoff=NOW,
        requested_at=NOW,
        revocation_state=MarketSupplyRevocationState.NOT_REVOKED,
        correlation_id=TypedId.new("correlation"),
        idempotency_reference="idempotency-key:workflow",
        semantic_request_digest=semantic_request_digest,
        population_digest=universe.population_digest,
    )


def _pre_population_audit_context(
    fingerprint: AggregationQueryFingerprint,
    *,
    semantic_request_digest: str = "request:sha256:workflow",
) -> MarketSupplyAuditRecordContext:
    return MarketSupplyAuditRecordContext(
        audit_id=TypedId.new("market_supply_query_audit"),
        policy_version=1,
        privacy_profile_id="market-supply-aggregate-test",
        authorization_context_digest="authorization:sha256:workflow",
        candidate_population_digest=fingerprint.policy_context_digest,
        reference_time=NOW,
        knowledge_cutoff=NOW,
        requested_at=NOW,
        revocation_state=MarketSupplyRevocationState.NOT_REVOKED,
        correlation_id=TypedId.new("correlation"),
        idempotency_reference="idempotency-key:workflow",
        semantic_request_digest=semantic_request_digest,
        population_digest=None,
    )


def _request_identity(
    request: MarketSupplyAuthorizationRequest,
    snapshot: CandidatePopulationSnapshot,
    *,
    idempotency_key: str = "market-supply-workflow-key",
    reference_time: datetime = NOW,
    knowledge_cutoff: datetime = NOW,
) -> MarketSupplyRequestIdentity:
    return MarketSupplyRequestIdentity(
        buyer_organization_id=request.beneficiary_organization_id,
        purpose=request.access_purpose,
        policy_id=request.policy_id,
        policy_version=snapshot.criteria.policy_version,
        demand_context_digest="demand:sha256:workflow",
        candidate_criteria_digest=snapshot.criteria_digest,
        reference_time=reference_time,
        knowledge_cutoff=knowledge_cutoff,
        idempotency_key=idempotency_key,
    )


def _principal(organization_id: OrganizationId) -> UniversalReference:
    return UniversalReference(
        target_id=TypedId.new("user"),
        organization_id=organization_id,
        contract_version=1,
    )


def _previous_audit_record(
    *,
    authorization_request: MarketSupplyAuthorizationRequest,
    fingerprint: AggregationQueryFingerprint,
    snapshot: CandidatePopulationSnapshot,
) -> MarketSupplyQueryAuditRecord:
    authorization = MarketSupplyAuthorizationAssessment(
        result=MarketSupplyAuthorizationResult.PERMITTED,
        reason=MarketSupplyAuthorizationReason.PERMITTED,
        access_purpose=authorization_request.access_purpose,
        field_scope_profile=authorization_request.field_scope_profile,
    )
    privacy = AggregationPrivacyAssessment(
        decision=AggregationPrivacyDecision.PERMITTED,
        reasons=(AggregationPrivacyReason.PERMITTED,),
        policy_version=1,
    )
    envelope = MarketSupplyAggregateQueryAuditPlanner().plan(
        MarketSupplyAggregateQueryAuditRequest(
            audit_owner_organization_id=authorization_request.owner_organization_id,
            requester_organization_id=authorization_request.beneficiary_organization_id,
            beneficiary_organization_id=authorization_request.beneficiary_organization_id,
            policy_id=authorization_request.policy_id,
            access_purpose=authorization_request.access_purpose,
            field_scope_profile=authorization_request.field_scope_profile,
            query_fingerprint=fingerprint,
            recorded_at=NOW - timedelta(minutes=5),
            authorization=authorization,
            privacy=privacy,
            grant_id=uuid4(),
        ),
    )
    return MarketSupplyQueryAuditRecord.from_envelope(
        audit_id=TypedId.new("market_supply_query_audit"),
        envelope=envelope,
        policy_version=1,
        privacy_profile_id="market-supply-aggregate-test",
        authorization_context_digest="authorization:sha256:previous",
        candidate_population_digest=snapshot.snapshot_digest,
        reference_time=NOW,
        knowledge_cutoff=NOW,
        requested_at=NOW - timedelta(minutes=5),
        disclosure_decision=DisclosureDecision(
            state=DisclosureDecisionState.ALLOW,
            reason_codes=("PERMITTED",),
            privacy_policy_version=1,
            query_fingerprint=fingerprint,
            candidate_population_digest=snapshot.snapshot_digest,
            evaluated_at=NOW - timedelta(minutes=5),
        ),
        result_digest="result:sha256:previous",
        revocation_state=MarketSupplyRevocationState.NOT_REVOKED,
        correlation_id=TypedId.new("correlation"),
        idempotency_reference="idempotency-key:previous",
        semantic_request_digest="request:sha256:previous",
        population_digest=snapshot.internal_universe_summary().population_digest,
    )


def test_missing_grant_denies_before_privacy_assessment() -> None:
    authorization_request = _authorization_request()
    fingerprint = _fingerprint(authorization_request)

    result = MarketSupplyAggregateGateWorkflow().assess_aggregate_access(
        MarketSupplyAggregateGateRequest(
            audit_owner_organization_id=authorization_request.owner_organization_id,
            authorization_request=authorization_request,
            query_policy_id=authorization_request.policy_id,
            query_fingerprint=fingerprint,
            recorded_at=NOW,
            grant=None,
            privacy_input=None,
            aggregate_payload={"ready_now": 42},
        ),
    )

    assert result.audit_envelope.outcome is MarketSupplyAuditOutcome.DENIED_BY_AUTHORIZATION
    assert (
        result.audit_envelope.authorization_reason == MarketSupplyAuthorizationReason.MISSING_GRANT
    )
    assert result.public_response.status is MarketSupplyPublicResponseStatus.NOT_RELEASED
    assert result.public_response.aggregate is None


def test_auditable_workflow_persists_authorization_denial_before_population() -> None:
    authorization_request = _authorization_request()
    fingerprint = _fingerprint(authorization_request)
    repository = InMemoryMarketSupplyQueryAuditRepository()

    result = MarketSupplyAggregateGateWorkflow(
        audit_repository=repository,
        grant_reader=StaticAuthorizationGrantReader(None),
    ).assess_aggregate_access(
        MarketSupplyAggregateGateRequest(
            audit_owner_organization_id=authorization_request.owner_organization_id,
            authorization_request=authorization_request,
            query_policy_id=authorization_request.policy_id,
            query_fingerprint=fingerprint,
            recorded_at=NOW,
            grant=None,
            privacy_input=None,
            aggregate_payload={"ready_now": 42},
            audit_record_context=_pre_population_audit_context(fingerprint),
        ),
    )

    assert result.audit_envelope.outcome is MarketSupplyAuditOutcome.DENIED_BY_AUTHORIZATION
    assert result.public_response.status is MarketSupplyPublicResponseStatus.NOT_RELEASED
    assert result.audit_record is not None
    assert result.audit_record.result_digest is None
    assert result.audit_record.population_digest is None
    assert result.audit_record.candidate_population_digest == fingerprint.policy_context_digest
    assert result.aggregate_result is None
    assert repository.get(result.audit_record.audit_id) == result.audit_record


def test_permitted_flow_requires_durable_audit_before_public_release() -> None:
    authorization_request = _authorization_request()
    snapshot = _population_snapshot(authorization_request)
    fingerprint = _fingerprint(
        authorization_request,
        policy_context_digest=snapshot.criteria.policy_context_digest(),
    )

    with pytest.raises(ValueError, match="audit record duravel"):
        MarketSupplyAggregateGateWorkflow().assess_aggregate_access(
            MarketSupplyAggregateGateRequest(
                audit_owner_organization_id=authorization_request.owner_organization_id,
                authorization_request=authorization_request,
                query_policy_id=authorization_request.policy_id,
                query_fingerprint=fingerprint,
                recorded_at=NOW,
                grant=_grant(authorization_request),
                population_snapshot=snapshot,
                privacy_input=_privacy_input(fingerprint),
                aggregate_payload={"ready_now": 42},
            ),
        )


def test_permitted_flow_releases_supplied_aggregate_payload_after_durable_audit() -> None:
    authorization_request = _authorization_request()
    snapshot = _population_snapshot(authorization_request)
    fingerprint = _fingerprint(
        authorization_request,
        policy_context_digest=snapshot.criteria.policy_context_digest(),
    )
    repository = InMemoryMarketSupplyQueryAuditRepository()
    audit_context = _audit_context(snapshot)

    result = MarketSupplyAggregateGateWorkflow(
        audit_repository=repository,
        grant_reader=StaticAuthorizationGrantReader(_grant(authorization_request)),
    ).assess_aggregate_access(
        MarketSupplyAggregateGateRequest(
            audit_owner_organization_id=authorization_request.owner_organization_id,
            authorization_request=authorization_request,
            query_policy_id=authorization_request.policy_id,
            query_fingerprint=fingerprint,
            recorded_at=NOW,
            grant=_grant(authorization_request),
            population_snapshot=snapshot,
            privacy_input=_privacy_input(fingerprint),
            aggregate_payload={"ready_now": 42},
            audit_record_context=audit_context,
        ),
    )

    assert result.audit_envelope.outcome is MarketSupplyAuditOutcome.RELEASED
    assert result.audit_record is not None
    assert repository.get(audit_context.audit_id) == result.audit_record
    assert result.public_response.status is MarketSupplyPublicResponseStatus.RELEASED
    assert result.public_response.aggregate == {"ready_now": 42}


def test_release_rejects_unapproved_public_payload_before_audit_append() -> None:
    authorization_request = _authorization_request()
    snapshot = _population_snapshot(authorization_request)
    fingerprint = _fingerprint(
        authorization_request,
        policy_context_digest=snapshot.criteria.policy_context_digest(),
    )
    repository = InMemoryMarketSupplyQueryAuditRepository()
    audit_context = _audit_context(snapshot)

    with pytest.raises(ValueError, match="identificadores"):
        MarketSupplyAggregateGateWorkflow(
            audit_repository=repository,
            grant_reader=StaticAuthorizationGrantReader(_grant(authorization_request)),
        ).assess_aggregate_access(
            MarketSupplyAggregateGateRequest(
                audit_owner_organization_id=authorization_request.owner_organization_id,
                authorization_request=authorization_request,
                query_policy_id=authorization_request.policy_id,
                query_fingerprint=fingerprint,
                recorded_at=NOW,
                grant=_grant(authorization_request),
                population_snapshot=snapshot,
                privacy_input=_privacy_input(fingerprint),
                aggregate_payload={"animal_id": "animal-1"},
                audit_record_context=audit_context,
            ),
        )

    assert repository.get(audit_context.audit_id) is None


def test_privacy_suppression_keeps_public_response_uniform() -> None:
    authorization_request = _authorization_request()
    fingerprint = _fingerprint(authorization_request, result_subject_count=10)

    result = MarketSupplyAggregateGateWorkflow().assess_aggregate_access(
        MarketSupplyAggregateGateRequest(
            audit_owner_organization_id=authorization_request.owner_organization_id,
            authorization_request=authorization_request,
            query_policy_id=authorization_request.policy_id,
            query_fingerprint=fingerprint,
            recorded_at=NOW,
            grant=_grant(authorization_request),
            privacy_input=_privacy_input(fingerprint, subject_count=10),
            aggregate_payload={"ready_now": 10},
        ),
    )

    assert result.audit_envelope.outcome is MarketSupplyAuditOutcome.SUPPRESSED_BY_PRIVACY
    assert result.public_response.status is MarketSupplyPublicResponseStatus.NOT_RELEASED
    assert result.public_response.aggregate is None


def test_auditable_workflow_requires_audit_context_for_not_released_outcomes() -> None:
    authorization_request = _authorization_request()
    fingerprint = _fingerprint(authorization_request)

    with pytest.raises(ValueError, match="workflow auditavel"):
        MarketSupplyAggregateGateWorkflow(
            audit_repository=InMemoryMarketSupplyQueryAuditRepository(),
            grant_reader=StaticAuthorizationGrantReader(_grant(authorization_request)),
        ).assess_aggregate_access(
            MarketSupplyAggregateGateRequest(
                audit_owner_organization_id=authorization_request.owner_organization_id,
                authorization_request=authorization_request,
                query_policy_id=authorization_request.policy_id,
                query_fingerprint=fingerprint,
                recorded_at=NOW,
                grant=None,
                privacy_input=None,
                aggregate_payload={"ready_now": 42},
            ),
        )


def test_permitted_authorization_requires_privacy_input() -> None:
    authorization_request = _authorization_request()
    fingerprint = _fingerprint(authorization_request)

    with pytest.raises(ValueError, match="privacy_input"):
        MarketSupplyAggregateGateWorkflow().assess_aggregate_access(
            MarketSupplyAggregateGateRequest(
                audit_owner_organization_id=authorization_request.owner_organization_id,
                authorization_request=authorization_request,
                query_policy_id=authorization_request.policy_id,
                query_fingerprint=fingerprint,
                recorded_at=NOW,
                grant=_grant(authorization_request),
                privacy_input=None,
                aggregate_payload={"ready_now": 42},
            ),
        )


def test_audit_owner_must_match_authorization_owner() -> None:
    authorization_request = _authorization_request()
    fingerprint = _fingerprint(authorization_request)

    with pytest.raises(ValueError, match="audit_owner_organization_id"):
        MarketSupplyAggregateGateRequest(
            audit_owner_organization_id=OrganizationId.new(),
            authorization_request=authorization_request,
            query_policy_id=authorization_request.policy_id,
            query_fingerprint=fingerprint,
            recorded_at=NOW,
            grant=None,
        )


def test_privacy_input_must_match_query_fingerprint() -> None:
    authorization_request = _authorization_request()
    fingerprint = _fingerprint(authorization_request)
    other = _fingerprint(authorization_request, filter_fingerprint="region=macro-b")

    with pytest.raises(ValueError, match="privacy_input.current_query"):
        MarketSupplyAggregateGateRequest(
            audit_owner_organization_id=authorization_request.owner_organization_id,
            authorization_request=authorization_request,
            query_policy_id=authorization_request.policy_id,
            query_fingerprint=fingerprint,
            recorded_at=NOW,
            grant=_grant(authorization_request),
            privacy_input=_privacy_input(other),
            aggregate_payload={"ready_now": 42},
        )


def test_population_snapshot_digest_must_match_query_fingerprint_context() -> None:
    authorization_request = _authorization_request()
    snapshot = _population_snapshot(authorization_request)
    fingerprint = _fingerprint(authorization_request)

    with pytest.raises(ValueError, match="policy_context_digest"):
        MarketSupplyAggregateGateRequest(
            audit_owner_organization_id=authorization_request.owner_organization_id,
            authorization_request=authorization_request,
            query_policy_id=authorization_request.policy_id,
            query_fingerprint=fingerprint,
            recorded_at=NOW,
            grant=_grant(authorization_request),
            population_snapshot=snapshot,
            privacy_input=_privacy_input(fingerprint),
            aggregate_payload={"ready_now": 42},
        )


def test_population_snapshot_count_must_match_query_fingerprint_count() -> None:
    authorization_request = _authorization_request()
    snapshot = _population_snapshot(authorization_request, included_count=2)
    fingerprint = _fingerprint(
        authorization_request,
        policy_context_digest=snapshot.criteria.policy_context_digest(),
        result_subject_count=42,
    )

    with pytest.raises(ValueError, match="result_subject_count"):
        MarketSupplyAggregateGateRequest(
            audit_owner_organization_id=authorization_request.owner_organization_id,
            authorization_request=authorization_request,
            query_policy_id=authorization_request.policy_id,
            query_fingerprint=fingerprint,
            recorded_at=NOW,
            grant=_grant(authorization_request),
            population_snapshot=snapshot,
            privacy_input=_privacy_input(fingerprint),
            aggregate_payload={"ready_now": 42},
        )


def test_privacy_subject_count_must_match_population_snapshot() -> None:
    authorization_request = _authorization_request()
    snapshot = _population_snapshot(authorization_request, included_count=2)
    fingerprint = _fingerprint(
        authorization_request,
        policy_context_digest=snapshot.criteria.policy_context_digest(),
        result_subject_count=2,
    )

    with pytest.raises(ValueError, match="subject_count"):
        MarketSupplyAggregateGateRequest(
            audit_owner_organization_id=authorization_request.owner_organization_id,
            authorization_request=authorization_request,
            query_policy_id=authorization_request.policy_id,
            query_fingerprint=fingerprint,
            recorded_at=NOW,
            grant=_grant(authorization_request),
            population_snapshot=snapshot,
            privacy_input=_privacy_input(fingerprint, subject_count=3),
            aggregate_payload={"ready_now": 2},
        )


def test_privacy_organization_count_must_match_population_snapshot() -> None:
    authorization_request = _authorization_request()
    snapshot = _population_snapshot(authorization_request)
    fingerprint = _fingerprint(
        authorization_request,
        policy_context_digest=snapshot.criteria.policy_context_digest(),
    )
    privacy_input = replace(_privacy_input(fingerprint), organization_count=2)

    with pytest.raises(ValueError, match="organization_count"):
        MarketSupplyAggregateGateRequest(
            audit_owner_organization_id=authorization_request.owner_organization_id,
            authorization_request=authorization_request,
            query_policy_id=authorization_request.policy_id,
            query_fingerprint=fingerprint,
            recorded_at=NOW,
            grant=_grant(authorization_request),
            population_snapshot=snapshot,
            privacy_input=privacy_input,
            aggregate_payload={"ready_now": 42},
        )


def test_privacy_property_count_must_match_population_snapshot_when_known() -> None:
    authorization_request = _authorization_request()
    criteria = CandidatePopulationCriteria(
        organization_id=authorization_request.owner_organization_id,
        purpose=authorization_request.access_purpose,
        policy_id=authorization_request.policy_id,
        policy_version=1,
        reference_time=NOW,
        knowledge_cutoff=NOW,
    )
    property_id = TypedId.new("property")
    subjects = tuple(
        CandidatePopulationSubject(
            subject_id=TypedId.new("animal"),
            organization_id=authorization_request.owner_organization_id,
            property_id=property_id,
            known_at=NOW,
        )
        for _ in range(2)
    )
    snapshot = CandidatePopulationResolver().resolve(
        criteria=criteria,
        subjects=subjects,
        resolved_at=NOW,
    )
    fingerprint = _fingerprint(
        authorization_request,
        policy_context_digest=snapshot.criteria.policy_context_digest(),
        result_subject_count=snapshot.included_count,
    )
    privacy_input = replace(
        _privacy_input(fingerprint, subject_count=snapshot.included_count),
        property_count=2,
    )

    with pytest.raises(ValueError, match="property_count"):
        MarketSupplyAggregateGateRequest(
            audit_owner_organization_id=authorization_request.owner_organization_id,
            authorization_request=authorization_request,
            query_policy_id=authorization_request.policy_id,
            query_fingerprint=fingerprint,
            recorded_at=NOW,
            grant=_grant(authorization_request),
            population_snapshot=snapshot,
            privacy_input=privacy_input,
            aggregate_payload={"ready_now": snapshot.included_count},
        )


def test_workflow_persists_audit_record_before_public_release() -> None:
    authorization_request = _authorization_request()
    snapshot = _population_snapshot(authorization_request)
    fingerprint = _fingerprint(
        authorization_request,
        policy_context_digest=snapshot.criteria.policy_context_digest(),
    )
    repository = InMemoryMarketSupplyQueryAuditRepository()
    audit_context = _audit_context(snapshot)

    result = MarketSupplyAggregateGateWorkflow(
        audit_repository=repository,
        grant_reader=StaticAuthorizationGrantReader(_grant(authorization_request)),
    ).assess_aggregate_access(
        MarketSupplyAggregateGateRequest(
            audit_owner_organization_id=authorization_request.owner_organization_id,
            authorization_request=authorization_request,
            query_policy_id=authorization_request.policy_id,
            query_fingerprint=fingerprint,
            recorded_at=NOW,
            grant=_grant(authorization_request),
            population_snapshot=snapshot,
            privacy_input=_privacy_input(fingerprint),
            aggregate_payload={"ready_now": 42},
            audit_record_context=audit_context,
        ),
    )

    assert result.public_response.status is MarketSupplyPublicResponseStatus.RELEASED
    assert result.audit_record is not None
    assert result.audit_record.result_digest is not None
    assert result.aggregate_result is not None
    assert result.aggregate_result.population_snapshot == snapshot
    assert result.aggregate_result.audit_record == result.audit_record
    assert result.aggregate_result.disclosure_decision.allows_external_release
    assert result.aggregate_result.aggregate_payload == {"ready_now": 42}
    assert repository.get(audit_context.audit_id) == result.audit_record


def test_aggregate_result_rejects_snapshot_disclosure_audit_mismatch() -> None:
    authorization_request = _authorization_request()
    snapshot = _population_snapshot(authorization_request)
    other_snapshot = _population_snapshot(authorization_request)
    fingerprint = _fingerprint(
        authorization_request,
        policy_context_digest=snapshot.criteria.policy_context_digest(),
    )
    repository = InMemoryMarketSupplyQueryAuditRepository()

    result = MarketSupplyAggregateGateWorkflow(
        audit_repository=repository,
        grant_reader=StaticAuthorizationGrantReader(_grant(authorization_request)),
    ).assess_aggregate_access(
        MarketSupplyAggregateGateRequest(
            audit_owner_organization_id=authorization_request.owner_organization_id,
            authorization_request=authorization_request,
            query_policy_id=authorization_request.policy_id,
            query_fingerprint=fingerprint,
            recorded_at=NOW,
            grant=_grant(authorization_request),
            population_snapshot=snapshot,
            privacy_input=_privacy_input(fingerprint),
            aggregate_payload={"ready_now": 42},
            audit_record_context=_audit_context(snapshot),
        ),
    )

    assert result.aggregate_result is not None
    with pytest.raises(ValueError, match="CandidatePopulationSnapshot"):
        MarketSupplyAggregateResult(
            population_snapshot=other_snapshot,
            disclosure_decision=result.aggregate_result.disclosure_decision,
            audit_record=result.aggregate_result.audit_record,
            aggregate_payload={"ready_now": 42},
        )


def test_auditable_workflow_requires_audit_context_before_public_release() -> None:
    authorization_request = _authorization_request()
    snapshot = _population_snapshot(authorization_request)
    fingerprint = _fingerprint(
        authorization_request,
        policy_context_digest=snapshot.criteria.policy_context_digest(),
    )

    with pytest.raises(ValueError, match="audit_record_context"):
        MarketSupplyAggregateGateWorkflow(
            audit_repository=InMemoryMarketSupplyQueryAuditRepository(),
            grant_reader=StaticAuthorizationGrantReader(_grant(authorization_request)),
        ).assess_aggregate_access(
            MarketSupplyAggregateGateRequest(
                audit_owner_organization_id=authorization_request.owner_organization_id,
                authorization_request=authorization_request,
                query_policy_id=authorization_request.policy_id,
                query_fingerprint=fingerprint,
                recorded_at=NOW,
                grant=_grant(authorization_request),
                population_snapshot=snapshot,
                privacy_input=_privacy_input(fingerprint),
                aggregate_payload={"ready_now": 42},
            ),
        )


def test_audit_append_failure_blocks_public_response_mapping() -> None:
    authorization_request = _authorization_request()
    snapshot = _population_snapshot(authorization_request)
    fingerprint = _fingerprint(
        authorization_request,
        policy_context_digest=snapshot.criteria.policy_context_digest(),
    )
    response_mapper = RecordingMarketSupplyPublicResponseMapper()

    with pytest.raises(RuntimeError, match="audit store unavailable"):
        MarketSupplyAggregateGateWorkflow(
            audit_repository=FailingMarketSupplyQueryAuditRepository(),
            grant_reader=StaticAuthorizationGrantReader(_grant(authorization_request)),
            response_mapper=response_mapper,
        ).assess_aggregate_access(
            MarketSupplyAggregateGateRequest(
                audit_owner_organization_id=authorization_request.owner_organization_id,
                authorization_request=authorization_request,
                query_policy_id=authorization_request.policy_id,
                query_fingerprint=fingerprint,
                recorded_at=NOW,
                grant=_grant(authorization_request),
                population_snapshot=snapshot,
                privacy_input=_privacy_input(fingerprint),
                aggregate_payload={"ready_now": 42},
                audit_record_context=_audit_context(snapshot),
            ),
        )

    assert response_mapper.called is False


def test_idempotent_workflow_replays_public_payload_without_duplicate_audit() -> None:
    authorization_request = _authorization_request()
    snapshot = _population_snapshot(authorization_request)
    fingerprint = _fingerprint(
        authorization_request,
        policy_context_digest=snapshot.criteria.policy_context_digest(),
    )
    identity = _request_identity(authorization_request, snapshot)
    repository = InMemoryMarketSupplyQueryAuditRepository()
    grant = _grant(authorization_request)
    request = MarketSupplyAggregateGateRequest(
        audit_owner_organization_id=authorization_request.owner_organization_id,
        authorization_request=authorization_request,
        query_policy_id=authorization_request.policy_id,
        query_fingerprint=fingerprint,
        recorded_at=NOW,
        grant=grant,
        population_snapshot=snapshot,
        privacy_input=_privacy_input(fingerprint),
        aggregate_payload={"ready_now": 42},
        audit_record_context=_audit_context(
            snapshot,
            semantic_request_digest=identity.semantic_digest(),
        ),
    )
    service = MarketSupplyIdempotentAggregateGateWorkflow(
        workflow=MarketSupplyAggregateGateWorkflow(
            audit_repository=repository,
            grant_reader=StaticAuthorizationGrantReader(grant),
        ),
        idempotency_gate=MarketSupplyIdempotencyGate(
            IdempotencyService(InMemoryMarketSupplyIdempotencyStore()),
        ),
    )

    first = service.execute(
        identity=identity,
        principal_reference=_principal(authorization_request.beneficiary_organization_id),
        requested_at=NOW,
        request=request,
    )
    second = service.execute(
        identity=identity,
        principal_reference=_principal(authorization_request.beneficiary_organization_id),
        requested_at=NOW,
        request=request,
    )

    assert first.replayed is False
    assert second.replayed is True
    assert second.result_canonical_bytes == first.result_canonical_bytes
    assert (
        len(
            repository.find_related(
                requester_organization_id=authorization_request.beneficiary_organization_id,
                beneficiary_organization_id=authorization_request.beneficiary_organization_id,
                access_purpose=authorization_request.access_purpose,
                policy_context_digest=snapshot.criteria.policy_context_digest(),
            ),
        )
        == 1
    )


def test_idempotent_workflow_does_not_replay_released_payload_after_revocation() -> None:
    authorization_request = _authorization_request()
    snapshot = _population_snapshot(authorization_request)
    fingerprint = _fingerprint(
        authorization_request,
        policy_context_digest=snapshot.criteria.policy_context_digest(),
    )
    identity = _request_identity(
        authorization_request,
        snapshot,
        idempotency_key="market-supply-revoked-replay-key",
    )
    repository = InMemoryMarketSupplyQueryAuditRepository()
    grant = _grant(authorization_request)
    grant_reader = StaticAuthorizationGrantReader(grant)
    service = MarketSupplyIdempotentAggregateGateWorkflow(
        workflow=MarketSupplyAggregateGateWorkflow(
            audit_repository=repository,
            grant_reader=grant_reader,
        ),
        idempotency_gate=MarketSupplyIdempotencyGate(
            IdempotencyService(InMemoryMarketSupplyIdempotencyStore()),
        ),
    )
    first_request = MarketSupplyAggregateGateRequest(
        audit_owner_organization_id=authorization_request.owner_organization_id,
        authorization_request=authorization_request,
        query_policy_id=authorization_request.policy_id,
        query_fingerprint=fingerprint,
        recorded_at=NOW,
        grant=grant,
        population_snapshot=snapshot,
        privacy_input=_privacy_input(fingerprint),
        aggregate_payload={"ready_now": 42},
        audit_record_context=_audit_context(
            snapshot,
            semantic_request_digest=identity.semantic_digest(),
        ),
    )
    revoked_grant = replace(
        grant,
        revoked_at=NOW + timedelta(seconds=30),
    )
    revoked_request = MarketSupplyAggregateGateRequest(
        audit_owner_organization_id=authorization_request.owner_organization_id,
        authorization_request=replace(
            authorization_request,
            requested_at=NOW + timedelta(minutes=1),
        ),
        query_policy_id=authorization_request.policy_id,
        query_fingerprint=replace(fingerprint, requested_at=NOW + timedelta(minutes=1)),
        recorded_at=NOW + timedelta(minutes=1),
        grant=grant,
        population_snapshot=snapshot,
        privacy_input=_privacy_input(
            replace(fingerprint, requested_at=NOW + timedelta(minutes=1)),
        ),
        aggregate_payload={"ready_now": 42},
        audit_record_context=_audit_context(
            snapshot,
            semantic_request_digest=identity.semantic_digest(),
        ),
    )

    first = service.execute(
        identity=identity,
        principal_reference=_principal(authorization_request.beneficiary_organization_id),
        requested_at=NOW,
        request=first_request,
    )
    grant_reader.grant = revoked_grant
    second = service.execute(
        identity=identity,
        principal_reference=_principal(authorization_request.beneficiary_organization_id),
        requested_at=NOW + timedelta(minutes=1),
        request=revoked_request,
    )

    records = repository.find_related(
        requester_organization_id=authorization_request.beneficiary_organization_id,
        beneficiary_organization_id=authorization_request.beneficiary_organization_id,
        access_purpose=authorization_request.access_purpose,
        policy_context_digest=snapshot.criteria.policy_context_digest(),
    )
    assert first.replayed is False
    assert second.replayed is False
    assert second.result_canonical_bytes != first.result_canonical_bytes
    assert b"NOT_RELEASED" in second.result_canonical_bytes
    assert len(records) == 2
    assert records[-1].outcome is MarketSupplyAuditOutcome.GRANT_REVOKED
    assert records[-1].revocation_state is MarketSupplyRevocationState.REVOKED_OBSERVED
    assert records[-1].result_digest is None


def test_idempotent_workflow_conflict_blocks_new_audit_append() -> None:
    authorization_request = _authorization_request()
    snapshot = _population_snapshot(authorization_request)
    fingerprint = _fingerprint(
        authorization_request,
        policy_context_digest=snapshot.criteria.policy_context_digest(),
    )
    original_identity = _request_identity(
        authorization_request,
        snapshot,
        idempotency_key="market-supply-conflict-key",
    )
    divergent_identity = MarketSupplyRequestIdentity(
        buyer_organization_id=authorization_request.beneficiary_organization_id,
        purpose=authorization_request.access_purpose,
        policy_id=authorization_request.policy_id,
        policy_version=snapshot.criteria.policy_version,
        demand_context_digest="demand:sha256:changed",
        candidate_criteria_digest=snapshot.criteria_digest,
        reference_time=NOW,
        knowledge_cutoff=NOW,
        idempotency_key=original_identity.idempotency_key,
    )
    repository = InMemoryMarketSupplyQueryAuditRepository()
    service = MarketSupplyIdempotentAggregateGateWorkflow(
        workflow=MarketSupplyAggregateGateWorkflow(
            audit_repository=repository,
            grant_reader=StaticAuthorizationGrantReader(_grant(authorization_request)),
        ),
        idempotency_gate=MarketSupplyIdempotencyGate(
            IdempotencyService(InMemoryMarketSupplyIdempotencyStore()),
        ),
    )

    service.execute(
        identity=original_identity,
        principal_reference=_principal(authorization_request.beneficiary_organization_id),
        requested_at=NOW,
        request=MarketSupplyAggregateGateRequest(
            audit_owner_organization_id=authorization_request.owner_organization_id,
            authorization_request=authorization_request,
            query_policy_id=authorization_request.policy_id,
            query_fingerprint=fingerprint,
            recorded_at=NOW,
            grant=_grant(authorization_request),
            population_snapshot=snapshot,
            privacy_input=_privacy_input(fingerprint),
            aggregate_payload={"ready_now": 42},
            audit_record_context=_audit_context(
                snapshot,
                semantic_request_digest=original_identity.semantic_digest(),
            ),
        ),
    )

    with pytest.raises(IdempotencyConflict, match="INTENCAO_DIVERGENTE"):
        service.execute(
            identity=divergent_identity,
            principal_reference=_principal(authorization_request.beneficiary_organization_id),
            requested_at=NOW,
            request=MarketSupplyAggregateGateRequest(
                audit_owner_organization_id=authorization_request.owner_organization_id,
                authorization_request=authorization_request,
                query_policy_id=authorization_request.policy_id,
                query_fingerprint=fingerprint,
                recorded_at=NOW,
                grant=_grant(authorization_request),
                population_snapshot=snapshot,
                privacy_input=_privacy_input(fingerprint),
                aggregate_payload={"ready_now": 41},
                audit_record_context=_audit_context(
                    snapshot,
                    semantic_request_digest=divergent_identity.semantic_digest(),
                ),
            ),
        )

    assert (
        len(
            repository.find_related(
                requester_organization_id=authorization_request.beneficiary_organization_id,
                beneficiary_organization_id=authorization_request.beneficiary_organization_id,
                access_purpose=authorization_request.access_purpose,
                policy_context_digest=snapshot.criteria.policy_context_digest(),
            ),
        )
        == 1
    )


def test_workflow_rechecks_revocation_before_public_release() -> None:
    authorization_request = _authorization_request()
    snapshot = _population_snapshot(authorization_request)
    fingerprint = _fingerprint(
        authorization_request,
        policy_context_digest=snapshot.criteria.policy_context_digest(),
    )
    repository = InMemoryMarketSupplyQueryAuditRepository()
    audit_context = _audit_context(snapshot)
    stale_active_grant = _grant(authorization_request)
    fresh_revoked_grant = replace(
        stale_active_grant,
        revoked_at=NOW + timedelta(seconds=30),
    )

    result = MarketSupplyAggregateGateWorkflow(
        audit_repository=repository,
        grant_reader=StaticAuthorizationGrantReader(fresh_revoked_grant),
    ).assess_aggregate_access(
        MarketSupplyAggregateGateRequest(
            audit_owner_organization_id=authorization_request.owner_organization_id,
            authorization_request=authorization_request,
            query_policy_id=authorization_request.policy_id,
            query_fingerprint=fingerprint,
            recorded_at=NOW + timedelta(minutes=1),
            grant=stale_active_grant,
            population_snapshot=snapshot,
            privacy_input=_privacy_input(fingerprint),
            aggregate_payload={"ready_now": 42},
            audit_record_context=audit_context,
        ),
    )

    assert result.audit_envelope.outcome is MarketSupplyAuditOutcome.GRANT_REVOKED
    assert result.public_response.status is MarketSupplyPublicResponseStatus.NOT_RELEASED
    assert result.public_response.aggregate is None
    assert result.audit_record is not None
    assert result.audit_record.revocation_state is MarketSupplyRevocationState.REVOKED_OBSERVED
    assert result.audit_record.result_digest is None
    assert repository.get(audit_context.audit_id) == result.audit_record


def test_workflow_uses_audit_history_for_differencing_before_release() -> None:
    authorization_request = _authorization_request()
    snapshot = _population_snapshot(authorization_request)
    current_fingerprint = _fingerprint(
        authorization_request,
        policy_context_digest=snapshot.criteria.policy_context_digest(),
        filter_fingerprint="region=macro-a;breed=nelore",
        result_subject_count=snapshot.included_count,
    )
    previous_fingerprint = _fingerprint(
        authorization_request,
        policy_context_digest=snapshot.criteria.policy_context_digest(),
        filter_fingerprint="region=macro-a",
        result_subject_count=snapshot.included_count + 1,
    )
    repository = InMemoryMarketSupplyQueryAuditRepository()
    repository.append(
        _previous_audit_record(
            authorization_request=authorization_request,
            fingerprint=previous_fingerprint,
            snapshot=snapshot,
        ),
    )

    result = MarketSupplyAggregateGateWorkflow(
        audit_repository=repository,
        grant_reader=StaticAuthorizationGrantReader(_grant(authorization_request)),
    ).assess_aggregate_access(
        MarketSupplyAggregateGateRequest(
            audit_owner_organization_id=authorization_request.owner_organization_id,
            authorization_request=authorization_request,
            query_policy_id=authorization_request.policy_id,
            query_fingerprint=current_fingerprint,
            recorded_at=NOW,
            grant=_grant(authorization_request),
            population_snapshot=snapshot,
            privacy_input=_privacy_input(current_fingerprint),
            aggregate_payload={"ready_now": 42},
            audit_record_context=_audit_context(snapshot),
        ),
    )

    assert result.audit_envelope.outcome is MarketSupplyAuditOutcome.SUPPRESSED_BY_PRIVACY
    assert result.public_response.status is MarketSupplyPublicResponseStatus.NOT_RELEASED
    assert result.aggregate_result is None
    assert result.audit_record is not None
    assert result.audit_record.result_digest is None


def test_workflow_relates_different_real_population_snapshots_for_differencing() -> None:
    authorization_request = _authorization_request()
    excluded_subject = TypedId.new("animal")
    subjects = tuple(
        CandidatePopulationSubject(
            subject_id=excluded_subject if index == 0 else TypedId.new("animal"),
            organization_id=authorization_request.owner_organization_id,
            known_at=NOW,
        )
        for index in range(42)
    )
    base_criteria = CandidatePopulationCriteria(
        organization_id=authorization_request.owner_organization_id,
        purpose=authorization_request.access_purpose,
        policy_id=authorization_request.policy_id,
        policy_version=1,
        reference_time=NOW,
        knowledge_cutoff=NOW,
    )
    narrowed_criteria = replace(
        base_criteria,
        excluded_subject_ids=(excluded_subject,),
    )
    resolver = CandidatePopulationResolver()
    previous_snapshot = resolver.resolve(
        criteria=base_criteria,
        subjects=subjects,
        resolved_at=NOW - timedelta(minutes=10),
    )
    current_snapshot = resolver.resolve(
        criteria=narrowed_criteria,
        subjects=subjects,
        resolved_at=NOW,
    )
    policy_context_digest = base_criteria.policy_context_digest()
    previous_fingerprint = _fingerprint(
        authorization_request,
        policy_context_digest=policy_context_digest,
        filter_fingerprint="region=ms",
        result_subject_count=previous_snapshot.included_count,
    )
    current_fingerprint = _fingerprint(
        authorization_request,
        policy_context_digest=policy_context_digest,
        filter_fingerprint="region=ms;exclude=one-subject",
        result_subject_count=current_snapshot.included_count,
    )
    repository = InMemoryMarketSupplyQueryAuditRepository()
    repository.append(
        _previous_audit_record(
            authorization_request=authorization_request,
            fingerprint=previous_fingerprint,
            snapshot=previous_snapshot,
        ),
    )

    result = MarketSupplyAggregateGateWorkflow(
        audit_repository=repository,
        grant_reader=StaticAuthorizationGrantReader(_grant(authorization_request)),
    ).assess_aggregate_access(
        MarketSupplyAggregateGateRequest(
            audit_owner_organization_id=authorization_request.owner_organization_id,
            authorization_request=authorization_request,
            query_policy_id=authorization_request.policy_id,
            query_fingerprint=current_fingerprint,
            recorded_at=NOW,
            grant=_grant(authorization_request),
            population_snapshot=current_snapshot,
            privacy_input=_privacy_input(
                current_fingerprint,
                subject_count=current_snapshot.included_count,
            ),
            aggregate_payload={"ready_now": current_snapshot.included_count},
            audit_record_context=_audit_context(current_snapshot),
        ),
    )

    assert previous_snapshot.snapshot_digest != current_snapshot.snapshot_digest
    assert previous_snapshot.criteria.policy_context_digest() == (
        current_snapshot.criteria.policy_context_digest()
    )
    assert result.audit_envelope.outcome is MarketSupplyAuditOutcome.SUPPRESSED_BY_PRIVACY
    assert result.audit_record is not None
    assert result.audit_record.decision_reason_codes == ("DIFFERENCING_RISK",)
    assert result.public_response.status is MarketSupplyPublicResponseStatus.NOT_RELEASED
    assert result.aggregate_result is None


def test_workflow_requires_audit_repository_when_audit_record_context_is_supplied() -> None:
    authorization_request = _authorization_request()
    snapshot = _population_snapshot(authorization_request)
    fingerprint = _fingerprint(
        authorization_request,
        policy_context_digest=snapshot.criteria.policy_context_digest(),
    )

    with pytest.raises(ValueError, match="audit_repository"):
        MarketSupplyAggregateGateWorkflow().assess_aggregate_access(
            MarketSupplyAggregateGateRequest(
                audit_owner_organization_id=authorization_request.owner_organization_id,
                authorization_request=authorization_request,
                query_policy_id=authorization_request.policy_id,
                query_fingerprint=fingerprint,
                recorded_at=NOW,
                grant=_grant(authorization_request),
                population_snapshot=snapshot,
                privacy_input=_privacy_input(fingerprint),
                aggregate_payload={"ready_now": 42},
                audit_record_context=_audit_context(snapshot),
            ),
        )


def test_audit_context_requires_population_snapshot_linkage() -> None:
    authorization_request = _authorization_request()
    fingerprint = _fingerprint(authorization_request)
    snapshot = _population_snapshot(authorization_request)

    with pytest.raises(ValueError, match="policy_context_digest"):
        MarketSupplyAggregateGateRequest(
            audit_owner_organization_id=authorization_request.owner_organization_id,
            authorization_request=authorization_request,
            query_policy_id=authorization_request.policy_id,
            query_fingerprint=fingerprint,
            recorded_at=NOW,
            grant=_grant(authorization_request),
            population_snapshot=snapshot,
            privacy_input=_privacy_input(fingerprint),
            aggregate_payload={"ready_now": 42},
            audit_record_context=_audit_context(snapshot),
        )


def test_audit_context_validates_internal_population_digest_when_supplied() -> None:
    authorization_request = _authorization_request()
    snapshot = _population_snapshot(authorization_request)
    fingerprint = _fingerprint(
        authorization_request,
        policy_context_digest=snapshot.criteria.policy_context_digest(),
    )
    audit_context = MarketSupplyAuditRecordContext(
        audit_id=TypedId.new("market_supply_query_audit"),
        policy_version=1,
        privacy_profile_id="market-supply-aggregate-test",
        authorization_context_digest="authorization:sha256:workflow",
        candidate_population_digest=snapshot.snapshot_digest,
        reference_time=NOW,
        knowledge_cutoff=NOW,
        requested_at=NOW,
        revocation_state=MarketSupplyRevocationState.NOT_REVOKED,
        correlation_id=TypedId.new("correlation"),
        idempotency_reference="idempotency-key:workflow",
        semantic_request_digest="request:sha256:workflow",
        population_digest="population:sha256:different",
    )

    with pytest.raises(ValueError, match="population digest interno"):
        MarketSupplyAggregateGateRequest(
            audit_owner_organization_id=authorization_request.owner_organization_id,
            authorization_request=authorization_request,
            query_policy_id=authorization_request.policy_id,
            query_fingerprint=fingerprint,
            recorded_at=NOW,
            grant=_grant(authorization_request),
            population_snapshot=snapshot,
            privacy_input=_privacy_input(fingerprint),
            aggregate_payload={"ready_now": 42},
            audit_record_context=audit_context,
        )


def test_audit_context_reference_time_must_match_population_snapshot() -> None:
    authorization_request = _authorization_request()
    snapshot = _population_snapshot(authorization_request)
    fingerprint = _fingerprint(
        authorization_request,
        policy_context_digest=snapshot.criteria.policy_context_digest(),
    )
    audit_context = replace(
        _audit_context(snapshot),
        reference_time=NOW - timedelta(days=1),
    )

    with pytest.raises(ValueError, match="reference_time"):
        MarketSupplyAggregateGateRequest(
            audit_owner_organization_id=authorization_request.owner_organization_id,
            authorization_request=authorization_request,
            query_policy_id=authorization_request.policy_id,
            query_fingerprint=fingerprint,
            recorded_at=NOW,
            grant=_grant(authorization_request),
            population_snapshot=snapshot,
            privacy_input=_privacy_input(fingerprint),
            aggregate_payload={"ready_now": 42},
            audit_record_context=audit_context,
        )


def test_audit_context_knowledge_cutoff_must_match_population_snapshot() -> None:
    authorization_request = _authorization_request()
    snapshot = _population_snapshot(authorization_request)
    fingerprint = _fingerprint(
        authorization_request,
        policy_context_digest=snapshot.criteria.policy_context_digest(),
    )
    audit_context = replace(
        _audit_context(snapshot),
        knowledge_cutoff=NOW - timedelta(hours=1),
    )

    with pytest.raises(ValueError, match="knowledge_cutoff"):
        MarketSupplyAggregateGateRequest(
            audit_owner_organization_id=authorization_request.owner_organization_id,
            authorization_request=authorization_request,
            query_policy_id=authorization_request.policy_id,
            query_fingerprint=fingerprint,
            recorded_at=NOW,
            grant=_grant(authorization_request),
            population_snapshot=snapshot,
            privacy_input=_privacy_input(fingerprint),
            aggregate_payload={"ready_now": 42},
            audit_record_context=audit_context,
        )


def test_pre_population_audit_context_rejects_population_digest() -> None:
    authorization_request = _authorization_request()
    fingerprint = _fingerprint(authorization_request)
    audit_context = MarketSupplyAuditRecordContext(
        audit_id=TypedId.new("market_supply_query_audit"),
        policy_version=1,
        privacy_profile_id="market-supply-aggregate-test",
        authorization_context_digest="authorization:sha256:workflow",
        candidate_population_digest=fingerprint.policy_context_digest,
        reference_time=NOW,
        knowledge_cutoff=NOW,
        requested_at=NOW,
        revocation_state=MarketSupplyRevocationState.NOT_REVOKED,
        correlation_id=TypedId.new("correlation"),
        idempotency_reference="idempotency-key:workflow",
        semantic_request_digest="request:sha256:workflow",
        population_digest="population:sha256:unresolved",
    )

    with pytest.raises(ValueError, match="sem population_snapshot"):
        MarketSupplyAggregateGateRequest(
            audit_owner_organization_id=authorization_request.owner_organization_id,
            authorization_request=authorization_request,
            query_policy_id=authorization_request.policy_id,
            query_fingerprint=fingerprint,
            recorded_at=NOW,
            grant=None,
            privacy_input=None,
            aggregate_payload={"ready_now": 42},
            audit_record_context=audit_context,
        )
