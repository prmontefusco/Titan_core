"""Producer-side Market Supply aggregate analysis (CUT F1).

This module composes existing MarketReadiness outputs. It does not evaluate
Policies, emit Decisions, persist reports, expose buyer visibility, or perform
cross-Organization access.
"""

import hashlib
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from packages.core_application.idempotency import IdempotencyExecution
from packages.core_domain.policy_sharing import AuthorizationGrant
from packages.livestock_application.market_optionality import (
    MarketOptionAssessment,
    MarketOptionState,
)
from packages.livestock_application.market_readiness import (
    MARKET_ELIGIBILITY_RESULT_BOUNDARY,
    MarketReadinessContext,
    MarketReadinessDecisionReaderPort,
    MarketReadinessEvaluationReaderPort,
    MarketReadinessGapSummary,
    MarketReadinessPopulationReader,
    MarketReadinessReport,
    MarketReadinessService,
    MarketReadinessStatus,
)
from packages.livestock_application.market_supply_audit import (
    MarketSupplyRevocationState,
)
from packages.livestock_application.market_supply_authorization import (
    MARKET_SUPPLY_AGGREGATE_ASSESSMENT,
    MARKET_SUPPLY_AGGREGATE_FIELD_SCOPE,
    MarketSupplyAuthorizationRequest,
)
from packages.livestock_application.market_supply_population import (
    AuthorizedCandidatePopulationComposition,
    AuthorizedCandidatePopulationCompositionService,
    AuthorizedCandidatePopulationResult,
    CandidatePopulationCriteria,
)
from packages.livestock_application.market_supply_privacy import (
    AggregationGeographicPrecision,
    AggregationPrivacyInput,
    AggregationPrivacyProfile,
    AggregationQueryFingerprint,
)
from packages.livestock_application.market_supply_request import MarketSupplyRequestIdentity
from packages.livestock_application.market_supply_workflow import (
    MarketSupplyAggregateGateRequest,
    MarketSupplyAggregateGateResult,
    MarketSupplyAggregateGateWorkflow,
    MarketSupplyAuditRecordContext,
    MarketSupplyIdempotentAggregateGateWorkflow,
)
from packages.shared_kernel import (
    CanonicalSerializer,
    OrganizationId,
    TypedId,
    UniversalReference,
    canonicalize_for_hash,
)
from packages.shared_kernel.temporal import require_utc

PRODUCER_SIDE_ANALYSIS_BOUNDARY = "PRODUCER_SIDE_SINGLE_ORGANIZATION_ANALYSIS"
_SERIALIZER = CanonicalSerializer()


@dataclass(frozen=True, slots=True)
class ProducerMarketSupplyQuestion:
    """Optional producer-side quantity question over an already resolved population."""

    requested_quantity: int | None = None

    def __post_init__(self) -> None:
        if self.requested_quantity is not None and self.requested_quantity < 1:
            raise ValueError("requested_quantity deve ser inteiro >= 1 quando informado.")


@dataclass(frozen=True, slots=True)
class ProducerMarketSupplyGap:
    code: str
    count: int


@dataclass(frozen=True, slots=True)
class ProducerMarketSupplyAnalysis:
    organization_id: str
    purpose: str
    policy_id: str
    policy_version: int
    reference_time: str
    knowledge_cutoff: str
    population_count: int
    readiness_counts: dict[str, int]
    current_capacity: int
    requested_quantity: int | None
    estimated_shortage_now: int | None
    gap_summary: tuple[ProducerMarketSupplyGap, ...]
    limitations: tuple[str, ...]
    analysis_boundary: str = PRODUCER_SIDE_ANALYSIS_BOUNDARY
    source_boundary: str = MARKET_ELIGIBILITY_RESULT_BOUNDARY


class ProducerMarketSupplyAnalysisService:
    """Aggregates readiness for the producer's own Organization."""

    def build_from_readiness(
        self,
        *,
        report: MarketReadinessReport,
        question: ProducerMarketSupplyQuestion | None = None,
    ) -> ProducerMarketSupplyAnalysis:
        question = question or ProducerMarketSupplyQuestion()
        readiness_counts = {
            status.value: report.counts.get(status, 0) for status in MarketReadinessStatus
        }
        current_capacity = readiness_counts[MarketReadinessStatus.READY.value]
        estimated_shortage = (
            None
            if question.requested_quantity is None
            else max(question.requested_quantity - current_capacity, 0)
        )
        limitations = _limitations_from_report(report)
        return ProducerMarketSupplyAnalysis(
            organization_id=str(report.context.organization_id.value),
            purpose=report.context.purpose,
            policy_id=str(report.context.policy_id.value),
            policy_version=report.context.policy_version,
            reference_time=report.context.reference_time.isoformat(),
            knowledge_cutoff=report.context.knowledge_cutoff.isoformat(),
            population_count=len(report.entries),
            readiness_counts=readiness_counts,
            current_capacity=current_capacity,
            requested_quantity=question.requested_quantity,
            estimated_shortage_now=estimated_shortage,
            gap_summary=_aggregate_gaps(report.gap_summary),
            limitations=limitations,
        )


def _aggregate_gaps(
    gaps: tuple[MarketReadinessGapSummary, ...],
) -> tuple[ProducerMarketSupplyGap, ...]:
    return tuple(
        ProducerMarketSupplyGap(code=gap.code, count=gap.count)
        for gap in sorted(gaps, key=lambda item: item.code)
    )


def _limitations_from_report(report: MarketReadinessReport) -> tuple[str, ...]:
    limitations = {
        "producer-side single-Organization analysis",
        "derived from MarketReadiness; not a Decision",
        "not export authorization",
        "not external authority recognition",
        "no forecast included",
        "no buyer visibility",
    }
    if any(entry.status is MarketReadinessStatus.NOT_EVALUATED for entry in report.entries):
        limitations.add("population contains not evaluated subjects")
    if any(entry.status is MarketReadinessStatus.INDETERMINATE for entry in report.entries):
        limitations.add("population contains indeterminate subjects")
    if any(entry.status is MarketReadinessStatus.REASSESSMENT_REQUIRED for entry in report.entries):
        limitations.add("population contains subjects requiring reassessment")
    return tuple(sorted(limitations))


@dataclass(frozen=True, slots=True)
class MarketSupplyAggregatePayloadBuilder:
    """Builds the public aggregate payload from canonical MarketReadiness reports.

    This is not a disclosure decision and not a Policy/Evaluation engine. The
    returned mapping is still subject to privacy, audit and public response
    mapping before it can be released externally.
    """

    def build_from_readiness_reports(
        self,
        *,
        reports: tuple[MarketReadinessReport, ...],
        requested_quantity: int | None,
    ) -> dict[str, Any]:
        if requested_quantity is not None and requested_quantity < 1:
            raise ValueError("requested_quantity deve ser inteiro >= 1 quando informado.")
        if not reports:
            readiness_counts = {status.value: 0 for status in MarketReadinessStatus}
            return _aggregate_payload(
                readiness_counts=readiness_counts,
                requested_quantity=requested_quantity,
                gap_summary=(),
                limitations=("no authorized candidate population",),
            )
        _assert_homogeneous_context(reports)
        readiness_counts = {
            status.value: sum(report.counts.get(status, 0) for report in reports)
            for status in MarketReadinessStatus
        }
        gap_counts: Counter[str] = Counter()
        limitations = {
            "derived from MarketReadiness; not a Decision",
            "not export authorization",
            "not external authority recognition",
            "no forecast included",
            "aggregate summary only",
        }
        for report in reports:
            for gap in report.gap_summary:
                public_gap_code = _public_gap_code(gap.code)
                if public_gap_code != gap.code:
                    limitations.add("some gap codes use a public general category")
                gap_counts[public_gap_code] += gap.count
            if any(entry.status is MarketReadinessStatus.NOT_EVALUATED for entry in report.entries):
                limitations.add("population contains not evaluated subjects")
            if any(entry.status is MarketReadinessStatus.INDETERMINATE for entry in report.entries):
                limitations.add("population contains indeterminate subjects")
            if any(
                entry.status is MarketReadinessStatus.REASSESSMENT_REQUIRED
                for entry in report.entries
            ):
                limitations.add("population contains subjects requiring reassessment")
        return _aggregate_payload(
            readiness_counts=readiness_counts,
            requested_quantity=requested_quantity,
            gap_summary=tuple(
                ProducerMarketSupplyGap(code=code, count=count)
                for code, count in sorted(gap_counts.items())
            ),
            limitations=tuple(sorted(limitations)),
        )


def _assert_homogeneous_context(reports: tuple[MarketReadinessReport, ...]) -> None:
    first = reports[0].context
    for report in reports[1:]:
        context = report.context
        if (
            context.purpose != first.purpose
            or context.policy_id != first.policy_id
            or context.policy_version != first.policy_version
            or context.reference_time != first.reference_time
            or context.knowledge_cutoff != first.knowledge_cutoff
        ):
            raise ValueError("Market Supply aggregate exige reports com contexto homogeneo.")


def _aggregate_payload(
    *,
    readiness_counts: dict[str, int],
    requested_quantity: int | None,
    gap_summary: tuple[ProducerMarketSupplyGap, ...],
    limitations: tuple[str, ...],
) -> dict[str, Any]:
    ready_now = readiness_counts[MarketReadinessStatus.READY.value]
    return {
        "population_count": sum(readiness_counts.values()),
        "readiness_counts": readiness_counts,
        "ready_now": ready_now,
        "conditioned": readiness_counts[MarketReadinessStatus.CONDITIONED.value],
        "indeterminate": readiness_counts[MarketReadinessStatus.INDETERMINATE.value],
        "not_ready": readiness_counts[MarketReadinessStatus.NOT_READY.value],
        "not_evaluated": readiness_counts[MarketReadinessStatus.NOT_EVALUATED.value],
        "reassessment_required": readiness_counts[
            MarketReadinessStatus.REASSESSMENT_REQUIRED.value
        ],
        "current_capacity": ready_now,
        "requested_quantity": requested_quantity,
        "estimated_shortage_now": (
            None if requested_quantity is None else max(requested_quantity - ready_now, 0)
        ),
        "gap_summary": tuple({"code": gap.code, "count": gap.count} for gap in gap_summary),
        "limitations": limitations,
    }


def _public_gap_code(code: str) -> str:
    normalized = code.casefold()
    blocked_fragments = ("id", "identifier", "producer", "property", "animal")
    if any(fragment in normalized for fragment in blocked_fragments):
        return "GENERAL_GAP"
    return code


@dataclass(frozen=True, slots=True)
class MarketSupplyOptionalityAggregation:
    """Internal aggregate of readiness and optionality over authorized snapshots."""

    population_count: int
    excluded_count: int
    rejected_contribution_subject_count: int
    evaluated_optionality_count: int
    missing_optionality_count: int
    readiness_counts: dict[str, int]
    option_counts: dict[str, int]
    limitations: tuple[str, ...]
    result_boundary: str = MARKET_ELIGIBILITY_RESULT_BOUNDARY


@dataclass(frozen=True, slots=True)
class MarketSupplyOptionalityAggregationService:
    """Aggregates supplied optionality assessments without resolving population."""

    def build(
        self,
        *,
        population_result: AuthorizedCandidatePopulationResult,
        readiness_reports: tuple[MarketReadinessReport, ...],
        optionality_assessments: tuple[MarketOptionAssessment, ...],
    ) -> MarketSupplyOptionalityAggregation:
        _assert_reports_match_population(population_result, readiness_reports)
        included_subjects = frozenset(
            subject_id
            for snapshot in population_result.snapshots
            for subject_id in snapshot.included_subject_ids
        )
        assessments_by_subject = _index_optionality_for_population(
            population_result=population_result,
            optionality_assessments=optionality_assessments,
        )
        readiness_counts = {
            status.value: sum(report.counts.get(status, 0) for report in readiness_reports)
            for status in MarketReadinessStatus
        }
        option_counts = {state.value: 0 for state in MarketOptionState}
        for assessment in assessments_by_subject.values():
            option_counts[assessment.state.value] += 1

        missing_optionality_count = len(included_subjects) - len(assessments_by_subject)
        limitations = {
            "derived from authorized CandidatePopulationSnapshot and MarketReadiness",
            "optionality is derived; not a Decision",
            "no forecast included",
            "aggregate summary only",
        }
        if missing_optionality_count:
            limitations.add("population contains subjects without optionality assessment")
        if any(snapshot.excluded_count for snapshot in population_result.snapshots):
            limitations.add("candidate population contains explicit exclusions")
        if population_result.rejected_contributions:
            limitations.add("candidate population contains rejected contributions")

        return MarketSupplyOptionalityAggregation(
            population_count=len(included_subjects),
            excluded_count=sum(snapshot.excluded_count for snapshot in population_result.snapshots),
            rejected_contribution_subject_count=sum(
                rejection.subject_count for rejection in population_result.rejected_contributions
            ),
            evaluated_optionality_count=len(assessments_by_subject),
            missing_optionality_count=missing_optionality_count,
            readiness_counts=readiness_counts,
            option_counts=option_counts,
            limitations=tuple(sorted(limitations)),
        )


@dataclass(frozen=True, slots=True)
class MarketSupplyReadinessCompositionService:
    """Builds MarketReadiness reports for authorized owner-scoped snapshots."""

    decision_reader: MarketReadinessDecisionReaderPort
    evaluation_reader: MarketReadinessEvaluationReaderPort
    readiness_service: MarketReadinessService
    owner_scoped_executor: "MarketSupplyOwnerScopedReadinessExecutorPort | None" = None

    def build_reports(
        self,
        *,
        population_result: AuthorizedCandidatePopulationResult,
    ) -> tuple[MarketReadinessReport, ...]:
        reports: list[MarketReadinessReport] = []
        for snapshot in population_result.snapshots:
            criteria = snapshot.criteria
            context = MarketReadinessContext(
                organization_id=criteria.organization_id,
                purpose=criteria.purpose,
                policy_id=criteria.policy_id,
                policy_version=criteria.policy_version,
                reference_time=criteria.reference_time,
                knowledge_cutoff=criteria.knowledge_cutoff,
            )
            reader = MarketReadinessPopulationReader(
                decision_repository=self.decision_reader,
                evaluation_repository=self.evaluation_reader,
                readiness_service=self.readiness_service,
            )

            def build(
                *,
                context: MarketReadinessContext = context,
                reader: MarketReadinessPopulationReader = reader,
                snapshot: Any = snapshot,
            ) -> MarketReadinessReport:
                return reader.build_for_animals(
                    context=context,
                    animal_ids=snapshot.included_subject_ids,
                )

            if self.owner_scoped_executor is None:
                reports.append(build())
            else:
                reports.append(
                    self.owner_scoped_executor.run_for_owner(
                        organization_id=criteria.organization_id,
                        callback=build,
                    )
                )
        return tuple(reports)


class MarketSupplyOwnerScopedReadinessExecutorPort(Protocol):
    """Runs readiness reads under the contributor's own RLS context."""

    def run_for_owner(
        self,
        *,
        organization_id: OrganizationId,
        callback: Callable[[], MarketReadinessReport],
    ) -> MarketReadinessReport: ...


@dataclass(frozen=True, slots=True)
class MarketSupplyAggregateAssessmentCommand:
    buyer_organization_id: OrganizationId
    base_criteria: CandidatePopulationCriteria
    requested_quantity: int | None
    privacy_profile: AggregationPrivacyProfile
    geographic_precision: AggregationGeographicPrecision
    filter_count: int
    requested_at: datetime
    audit_id: TypedId
    correlation_id: TypedId
    idempotency_reference: str
    semantic_request_digest: str
    rare_attribute_filters: tuple[str, ...] = ()
    previous_queries: tuple[AggregationQueryFingerprint, ...] = ()

    def __post_init__(self) -> None:
        if self.requested_quantity is not None and self.requested_quantity < 1:
            raise ValueError("requested_quantity deve ser inteiro >= 1 quando informado.")
        if self.base_criteria.organization_id != self.buyer_organization_id:
            raise ValueError("base_criteria deve representar a Organization compradora.")
        if self.filter_count < 0:
            raise ValueError("filter_count nao pode ser negativo.")
        if self.audit_id.entity_type != "market_supply_query_audit":
            raise ValueError("audit_id deve ter entity_type 'market_supply_query_audit'.")
        if self.correlation_id.entity_type != "correlation":
            raise ValueError("correlation_id deve ter entity_type 'correlation'.")
        for field_name in ("idempotency_reference", "semantic_request_digest"):
            if not getattr(self, field_name).strip():
                raise ValueError(f"{field_name} deve ser texto nao vazio.")
        require_utc(self.requested_at, field_name="requested_at")


@dataclass(frozen=True, slots=True)
class MarketSupplyPreparedAggregateAssessment:
    population: AuthorizedCandidatePopulationComposition
    readiness_reports: tuple[MarketReadinessReport, ...]
    aggregate_payload: dict[str, Any]


@dataclass(frozen=True, slots=True)
class MarketSupplyPreparedAggregateGateRequest:
    assessment: MarketSupplyPreparedAggregateAssessment
    request: MarketSupplyAggregateGateRequest


@dataclass(frozen=True, slots=True)
class MarketSupplyAggregateAssessmentOrchestrator:
    """Application orchestration for the auditable F3.5 aggregate pipeline."""

    population_composer: AuthorizedCandidatePopulationCompositionService
    readiness_composer: MarketSupplyReadinessCompositionService
    payload_builder: MarketSupplyAggregatePayloadBuilder
    gate_workflow: MarketSupplyAggregateGateWorkflow
    idempotent_gate_workflow: MarketSupplyIdempotentAggregateGateWorkflow | None = None

    def prepare(
        self,
        command: MarketSupplyAggregateAssessmentCommand,
    ) -> MarketSupplyPreparedAggregateAssessment:
        population = self.population_composer.compose(
            buyer_organization_id=command.buyer_organization_id,
            base_criteria=command.base_criteria,
            requested_at=command.requested_at,
        )
        reports = self.readiness_composer.build_reports(population_result=population.result)
        payload = self.payload_builder.build_from_readiness_reports(
            reports=reports,
            requested_quantity=command.requested_quantity,
        )
        return MarketSupplyPreparedAggregateAssessment(
            population=population,
            readiness_reports=reports,
            aggregate_payload=payload,
        )

    def assess_single_owner(
        self,
        command: MarketSupplyAggregateAssessmentCommand,
    ) -> tuple[MarketSupplyPreparedAggregateAssessment, MarketSupplyAggregateGateResult]:
        prepared_gate = self.build_single_owner_gate_request(command)
        result = self.gate_workflow.assess_aggregate_access(prepared_gate.request)
        return prepared_gate.assessment, result

    def execute_idempotent_single_owner(
        self,
        *,
        command: MarketSupplyAggregateAssessmentCommand,
        identity: MarketSupplyRequestIdentity,
        principal_reference: UniversalReference,
    ) -> tuple[MarketSupplyPreparedAggregateAssessment, IdempotencyExecution]:
        if self.idempotent_gate_workflow is None:
            raise ValueError("idempotent_gate_workflow e obrigatorio para execucao idempotente.")
        prepared_gate = self.build_single_owner_gate_request(command)
        execution = self.idempotent_gate_workflow.execute(
            identity=identity,
            principal_reference=principal_reference,
            requested_at=command.requested_at,
            request=prepared_gate.request,
        )
        return prepared_gate.assessment, execution

    def build_single_owner_gate_request(
        self,
        command: MarketSupplyAggregateAssessmentCommand,
    ) -> MarketSupplyPreparedAggregateGateRequest:
        prepared = self.prepare(command)
        accepted = prepared.population.result.accepted_contributions
        if len(accepted) != 1:
            return MarketSupplyPreparedAggregateGateRequest(
                assessment=prepared,
                request=_uniform_not_released_gate_request(command),
            )
        contribution = accepted[0]
        snapshot = contribution.snapshot
        universe = snapshot.internal_universe_summary()
        query_fingerprint = AggregationQueryFingerprint(
            requester_organization_id=command.buyer_organization_id,
            beneficiary_organization_id=command.buyer_organization_id,
            access_purpose=MARKET_SUPPLY_AGGREGATE_ASSESSMENT,
            policy_context_digest=snapshot.criteria.policy_context_digest(),
            filter_fingerprint=snapshot.criteria_digest,
            result_subject_count=snapshot.included_count,
            requested_at=command.requested_at,
        )
        privacy_input = AggregationPrivacyInput(
            privacy_policy=command.privacy_profile.policy,
            organization_count=universe.organization_count,
            property_count=0 if universe.property_count is None else universe.property_count,
            subject_count=universe.subject_count,
            geographic_precision=command.geographic_precision,
            filter_count=command.filter_count,
            rare_attribute_filters=command.rare_attribute_filters,
            current_query=query_fingerprint,
            previous_queries=command.previous_queries,
        )
        authorization_request = MarketSupplyAuthorizationRequest(
            owner_organization_id=contribution.owner_organization_id,
            beneficiary_organization_id=command.buyer_organization_id,
            policy_id=snapshot.criteria.policy_id,
            access_purpose=MARKET_SUPPLY_AGGREGATE_ASSESSMENT,
            field_scope_profile=MARKET_SUPPLY_AGGREGATE_FIELD_SCOPE,
            requested_at=command.requested_at,
        )
        audit_context = MarketSupplyAuditRecordContext(
            audit_id=command.audit_id,
            policy_version=snapshot.criteria.policy_version,
            privacy_profile_id=command.privacy_profile.profile_id,
            authorization_context_digest=_authorization_context_digest(contribution.grant),
            candidate_population_digest=snapshot.snapshot_digest,
            reference_time=snapshot.criteria.reference_time,
            knowledge_cutoff=snapshot.criteria.knowledge_cutoff,
            requested_at=command.requested_at,
            revocation_state=MarketSupplyRevocationState.NOT_REVOKED,
            correlation_id=command.correlation_id,
            idempotency_reference=command.idempotency_reference,
            semantic_request_digest=command.semantic_request_digest,
            population_digest=universe.population_digest,
        )
        return MarketSupplyPreparedAggregateGateRequest(
            assessment=prepared,
            request=MarketSupplyAggregateGateRequest(
                audit_owner_organization_id=contribution.owner_organization_id,
                authorization_request=authorization_request,
                query_policy_id=snapshot.criteria.policy_id,
                query_fingerprint=query_fingerprint,
                recorded_at=command.requested_at,
                grant=contribution.grant,
                population_snapshot=snapshot,
                privacy_input=privacy_input,
                aggregate_payload=prepared.aggregate_payload,
                audit_record_context=audit_context,
                request_candidate_criteria_digest=command.base_criteria.digest(),
            ),
        )


def _uniform_not_released_gate_request(
    command: MarketSupplyAggregateAssessmentCommand,
) -> MarketSupplyAggregateGateRequest:
    query_fingerprint = AggregationQueryFingerprint(
        requester_organization_id=command.buyer_organization_id,
        beneficiary_organization_id=command.buyer_organization_id,
        access_purpose=MARKET_SUPPLY_AGGREGATE_ASSESSMENT,
        policy_context_digest=command.base_criteria.policy_context_digest(),
        filter_fingerprint=command.base_criteria.digest(),
        result_subject_count=0,
        requested_at=command.requested_at,
    )
    authorization_request = MarketSupplyAuthorizationRequest(
        owner_organization_id=command.buyer_organization_id,
        beneficiary_organization_id=command.buyer_organization_id,
        policy_id=command.base_criteria.policy_id,
        access_purpose=MARKET_SUPPLY_AGGREGATE_ASSESSMENT,
        field_scope_profile=MARKET_SUPPLY_AGGREGATE_FIELD_SCOPE,
        requested_at=command.requested_at,
    )
    return MarketSupplyAggregateGateRequest(
        audit_owner_organization_id=command.buyer_organization_id,
        authorization_request=authorization_request,
        query_policy_id=command.base_criteria.policy_id,
        query_fingerprint=query_fingerprint,
        recorded_at=command.requested_at,
        grant=None,
        aggregate_payload=None,
        audit_record_context=MarketSupplyAuditRecordContext(
            audit_id=command.audit_id,
            policy_version=command.base_criteria.policy_version,
            privacy_profile_id=command.privacy_profile.profile_id,
            authorization_context_digest="authorization:sha256:uniform-not-released",
            candidate_population_digest=command.base_criteria.policy_context_digest(),
            reference_time=command.base_criteria.reference_time,
            knowledge_cutoff=command.base_criteria.knowledge_cutoff,
            requested_at=command.requested_at,
            revocation_state=MarketSupplyRevocationState.NOT_REVOKED,
            correlation_id=command.correlation_id,
            idempotency_reference=command.idempotency_reference,
            semantic_request_digest=command.semantic_request_digest,
        ),
        request_candidate_criteria_digest=command.base_criteria.digest(),
    )


def _authorization_context_digest(grant: AuthorizationGrant) -> str:
    return hashlib.sha256(
        _SERIALIZER.serialize(
            canonicalize_for_hash(
                {
                    "schema": "titan.market_supply.authorization_context",
                    "version": 1,
                    "grant_id": str(grant.grant_id),
                    "owner_organization_id": str(grant.owner_organization_id.value),
                    "beneficiary_organization_id": str(
                        grant.beneficiary_organization_id.value,
                    ),
                    "policy_id": str(grant.policy_id.value),
                    "policy_version_id": str(grant.policy_version_id.value),
                    "access_purpose": grant.access_purpose,
                    "field_scope_profile": grant.field_scope_profile,
                    "valid_from": grant.valid_from,
                    "valid_until": grant.valid_until,
                    "status": grant.status,
                    "revoked_at": grant.revoked_at,
                }
            ),
        ),
    ).hexdigest()


def _assert_reports_match_population(
    population_result: AuthorizedCandidatePopulationResult,
    reports: tuple[MarketReadinessReport, ...],
) -> None:
    if len(population_result.snapshots) != len(reports):
        raise ValueError("readiness reports devem corresponder aos snapshots autorizados.")
    for snapshot, report in zip(population_result.snapshots, reports, strict=True):
        criteria = snapshot.criteria
        context = report.context
        if (
            context.organization_id != criteria.organization_id
            or context.purpose != criteria.purpose
            or context.policy_id != criteria.policy_id
            or context.policy_version != criteria.policy_version
            or context.reference_time != criteria.reference_time
            or context.knowledge_cutoff != criteria.knowledge_cutoff
        ):
            raise ValueError("readiness report diverge do CandidatePopulationSnapshot.")
        report_subjects = frozenset(entry.subject_id for entry in report.entries)
        if report_subjects != frozenset(snapshot.included_subject_ids):
            raise ValueError("readiness report deve cobrir exatamente os subjects do snapshot.")


def _index_optionality_for_population(
    *,
    population_result: AuthorizedCandidatePopulationResult,
    optionality_assessments: tuple[MarketOptionAssessment, ...],
) -> dict[TypedId, MarketOptionAssessment]:
    snapshots_by_subject: dict[TypedId, CandidatePopulationCriteria] = {}
    for snapshot in population_result.snapshots:
        for subject_id in snapshot.included_subject_ids:
            if subject_id in snapshots_by_subject:
                raise ValueError("subject duplicado em CandidatePopulationSnapshot.")
            snapshots_by_subject[subject_id] = snapshot.criteria

    indexed: dict[TypedId, MarketOptionAssessment] = {}
    for assessment in optionality_assessments:
        subject_id = assessment.context.subject_id
        if subject_id in indexed:
            raise ValueError("optionality assessment duplicado para subject.")
        criteria = snapshots_by_subject.get(subject_id)
        if criteria is None:
            raise ValueError("optionality assessment fora da população candidata.")
        if (
            assessment.context.organization_id != criteria.organization_id
            or assessment.context.market_purpose != criteria.purpose
            or assessment.context.policy_id != criteria.policy_id
            or assessment.context.policy_version != criteria.policy_version
            or assessment.context.reference_time != criteria.reference_time
            or assessment.context.knowledge_cutoff != criteria.knowledge_cutoff
        ):
            raise ValueError("optionality assessment diverge do CandidatePopulationSnapshot.")
        indexed[subject_id] = assessment
    return indexed
