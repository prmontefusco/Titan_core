"""In-memory Market Supply aggregate gate orchestration.

This module fixes the order for future aggregate release checks without creating
population resolution, persistence, APIs, workers or cross-tenant reads.
"""

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import datetime
from types import MappingProxyType
from typing import Any, Protocol
from uuid import UUID

from packages.core_application.idempotency import IdempotencyExecution
from packages.core_domain.policy_sharing import AuthorizationGrant
from packages.livestock_application.market_supply_audit import (
    MarketSupplyAggregateQueryAuditEnvelope,
    MarketSupplyAggregateQueryAuditPlanner,
    MarketSupplyAggregateQueryAuditRequest,
    MarketSupplyAuditOutcome,
    MarketSupplyQueryAuditRecord,
    MarketSupplyQueryAuditRepositoryPort,
    MarketSupplyRevocationState,
)
from packages.livestock_application.market_supply_authorization import (
    MarketSupplyAuthorizationReason,
    MarketSupplyAuthorizationRequest,
    MarketSupplyAuthorizationService,
)
from packages.livestock_application.market_supply_population import CandidatePopulationSnapshot
from packages.livestock_application.market_supply_privacy import (
    AggregationPrivacyAssessment,
    AggregationPrivacyAssessmentService,
    AggregationPrivacyInput,
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
)
from packages.shared_kernel import (
    CanonicalSerializer,
    OrganizationId,
    TypedId,
    UniversalReference,
    canonicalize_for_hash,
)
from packages.shared_kernel.temporal import require_utc

_SERIALIZER = CanonicalSerializer()


class MarketSupplyAuthorizationGrantReaderPort(Protocol):
    """Reads the freshest grant state for pre-release revocation checks."""

    def get_by_id(self, grant_id: UUID) -> AuthorizationGrant | None: ...


@dataclass(frozen=True, slots=True)
class MarketSupplyAuditRecordContext:
    audit_id: TypedId
    policy_version: int
    privacy_profile_id: str
    authorization_context_digest: str
    candidate_population_digest: str
    reference_time: datetime
    knowledge_cutoff: datetime
    requested_at: datetime
    revocation_state: MarketSupplyRevocationState
    correlation_id: TypedId
    idempotency_reference: str
    semantic_request_digest: str
    population_digest: str | None = None

    def __post_init__(self) -> None:
        if self.audit_id.entity_type != "market_supply_query_audit":
            raise ValueError("audit_id deve ter entity_type 'market_supply_query_audit'.")
        if self.policy_version < 1:
            raise ValueError("policy_version deve ser inteiro >= 1.")
        for field_name in (
            "privacy_profile_id",
            "authorization_context_digest",
            "candidate_population_digest",
            "idempotency_reference",
            "semantic_request_digest",
        ):
            if not getattr(self, field_name).strip():
                raise ValueError(f"{field_name} deve ser texto nao vazio.")
        if self.population_digest is not None and not self.population_digest.strip():
            raise ValueError("population_digest deve ser texto nao vazio quando informado.")
        if self.correlation_id.entity_type != "correlation":
            raise ValueError("correlation_id deve ter entity_type 'correlation'.")
        for field_name in (
            "reference_time",
            "knowledge_cutoff",
            "requested_at",
        ):
            require_utc(getattr(self, field_name), field_name=field_name)


@dataclass(frozen=True, slots=True)
class MarketSupplyAggregateGateRequest:
    audit_owner_organization_id: OrganizationId
    authorization_request: MarketSupplyAuthorizationRequest
    query_policy_id: TypedId
    query_fingerprint: AggregationQueryFingerprint
    recorded_at: datetime
    grant: AuthorizationGrant | None
    population_snapshot: CandidatePopulationSnapshot | None = None
    privacy_input: AggregationPrivacyInput | None = None
    aggregate_payload: Mapping[str, Any] | None = None
    audit_record_context: MarketSupplyAuditRecordContext | None = None

    def __post_init__(self) -> None:
        if self.audit_owner_organization_id != self.authorization_request.owner_organization_id:
            raise ValueError("audit_owner_organization_id diverge da owner Organization.")
        if self.query_policy_id.entity_type != "policy":
            raise ValueError("query_policy_id deve ter entity_type 'policy'.")
        if self.query_policy_id != self.authorization_request.policy_id:
            raise ValueError("query_policy_id diverge da authorization_request.")
        if (
            self.query_fingerprint.requester_organization_id
            != self.authorization_request.beneficiary_organization_id
        ):
            raise ValueError("query_fingerprint requester diverge da Organization beneficiaria.")
        if (
            self.query_fingerprint.beneficiary_organization_id
            != self.authorization_request.beneficiary_organization_id
        ):
            raise ValueError("query_fingerprint beneficiary diverge da Organization beneficiaria.")
        if self.query_fingerprint.access_purpose != self.authorization_request.access_purpose:
            raise ValueError("query_fingerprint access_purpose diverge da authorization_request.")
        if self.population_snapshot is not None:
            _validate_population_snapshot(
                snapshot=self.population_snapshot,
                authorization_request=self.authorization_request,
                query_fingerprint=self.query_fingerprint,
            )
        if (
            self.privacy_input is not None
            and self.privacy_input.current_query != self.query_fingerprint
        ):
            raise ValueError("privacy_input.current_query diverge do query_fingerprint.")
        if self.population_snapshot is not None and self.privacy_input is not None:
            _validate_privacy_input_population_counts(
                privacy_input=self.privacy_input,
                population_snapshot=self.population_snapshot,
            )
        if self.audit_record_context is not None:
            _validate_audit_record_context(
                context=self.audit_record_context,
                query_fingerprint=self.query_fingerprint,
                population_snapshot=self.population_snapshot,
            )
        require_utc(self.recorded_at, field_name="recorded_at")


@dataclass(frozen=True, slots=True)
class MarketSupplyAggregateGateResult:
    audit_envelope: MarketSupplyAggregateQueryAuditEnvelope
    public_response: MarketSupplyPublicAggregateResponse
    audit_record: MarketSupplyQueryAuditRecord | None = None
    aggregate_result: "MarketSupplyAggregateResult | None" = None


@dataclass(frozen=True, slots=True)
class MarketSupplyAggregateResult:
    """Internally releasable aggregate bound to snapshot, disclosure and audit."""

    population_snapshot: CandidatePopulationSnapshot
    disclosure_decision: DisclosureDecision
    audit_record: MarketSupplyQueryAuditRecord
    aggregate_payload: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not self.disclosure_decision.allows_external_release:
            raise ValueError("aggregate result exige DisclosureDecision liberavel.")
        if self.audit_record.outcome is not MarketSupplyAuditOutcome.RELEASED:
            raise ValueError("aggregate result exige audit record RELEASED.")
        if self.audit_record.disclosure_state != self.disclosure_decision.state:
            raise ValueError("aggregate result diverge do disclosure state auditado.")
        if (
            self.disclosure_decision.candidate_population_digest
            != self.population_snapshot.snapshot_digest
        ):
            raise ValueError("aggregate result diverge da CandidatePopulationSnapshot.")
        if (
            self.audit_record.candidate_population_digest
            != self.population_snapshot.snapshot_digest
        ):
            raise ValueError("aggregate result auditado diverge da CandidatePopulationSnapshot.")
        if self.audit_record.query_fingerprint != self.disclosure_decision.query_fingerprint:
            raise ValueError("aggregate result diverge do query fingerprint auditado.")
        if self.audit_record.result_digest != _payload_digest(self.aggregate_payload):
            raise ValueError("aggregate result diverge do result_digest auditado.")
        object.__setattr__(
            self,
            "aggregate_payload",
            MappingProxyType(dict(self.aggregate_payload)),
        )


class MarketSupplyAggregateGateWorkflow:
    """Composes authorization, privacy, audit and public-response gates."""

    def __init__(
        self,
        *,
        authorization_service: MarketSupplyAuthorizationService | None = None,
        privacy_service: AggregationPrivacyAssessmentService | None = None,
        audit_planner: MarketSupplyAggregateQueryAuditPlanner | None = None,
        audit_repository: MarketSupplyQueryAuditRepositoryPort | None = None,
        grant_reader: MarketSupplyAuthorizationGrantReaderPort | None = None,
        response_mapper: MarketSupplyPublicResponseMapper | None = None,
    ) -> None:
        self._authorization_service = authorization_service or MarketSupplyAuthorizationService()
        self._privacy_service = privacy_service or AggregationPrivacyAssessmentService()
        self._audit_planner = audit_planner or MarketSupplyAggregateQueryAuditPlanner()
        self._audit_repository = audit_repository
        self._grant_reader = grant_reader
        self._response_mapper = response_mapper or MarketSupplyPublicResponseMapper()

    def assess_aggregate_access(
        self,
        request: MarketSupplyAggregateGateRequest,
    ) -> MarketSupplyAggregateGateResult:
        authorization = self._authorization_service.assess_aggregate_access(
            request=request.authorization_request,
            grant=request.grant,
        )
        privacy = None
        if authorization.permitted:
            if request.privacy_input is None:
                raise ValueError("privacy_input e obrigatorio quando autorizacao permite.")
            privacy_input = request.privacy_input
            if self._audit_repository is not None:
                privacy_input = replace(
                    privacy_input,
                    previous_queries=(
                        *privacy_input.previous_queries,
                        *self._audit_repository.find_related_query_fingerprints(
                            requester_organization_id=(
                                request.query_fingerprint.requester_organization_id
                            ),
                            beneficiary_organization_id=(
                                request.query_fingerprint.beneficiary_organization_id
                            ),
                            access_purpose=request.query_fingerprint.access_purpose,
                            policy_context_digest=(request.query_fingerprint.policy_context_digest),
                        ),
                    ),
                )
            privacy = self._privacy_service.assess(privacy_input)
            pre_release_grant = self._grant_for_pre_release(request)
            pre_release_authorization = self._authorization_service.assess_aggregate_access(
                request=replace(request.authorization_request, requested_at=request.recorded_at),
                grant=pre_release_grant,
            )
            if not pre_release_authorization.permitted:
                authorization = pre_release_authorization
                privacy = None

        audit_envelope = self._audit_planner.plan(
            MarketSupplyAggregateQueryAuditRequest(
                audit_owner_organization_id=request.audit_owner_organization_id,
                requester_organization_id=request.authorization_request.beneficiary_organization_id,
                beneficiary_organization_id=request.authorization_request.beneficiary_organization_id,
                policy_id=request.query_policy_id,
                access_purpose=request.authorization_request.access_purpose,
                field_scope_profile=request.authorization_request.field_scope_profile,
                query_fingerprint=request.query_fingerprint,
                recorded_at=request.recorded_at,
                authorization=authorization,
                privacy=privacy,
                grant_id=None if request.grant is None else request.grant.grant_id,
            ),
        )
        public_aggregate_payload = None
        if audit_envelope.outcome is MarketSupplyAuditOutcome.RELEASED:
            public_aggregate_payload = self._response_mapper.validate_aggregate_payload(
                request.aggregate_payload,
            )
        audit_record = None
        disclosure_decision = None
        if request.audit_record_context is not None:
            if self._audit_repository is None:
                raise ValueError("audit_repository e obrigatorio com audit_record_context.")
            revocation_state = request.audit_record_context.revocation_state
            if authorization.reason is MarketSupplyAuthorizationReason.REVOKED_GRANT:
                revocation_state = MarketSupplyRevocationState.REVOKED_OBSERVED
            disclosure_decision = _build_disclosure_decision(
                audit_envelope=audit_envelope,
                privacy=privacy,
                query_fingerprint=request.query_fingerprint,
                candidate_population_digest=(
                    request.audit_record_context.candidate_population_digest
                ),
                evaluated_at=request.recorded_at,
            )
            audit_record = MarketSupplyQueryAuditRecord.from_envelope(
                audit_id=request.audit_record_context.audit_id,
                envelope=audit_envelope,
                policy_version=request.audit_record_context.policy_version,
                privacy_profile_id=request.audit_record_context.privacy_profile_id,
                authorization_context_digest=(
                    request.audit_record_context.authorization_context_digest
                ),
                candidate_population_digest=(
                    request.audit_record_context.candidate_population_digest
                ),
                reference_time=request.audit_record_context.reference_time,
                knowledge_cutoff=request.audit_record_context.knowledge_cutoff,
                requested_at=request.audit_record_context.requested_at,
                disclosure_decision=disclosure_decision,
                result_digest=_aggregate_payload_digest(
                    public_aggregate_payload,
                    audit_envelope=audit_envelope,
                ),
                revocation_state=revocation_state,
                correlation_id=request.audit_record_context.correlation_id,
                idempotency_reference=request.audit_record_context.idempotency_reference,
                semantic_request_digest=request.audit_record_context.semantic_request_digest,
                population_digest=request.audit_record_context.population_digest,
            )
            self._audit_repository.append(audit_record)

        if self._audit_repository is not None and audit_record is None:
            raise ValueError("audit_record_context e obrigatorio para workflow auditavel.")

        aggregate_result = None
        if audit_envelope.outcome is MarketSupplyAuditOutcome.RELEASED and audit_record is None:
            raise ValueError("release agregado exige audit record duravel.")
        if audit_envelope.outcome is MarketSupplyAuditOutcome.RELEASED and audit_record is not None:
            if request.population_snapshot is None:
                raise ValueError("population_snapshot e obrigatorio para aggregate result.")
            if disclosure_decision is None:
                raise ValueError("DisclosureDecision e obrigatoria para aggregate result.")
            if public_aggregate_payload is None:
                raise ValueError("aggregate_payload e obrigatorio para aggregate result.")
            aggregate_result = MarketSupplyAggregateResult(
                population_snapshot=request.population_snapshot,
                disclosure_decision=disclosure_decision,
                audit_record=audit_record,
                aggregate_payload=public_aggregate_payload,
            )

        return MarketSupplyAggregateGateResult(
            audit_envelope=audit_envelope,
            audit_record=audit_record,
            aggregate_result=aggregate_result,
            public_response=self._response_mapper.map_aggregate(
                envelope=audit_envelope,
                aggregate_payload=public_aggregate_payload,
            ),
        )

    def assess_reexecution_authorization(
        self,
        *,
        request: MarketSupplyAggregateGateRequest,
        requested_at: datetime,
    ) -> MarketSupplyAuthorizationReason | None:
        """Checks fresh revocation state before idempotent replay."""

        grant = self._grant_for_reexecution(request)
        assessment = self._authorization_service.assess_aggregate_access(
            request=replace(request.authorization_request, requested_at=requested_at),
            grant=grant,
        )
        return None if assessment.permitted else assessment.reason

    def _grant_for_pre_release(
        self,
        request: MarketSupplyAggregateGateRequest,
    ) -> AuthorizationGrant | None:
        if self._audit_repository is None:
            return request.grant
        return self._fresh_grant(request)

    def _grant_for_reexecution(
        self,
        request: MarketSupplyAggregateGateRequest,
    ) -> AuthorizationGrant | None:
        if self._audit_repository is None:
            return request.grant
        return self._fresh_grant(request)

    def _fresh_grant(
        self,
        request: MarketSupplyAggregateGateRequest,
    ) -> AuthorizationGrant | None:
        if request.grant is None:
            return None
        if self._grant_reader is None:
            raise ValueError("grant_reader e obrigatorio para workflow auditavel.")
        return self._grant_reader.get_by_id(request.grant.grant_id)


@dataclass(frozen=True, slots=True)
class MarketSupplyIdempotentAggregateGateWorkflow:
    """Runs the aggregate gate under Core semantic idempotency."""

    workflow: MarketSupplyAggregateGateWorkflow
    idempotency_gate: MarketSupplyIdempotencyGate

    def execute(
        self,
        *,
        identity: MarketSupplyRequestIdentity,
        principal_reference: UniversalReference,
        requested_at: datetime,
        request: MarketSupplyAggregateGateRequest,
    ) -> IdempotencyExecution:
        _validate_idempotent_workflow_identity(identity=identity, request=request)
        replay_authorization_reason = self.workflow.assess_reexecution_authorization(
            request=request,
            requested_at=requested_at,
        )
        if replay_authorization_reason is MarketSupplyAuthorizationReason.REVOKED_GRANT:
            result = self.workflow.assess_aggregate_access(request).public_response
            payload = result.to_canonical_payload()
            return IdempotencyExecution(
                payload.schema,
                payload.version,
                payload.canonical_bytes,
                False,
            )
        return self.idempotency_gate.execute(
            identity=identity,
            principal_reference=principal_reference,
            requested_at=requested_at,
            handler=lambda: self.workflow.assess_aggregate_access(
                request,
            ).public_response.to_canonical_payload(),
        )


def _validate_population_snapshot(
    *,
    snapshot: CandidatePopulationSnapshot,
    authorization_request: MarketSupplyAuthorizationRequest,
    query_fingerprint: AggregationQueryFingerprint,
) -> None:
    if snapshot.criteria.organization_id != authorization_request.owner_organization_id:
        raise ValueError("population_snapshot Organization diverge da owner Organization.")
    if snapshot.criteria.policy_id != authorization_request.policy_id:
        raise ValueError("population_snapshot Policy diverge da authorization_request.")
    if snapshot.criteria.purpose != authorization_request.access_purpose:
        raise ValueError("population_snapshot purpose diverge da authorization_request.")
    if snapshot.criteria.policy_context_digest() != query_fingerprint.policy_context_digest:
        raise ValueError("query_fingerprint policy_context_digest diverge dos criterios.")
    if snapshot.included_count != query_fingerprint.result_subject_count:
        raise ValueError("query_fingerprint result_subject_count diverge da population_snapshot.")


def _validate_audit_record_context(
    *,
    context: MarketSupplyAuditRecordContext,
    query_fingerprint: AggregationQueryFingerprint,
    population_snapshot: CandidatePopulationSnapshot | None,
) -> None:
    if population_snapshot is None:
        if context.population_digest is not None:
            raise ValueError(
                "audit_record_context sem population_snapshot nao deve informar population_digest.",
            )
        if context.candidate_population_digest != query_fingerprint.policy_context_digest:
            raise ValueError(
                "audit_record_context population digest diverge do query_fingerprint.",
            )
        return
    if context.candidate_population_digest != population_snapshot.snapshot_digest:
        raise ValueError("audit_record_context population digest diverge da snapshot.")
    if context.reference_time != population_snapshot.criteria.reference_time:
        raise ValueError("audit_record_context reference_time diverge da snapshot.")
    if context.knowledge_cutoff != population_snapshot.criteria.knowledge_cutoff:
        raise ValueError("audit_record_context knowledge_cutoff diverge da snapshot.")
    if (
        context.population_digest is not None
        and context.population_digest
        != population_snapshot.internal_universe_summary().population_digest
    ):
        raise ValueError("audit_record_context deve usar population digest interno.")


def _validate_privacy_input_population_counts(
    *,
    privacy_input: AggregationPrivacyInput,
    population_snapshot: CandidatePopulationSnapshot,
) -> None:
    summary = population_snapshot.internal_universe_summary()
    if privacy_input.subject_count != summary.subject_count:
        raise ValueError("privacy_input subject_count diverge da CandidatePopulationSnapshot.")
    if privacy_input.organization_count != summary.organization_count:
        raise ValueError("privacy_input organization_count diverge da CandidatePopulationSnapshot.")
    if (
        summary.property_count is not None
        and privacy_input.property_count != summary.property_count
    ):
        raise ValueError("privacy_input property_count diverge da CandidatePopulationSnapshot.")


def _validate_idempotent_workflow_identity(
    *,
    identity: MarketSupplyRequestIdentity,
    request: MarketSupplyAggregateGateRequest,
) -> None:
    if identity.buyer_organization_id != request.authorization_request.beneficiary_organization_id:
        raise ValueError("MarketSupplyRequestIdentity buyer Organization diverge do request.")
    if identity.purpose != request.authorization_request.access_purpose:
        raise ValueError("MarketSupplyRequestIdentity purpose diverge do request.")
    if identity.policy_id != request.query_policy_id:
        raise ValueError("MarketSupplyRequestIdentity Policy diverge do request.")
    if request.population_snapshot is not None:
        if identity.policy_version != request.population_snapshot.criteria.policy_version:
            raise ValueError("MarketSupplyRequestIdentity policy_version diverge da snapshot.")
        if identity.candidate_criteria_digest != request.population_snapshot.criteria_digest:
            raise ValueError("MarketSupplyRequestIdentity criteria digest diverge da snapshot.")
    if request.audit_record_context is not None:
        if identity.policy_version != request.audit_record_context.policy_version:
            raise ValueError("MarketSupplyRequestIdentity policy_version diverge do audit context.")
        if identity.reference_time != request.audit_record_context.reference_time:
            raise ValueError("MarketSupplyRequestIdentity reference_time diverge do audit context.")
        if identity.knowledge_cutoff != request.audit_record_context.knowledge_cutoff:
            raise ValueError(
                "MarketSupplyRequestIdentity knowledge_cutoff diverge do audit context."
            )
        if identity.semantic_digest() != request.audit_record_context.semantic_request_digest:
            raise ValueError(
                "MarketSupplyRequestIdentity semantic digest diverge do audit context."
            )


def _build_disclosure_decision(
    *,
    audit_envelope: MarketSupplyAggregateQueryAuditEnvelope,
    privacy: AggregationPrivacyAssessment | None,
    query_fingerprint: AggregationQueryFingerprint,
    candidate_population_digest: str,
    evaluated_at: datetime,
) -> DisclosureDecision:
    if privacy is not None:
        return privacy.to_disclosure_decision(
            query_fingerprint=query_fingerprint,
            candidate_population_digest=candidate_population_digest,
            evaluated_at=evaluated_at,
        )
    return DisclosureDecision(
        state=(
            DisclosureDecisionState.ALLOW
            if audit_envelope.outcome is MarketSupplyAuditOutcome.RELEASED
            else DisclosureDecisionState.DENY
        ),
        reason_codes=(audit_envelope.authorization_reason or audit_envelope.outcome.value,),
        privacy_policy_version=1,
        query_fingerprint=query_fingerprint,
        candidate_population_digest=candidate_population_digest,
        evaluated_at=evaluated_at,
    )


def _aggregate_payload_digest(
    aggregate_payload: Mapping[str, Any] | None,
    *,
    audit_envelope: MarketSupplyAggregateQueryAuditEnvelope,
) -> str | None:
    if audit_envelope.outcome is not MarketSupplyAuditOutcome.RELEASED:
        return None
    if aggregate_payload is None:
        raise ValueError("aggregate_payload e obrigatorio para audit de release.")
    return _payload_digest(aggregate_payload)


def _payload_digest(aggregate_payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        _SERIALIZER.serialize(canonicalize_for_hash(aggregate_payload)),
    ).hexdigest()
