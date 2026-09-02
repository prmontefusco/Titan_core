from datetime import datetime, timedelta
from uuid import UUID, uuid4

import pytest

from packages.core_application import IdempotencyService
from packages.core_application.idempotency import IdempotencyRequest, StoredIdempotencyResult
from packages.core_domain import CanonicalPayload
from packages.core_domain.decision import Decision, DecisionResult
from packages.core_domain.evaluation import Evaluation
from packages.core_domain.policy_sharing import AuthorizationGrant
from packages.livestock_application.market_readiness import (
    MarketReadinessInput,
    MarketReadinessService,
    MarketReadinessStatus,
)
from packages.livestock_application.market_supply import (
    PRODUCER_SIDE_ANALYSIS_BOUNDARY,
    MarketSupplyAggregateAssessmentCommand,
    MarketSupplyAggregateAssessmentOrchestrator,
    MarketSupplyAggregatePayloadBuilder,
    MarketSupplyReadinessCompositionService,
    ProducerMarketSupplyAnalysisService,
    ProducerMarketSupplyQuestion,
)
from packages.livestock_application.market_supply_audit import (
    InMemoryMarketSupplyQueryAuditRepository,
)
from packages.livestock_application.market_supply_authorization import (
    MARKET_SUPPLY_AGGREGATE_ASSESSMENT,
    MARKET_SUPPLY_AGGREGATE_FIELD_SCOPE,
)
from packages.livestock_application.market_supply_population import (
    AuthorizedCandidatePopulationCompositionService,
    AuthorizedCandidatePopulationResult,
    CandidatePopulationCriteria,
    CandidatePopulationResolver,
    CandidatePopulationSubject,
)
from packages.livestock_application.market_supply_privacy import (
    AggregationGeographicPrecision,
    AggregationPrivacyPolicy,
    AggregationPrivacyProfile,
)
from packages.livestock_application.market_supply_request import (
    CommercialDemandContext,
    MarketSupplyIdempotencyGate,
)
from packages.livestock_application.market_supply_response import (
    MarketSupplyPublicResponseMapper,
    MarketSupplyPublicResponseStatus,
)
from packages.livestock_application.market_supply_workflow import (
    MarketSupplyAggregateGateWorkflow,
    MarketSupplyIdempotentAggregateGateWorkflow,
)
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference
from tests.livestock_application.test_market_readiness import _artifacts, _context
from tests.livestock_application.test_market_supply_response import _envelope


def test_producer_market_supply_aggregates_readiness_without_new_decision() -> None:
    ready, ready_evaluation, policy = _artifacts()
    not_ready, not_ready_evaluation, _ = _artifacts(
        organization_id=policy.organization_id,
        policy_id=policy.policy_id,
        result=DecisionResult.REJEITADA,
    )
    conditioned, conditioned_evaluation, _ = _artifacts(
        organization_id=policy.organization_id,
        policy_id=policy.policy_id,
        result=DecisionResult.APROVADA_COM_RESTRICOES,
    )
    report = MarketReadinessService().build_report(
        context=_context(policy),
        inputs=(
            MarketReadinessInput(ready.subject_id, ready, ready_evaluation),
            MarketReadinessInput(not_ready.subject_id, not_ready, not_ready_evaluation),
            MarketReadinessInput(conditioned.subject_id, conditioned, conditioned_evaluation),
        ),
    )

    analysis = ProducerMarketSupplyAnalysisService().build_from_readiness(
        report=report,
        question=ProducerMarketSupplyQuestion(requested_quantity=2),
    )

    assert analysis.analysis_boundary == PRODUCER_SIDE_ANALYSIS_BOUNDARY
    assert analysis.population_count == 3
    assert analysis.readiness_counts[MarketReadinessStatus.READY.value] == 1
    assert analysis.readiness_counts[MarketReadinessStatus.CONDITIONED.value] == 1
    assert analysis.readiness_counts[MarketReadinessStatus.NOT_READY.value] == 1
    assert analysis.current_capacity == 1
    assert analysis.estimated_shortage_now == 1
    assert ready.decision_id in {entry.decision_id for entry in report.entries}


def test_producer_market_supply_keeps_temporal_and_policy_context() -> None:
    decision, evaluation, policy = _artifacts()
    report = MarketReadinessService().build_report(
        context=_context(policy),
        inputs=(MarketReadinessInput(decision.subject_id, decision, evaluation),),
    )

    analysis = ProducerMarketSupplyAnalysisService().build_from_readiness(report=report)

    assert analysis.organization_id == str(policy.organization_id.value)
    assert analysis.policy_id == str(policy.policy_id.value)
    assert analysis.policy_version == policy.version
    assert analysis.reference_time == report.context.reference_time.isoformat()
    assert analysis.knowledge_cutoff == report.context.knowledge_cutoff.isoformat()


def test_producer_market_supply_exposes_only_aggregate_gap_counts() -> None:
    not_ready, not_ready_evaluation, policy = _artifacts(result=DecisionResult.REJEITADA)
    indeterminate, indeterminate_evaluation, _ = _artifacts(
        organization_id=policy.organization_id,
        policy_id=policy.policy_id,
        result=DecisionResult.INDETERMINADA,
    )
    report = MarketReadinessService().build_report(
        context=_context(policy),
        inputs=(
            MarketReadinessInput(not_ready.subject_id, not_ready, not_ready_evaluation),
            MarketReadinessInput(
                indeterminate.subject_id,
                indeterminate,
                indeterminate_evaluation,
            ),
        ),
    )

    analysis = ProducerMarketSupplyAnalysisService().build_from_readiness(report=report)

    assert analysis.gap_summary
    assert all(isinstance(gap.code, str) for gap in analysis.gap_summary)
    assert all(gap.count >= 1 for gap in analysis.gap_summary)
    assert all(not hasattr(gap, "example_subject_ids") for gap in analysis.gap_summary)


def test_producer_market_supply_marks_unknown_and_reassessment_limitations() -> None:
    decision, evaluation, policy = _artifacts(purpose="another-purpose")
    report = MarketReadinessService().build_report(
        context=_context(policy),
        inputs=(
            MarketReadinessInput(decision.subject_id, decision, evaluation),
            MarketReadinessInput(_artifacts(organization_id=policy.organization_id)[0].subject_id),
        ),
    )

    analysis = ProducerMarketSupplyAnalysisService().build_from_readiness(report=report)

    assert "derived from MarketReadiness; not a Decision" in analysis.limitations
    assert "no buyer visibility" in analysis.limitations
    assert "population contains not evaluated subjects" in analysis.limitations
    assert "population contains subjects requiring reassessment" in analysis.limitations


def test_producer_market_supply_rejects_invalid_quantity() -> None:
    with pytest.raises(ValueError, match="requested_quantity"):
        ProducerMarketSupplyQuestion(requested_quantity=0)


def test_market_supply_aggregate_payload_sums_canonical_readiness_reports() -> None:
    ready, ready_evaluation, policy = _artifacts()
    not_ready, not_ready_evaluation, _ = _artifacts(
        organization_id=policy.organization_id,
        policy_id=policy.policy_id,
        result=DecisionResult.REJEITADA,
    )
    report_a = MarketReadinessService().build_report(
        context=_context(policy),
        inputs=(MarketReadinessInput(ready.subject_id, ready, ready_evaluation),),
    )
    report_b = MarketReadinessService().build_report(
        context=_context(policy),
        inputs=(MarketReadinessInput(not_ready.subject_id, not_ready, not_ready_evaluation),),
    )

    payload = MarketSupplyAggregatePayloadBuilder().build_from_readiness_reports(
        reports=(report_a, report_b),
        requested_quantity=3,
    )

    assert payload["population_count"] == 2
    assert payload["ready_now"] == 1
    assert payload["not_ready"] == 1
    assert payload["current_capacity"] == 1
    assert payload["requested_quantity"] == 3
    assert payload["estimated_shortage_now"] == 2
    assert payload["readiness_counts"][MarketReadinessStatus.READY.value] == 1
    assert payload["readiness_counts"][MarketReadinessStatus.NOT_READY.value] == 1
    assert "derived from MarketReadiness; not a Decision" in payload["limitations"]
    response = MarketSupplyPublicResponseMapper().map_aggregate(
        envelope=_envelope(),
        aggregate_payload=payload,
    )
    assert response.status is MarketSupplyPublicResponseStatus.RELEASED


def test_market_supply_aggregate_payload_rejects_mixed_temporal_or_policy_context() -> None:
    decision, evaluation, policy = _artifacts()
    other_decision, other_evaluation, other_policy = _artifacts()
    report = MarketReadinessService().build_report(
        context=_context(policy),
        inputs=(MarketReadinessInput(decision.subject_id, decision, evaluation),),
    )
    other_report = MarketReadinessService().build_report(
        context=_context(other_policy),
        inputs=(
            MarketReadinessInput(
                other_decision.subject_id,
                other_decision,
                other_evaluation,
            ),
        ),
    )

    with pytest.raises(ValueError, match="contexto homogeneo"):
        MarketSupplyAggregatePayloadBuilder().build_from_readiness_reports(
            reports=(report, other_report),
            requested_quantity=1,
        )


def test_market_supply_aggregate_payload_keeps_gaps_aggregate_only() -> None:
    not_ready, not_ready_evaluation, policy = _artifacts(result=DecisionResult.REJEITADA)
    report = MarketReadinessService().build_report(
        context=_context(policy),
        inputs=(MarketReadinessInput(not_ready.subject_id, not_ready, not_ready_evaluation),),
    )

    payload = MarketSupplyAggregatePayloadBuilder().build_from_readiness_reports(
        reports=(report,),
        requested_quantity=None,
    )

    assert payload["gap_summary"]
    assert all(set(gap) == {"code", "count"} for gap in payload["gap_summary"])
    assert {"code": "GENERAL_GAP", "count": 1} in payload["gap_summary"]
    assert "some gap codes use a public general category" in payload["limitations"]
    assert str(not_ready.subject_id.value) not in repr(payload["gap_summary"])


class EmptyDecisionReader:
    def list_by_subject(
        self,
        organization_id: OrganizationId,
        subject_id: TypedId,
    ) -> list[Decision]:
        return []


class EmptyEvaluationReader:
    def get_by_id(self, evaluation_id: TypedId) -> Evaluation | None:
        return None


def test_market_supply_readiness_composition_builds_owner_scoped_reports_from_snapshots() -> None:
    _, _, policy = _artifacts()
    criteria = CandidatePopulationCriteria(
        organization_id=policy.organization_id,
        purpose="MARKET_SUPPLY_AGGREGATE_ASSESSMENT",
        policy_id=policy.policy_id,
        policy_version=policy.version,
        reference_time=_context(policy).reference_time,
        knowledge_cutoff=_context(policy).knowledge_cutoff,
    )
    subject = CandidatePopulationSubject(
        subject_id=_artifacts(organization_id=policy.organization_id)[0].subject_id,
        organization_id=policy.organization_id,
        known_at=_context(policy).knowledge_cutoff,
    )
    snapshot = CandidatePopulationResolver().resolve(
        criteria=criteria,
        subjects=(subject,),
        resolved_at=_context(policy).knowledge_cutoff,
    )

    reports = MarketSupplyReadinessCompositionService(
        decision_reader=EmptyDecisionReader(),
        evaluation_reader=EmptyEvaluationReader(),
        readiness_service=MarketReadinessService(),
    ).build_reports(
        population_result=AuthorizedCandidatePopulationResult(
            snapshots=(snapshot,),
            rejected_contributions=(),
        ),
    )

    assert len(reports) == 1
    assert reports[0].context.organization_id == policy.organization_id
    assert reports[0].context.policy_id == policy.policy_id
    assert reports[0].counts[MarketReadinessStatus.NOT_EVALUATED] == 1


class RecordingGrantReader:
    def __init__(self, grants: list[AuthorizationGrant]) -> None:
        self.grants = grants

    def list_active_by_policy_beneficiary_purpose_scope_at(
        self,
        *,
        policy_id: TypedId,
        beneficiary_organization_id: OrganizationId,
        access_purpose: str,
        field_scope_profile: str,
        requested_at: datetime,
    ) -> list[AuthorizationGrant]:
        return [
            grant
            for grant in self.grants
            if grant.policy_id == policy_id
            and grant.beneficiary_organization_id == beneficiary_organization_id
            and grant.access_purpose == access_purpose
            and grant.field_scope_profile == field_scope_profile
            and grant.valid_from <= requested_at < grant.valid_until
        ]


class RecordingSubjectReader:
    def __init__(
        self,
        subjects_by_owner: dict[OrganizationId, tuple[CandidatePopulationSubject, ...]],
    ) -> None:
        self.subjects_by_owner = subjects_by_owner

    def list_subjects(
        self,
        *,
        criteria: CandidatePopulationCriteria,
    ) -> tuple[CandidatePopulationSubject, ...]:
        return self.subjects_by_owner.get(criteria.organization_id, ())


class StaticGrantReader:
    def __init__(self, grant: AuthorizationGrant) -> None:
        self.grant = grant

    def get_by_id(self, grant_id: UUID) -> AuthorizationGrant | None:
        return self.grant if grant_id == self.grant.grant_id else None


class InMemoryIdempotencyStore:
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


def _grant(
    *,
    criteria: CandidatePopulationCriteria,
    buyer_organization_id: OrganizationId,
) -> AuthorizationGrant:
    return AuthorizationGrant(
        grant_id=uuid4(),
        owner_organization_id=criteria.organization_id,
        beneficiary_organization_id=buyer_organization_id,
        policy_id=criteria.policy_id,
        policy_version_id=TypedId.new("policy_version"),
        access_purpose=MARKET_SUPPLY_AGGREGATE_ASSESSMENT,
        field_scope_profile=MARKET_SUPPLY_AGGREGATE_FIELD_SCOPE,
        valid_from=criteria.reference_time - timedelta(days=1),
        valid_until=criteria.reference_time + timedelta(days=1),
        status="ATIVO",
        created_at=criteria.reference_time - timedelta(days=2),
        created_by="test",
    )


def _privacy_profile() -> AggregationPrivacyProfile:
    return AggregationPrivacyProfile(
        profile_id="market-supply-aggregate-test",
        policy=AggregationPrivacyPolicy(
            policy_version=1,
            minimum_organizations=1,
            minimum_properties=1,
            minimum_subjects=1,
            max_filter_count_without_review=4,
            repeated_query_window=timedelta(minutes=10),
        ),
    )


def _principal(organization_id: OrganizationId) -> UniversalReference:
    return UniversalReference(
        target_id=TypedId.new("user"),
        organization_id=organization_id,
        contract_version=1,
    )


def test_market_supply_orchestrator_releases_single_owner_after_snapshot_and_audit() -> None:
    buyer = OrganizationId.new()
    _, _, policy = _artifacts()
    owner = policy.organization_id
    base_criteria = CandidatePopulationCriteria(
        organization_id=buyer,
        purpose=MARKET_SUPPLY_AGGREGATE_ASSESSMENT,
        policy_id=policy.policy_id,
        policy_version=policy.version,
        reference_time=_context(policy).reference_time,
        knowledge_cutoff=_context(policy).knowledge_cutoff,
    )
    owner_criteria = CandidatePopulationCriteria(
        organization_id=owner,
        purpose=base_criteria.purpose,
        policy_id=base_criteria.policy_id,
        policy_version=base_criteria.policy_version,
        reference_time=base_criteria.reference_time,
        knowledge_cutoff=base_criteria.knowledge_cutoff,
    )
    subject = CandidatePopulationSubject(
        subject_id=TypedId.new("animal"),
        organization_id=owner,
        property_id=TypedId.new("rural_property"),
        known_at=base_criteria.knowledge_cutoff,
    )
    grant = _grant(criteria=owner_criteria, buyer_organization_id=buyer)
    audit_repository = InMemoryMarketSupplyQueryAuditRepository()
    orchestrator = MarketSupplyAggregateAssessmentOrchestrator(
        population_composer=AuthorizedCandidatePopulationCompositionService(
            grant_reader=RecordingGrantReader([grant]),
            subject_reader=RecordingSubjectReader({owner: (subject,)}),
        ),
        readiness_composer=MarketSupplyReadinessCompositionService(
            decision_reader=EmptyDecisionReader(),
            evaluation_reader=EmptyEvaluationReader(),
            readiness_service=MarketReadinessService(),
        ),
        payload_builder=MarketSupplyAggregatePayloadBuilder(),
        gate_workflow=MarketSupplyAggregateGateWorkflow(
            audit_repository=audit_repository,
            grant_reader=StaticGrantReader(grant),
        ),
    )

    prepared, gate_result = orchestrator.assess_single_owner(
        MarketSupplyAggregateAssessmentCommand(
            buyer_organization_id=buyer,
            base_criteria=base_criteria,
            requested_quantity=2,
            privacy_profile=_privacy_profile(),
            geographic_precision=AggregationGeographicPrecision.REGION,
            filter_count=1,
            requested_at=base_criteria.reference_time,
            audit_id=TypedId.new("market_supply_query_audit"),
            correlation_id=TypedId.new("correlation"),
            idempotency_reference="idem-key-1",
            semantic_request_digest="request:sha256:single-owner",
        )
    )

    assert prepared.population.result.included_count == 1
    assert gate_result.public_response.status is MarketSupplyPublicResponseStatus.RELEASED
    assert gate_result.aggregate_result is not None
    assert gate_result.audit_record is not None
    assert gate_result.audit_record.audit_owner_organization_id == owner
    assert gate_result.audit_record.candidate_population_digest == (
        prepared.population.result.snapshots[0].snapshot_digest
    )
    assert gate_result.aggregate_result.aggregate_payload["not_evaluated"] == 1


def test_market_supply_orchestrator_replays_idempotent_single_owner_without_new_audit() -> None:
    buyer = OrganizationId.new()
    _, _, policy = _artifacts()
    owner = policy.organization_id
    context = _context(policy)
    base_criteria = CandidatePopulationCriteria(
        organization_id=buyer,
        purpose=MARKET_SUPPLY_AGGREGATE_ASSESSMENT,
        policy_id=policy.policy_id,
        policy_version=policy.version,
        reference_time=context.reference_time,
        knowledge_cutoff=context.knowledge_cutoff,
    )
    owner_criteria = CandidatePopulationCriteria(
        organization_id=owner,
        purpose=base_criteria.purpose,
        policy_id=base_criteria.policy_id,
        policy_version=base_criteria.policy_version,
        reference_time=base_criteria.reference_time,
        knowledge_cutoff=base_criteria.knowledge_cutoff,
    )
    grant = _grant(criteria=owner_criteria, buyer_organization_id=buyer)
    audit_repository = InMemoryMarketSupplyQueryAuditRepository()
    gate_workflow = MarketSupplyAggregateGateWorkflow(
        audit_repository=audit_repository,
        grant_reader=StaticGrantReader(grant),
    )
    orchestrator = MarketSupplyAggregateAssessmentOrchestrator(
        population_composer=AuthorizedCandidatePopulationCompositionService(
            grant_reader=RecordingGrantReader([grant]),
            subject_reader=RecordingSubjectReader(
                {
                    owner: (
                        CandidatePopulationSubject(
                            subject_id=TypedId.new("animal"),
                            organization_id=owner,
                            property_id=TypedId.new("rural_property"),
                            known_at=base_criteria.knowledge_cutoff,
                        ),
                    )
                }
            ),
        ),
        readiness_composer=MarketSupplyReadinessCompositionService(
            decision_reader=EmptyDecisionReader(),
            evaluation_reader=EmptyEvaluationReader(),
            readiness_service=MarketReadinessService(),
        ),
        payload_builder=MarketSupplyAggregatePayloadBuilder(),
        gate_workflow=gate_workflow,
        idempotent_gate_workflow=MarketSupplyIdempotentAggregateGateWorkflow(
            workflow=gate_workflow,
            idempotency_gate=MarketSupplyIdempotencyGate(
                IdempotencyService(InMemoryIdempotencyStore())
            ),
        ),
    )
    demand = CommercialDemandContext(
        buyer_organization_id=buyer,
        purpose=base_criteria.purpose,
        policy_id=base_criteria.policy_id,
        policy_version=base_criteria.policy_version,
        requested_quantity=2,
        commercial_window_from=context.reference_time,
        commercial_window_until=context.reference_time + timedelta(days=7),
    )
    identity = demand.to_request_identity(
        candidate_criteria_digest=base_criteria.digest(),
        reference_time=base_criteria.reference_time,
        knowledge_cutoff=base_criteria.knowledge_cutoff,
        idempotency_key="idem-key-replay",
    )
    command = MarketSupplyAggregateAssessmentCommand(
        buyer_organization_id=buyer,
        base_criteria=base_criteria,
        requested_quantity=2,
        privacy_profile=_privacy_profile(),
        geographic_precision=AggregationGeographicPrecision.REGION,
        filter_count=1,
        requested_at=base_criteria.reference_time,
        audit_id=TypedId.new("market_supply_query_audit"),
        correlation_id=TypedId.new("correlation"),
        idempotency_reference=identity.idempotency_key,
        semantic_request_digest=identity.semantic_digest(),
    )

    _, first = orchestrator.execute_idempotent_single_owner(
        command=command,
        identity=identity,
        principal_reference=_principal(buyer),
    )
    _, replay = orchestrator.execute_idempotent_single_owner(
        command=command,
        identity=identity,
        principal_reference=_principal(buyer),
    )

    assert first.replayed is False
    assert replay.replayed is True
    assert replay.result_canonical_bytes == first.result_canonical_bytes
    assert (
        len(
            audit_repository.find_related_query_fingerprints(
                requester_organization_id=buyer,
                beneficiary_organization_id=buyer,
                access_purpose=MARKET_SUPPLY_AGGREGATE_ASSESSMENT,
                policy_context_digest=owner_criteria.policy_context_digest(),
            )
        )
        == 1
    )


def test_market_supply_orchestrator_blocks_multi_owner_release_without_audit_correlation() -> None:
    buyer = OrganizationId.new()
    _, _, policy = _artifacts()
    owner_a = OrganizationId.new()
    owner_b = OrganizationId.new()
    base_criteria = CandidatePopulationCriteria(
        organization_id=buyer,
        purpose=MARKET_SUPPLY_AGGREGATE_ASSESSMENT,
        policy_id=policy.policy_id,
        policy_version=policy.version,
        reference_time=_context(policy).reference_time,
        knowledge_cutoff=_context(policy).knowledge_cutoff,
    )
    criteria_a = CandidatePopulationCriteria(
        organization_id=owner_a,
        purpose=base_criteria.purpose,
        policy_id=base_criteria.policy_id,
        policy_version=base_criteria.policy_version,
        reference_time=base_criteria.reference_time,
        knowledge_cutoff=base_criteria.knowledge_cutoff,
    )
    criteria_b = CandidatePopulationCriteria(
        organization_id=owner_b,
        purpose=base_criteria.purpose,
        policy_id=base_criteria.policy_id,
        policy_version=base_criteria.policy_version,
        reference_time=base_criteria.reference_time,
        knowledge_cutoff=base_criteria.knowledge_cutoff,
    )
    grants = [
        _grant(criteria=criteria_a, buyer_organization_id=buyer),
        _grant(criteria=criteria_b, buyer_organization_id=buyer),
    ]
    orchestrator = MarketSupplyAggregateAssessmentOrchestrator(
        population_composer=AuthorizedCandidatePopulationCompositionService(
            grant_reader=RecordingGrantReader(grants),
            subject_reader=RecordingSubjectReader(
                {
                    owner_a: (
                        CandidatePopulationSubject(
                            subject_id=TypedId.new("animal"),
                            organization_id=owner_a,
                            property_id=TypedId.new("rural_property"),
                            known_at=base_criteria.knowledge_cutoff,
                        ),
                    ),
                    owner_b: (
                        CandidatePopulationSubject(
                            subject_id=TypedId.new("animal"),
                            organization_id=owner_b,
                            property_id=TypedId.new("rural_property"),
                            known_at=base_criteria.knowledge_cutoff,
                        ),
                    ),
                }
            ),
        ),
        readiness_composer=MarketSupplyReadinessCompositionService(
            decision_reader=EmptyDecisionReader(),
            evaluation_reader=EmptyEvaluationReader(),
            readiness_service=MarketReadinessService(),
        ),
        payload_builder=MarketSupplyAggregatePayloadBuilder(),
        gate_workflow=MarketSupplyAggregateGateWorkflow(),
    )

    with pytest.raises(ValueError, match="correlacao auditavel multi-owner"):
        orchestrator.assess_single_owner(
            MarketSupplyAggregateAssessmentCommand(
                buyer_organization_id=buyer,
                base_criteria=base_criteria,
                requested_quantity=None,
                privacy_profile=_privacy_profile(),
                geographic_precision=AggregationGeographicPrecision.REGION,
                filter_count=1,
                requested_at=base_criteria.reference_time,
                audit_id=TypedId.new("market_supply_query_audit"),
                correlation_id=TypedId.new("correlation"),
                idempotency_reference="idem-key-2",
                semantic_request_digest="request:sha256:multi-owner",
            )
        )
