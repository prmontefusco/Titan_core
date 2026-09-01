"""Audit planning for future Market Supply aggregate access.

The objects here describe what must be captured around an aggregate query without
creating a production database model or API. Production storage remains gated by
schema, RLS and retention decisions.
"""

import hashlib
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from packages.livestock_application.market_supply_authorization import (
    MarketSupplyAuthorizationAssessment,
    MarketSupplyAuthorizationReason,
    MarketSupplyAuthorizationResult,
)
from packages.livestock_application.market_supply_privacy import (
    AggregationPrivacyAssessment,
    AggregationPrivacyDecision,
    AggregationQueryFingerprint,
    DisclosureDecision,
    DisclosureDecisionState,
)
from packages.shared_kernel import (
    CanonicalSerializer,
    OrganizationId,
    TypedId,
    canonicalize_for_hash,
)
from packages.shared_kernel.temporal import require_utc

_SERIALIZER = CanonicalSerializer()


class MarketSupplyAuditOutcome(StrEnum):
    RELEASED = "RELEASED"
    DENIED_BY_AUTHORIZATION = "DENIED_BY_AUTHORIZATION"
    PURPOSE_MISMATCH = "PURPOSE_MISMATCH"
    GRANT_REVOKED = "GRANT_REVOKED"
    SUPPRESSED_BY_PRIVACY = "SUPPRESSED_BY_PRIVACY"


class MarketSupplyAuditExternalDisposition(StrEnum):
    RELEASE_AGGREGATE = "RELEASE_AGGREGATE"
    UNIFORM_NOT_RELEASED = "UNIFORM_NOT_RELEASED"


class MarketSupplyRevocationState(StrEnum):
    NOT_APPLICABLE = "NOT_APPLICABLE"
    NOT_REVOKED = "NOT_REVOKED"
    REVOKED_OBSERVED = "REVOKED_OBSERVED"


@dataclass(frozen=True, slots=True)
class MarketSupplyAggregateQueryAuditEnvelope:
    audit_owner_organization_id: OrganizationId
    requester_organization_id: OrganizationId
    beneficiary_organization_id: OrganizationId
    policy_id: TypedId
    access_purpose: str
    field_scope_profile: str
    query_fingerprint: AggregationQueryFingerprint
    recorded_at: datetime
    outcome: MarketSupplyAuditOutcome
    external_disposition: MarketSupplyAuditExternalDisposition
    authorization_reason: str | None
    privacy_reasons: tuple[str, ...]
    grant_id: UUID | None = None

    def __post_init__(self) -> None:
        if self.policy_id.entity_type != "policy":
            raise ValueError("policy_id deve ter entity_type 'policy'.")
        if not self.access_purpose.strip():
            raise ValueError("access_purpose deve ser texto nao vazio.")
        if not self.field_scope_profile.strip():
            raise ValueError("field_scope_profile deve ser texto nao vazio.")
        require_utc(self.recorded_at, field_name="recorded_at")
        if self.query_fingerprint.requester_organization_id != self.requester_organization_id:
            raise ValueError("query_fingerprint requester diverge do envelope.")
        if self.query_fingerprint.beneficiary_organization_id != self.beneficiary_organization_id:
            raise ValueError("query_fingerprint beneficiary diverge do envelope.")
        if self.query_fingerprint.access_purpose != self.access_purpose:
            raise ValueError("query_fingerprint access_purpose diverge do envelope.")


@dataclass(frozen=True, slots=True)
class MarketSupplyAggregateQueryAuditRequest:
    audit_owner_organization_id: OrganizationId
    requester_organization_id: OrganizationId
    beneficiary_organization_id: OrganizationId
    policy_id: TypedId
    access_purpose: str
    field_scope_profile: str
    query_fingerprint: AggregationQueryFingerprint
    recorded_at: datetime
    authorization: MarketSupplyAuthorizationAssessment
    privacy: AggregationPrivacyAssessment | None
    grant_id: UUID | None = None


class MarketSupplyAggregateQueryAuditPlanner:
    """Builds an audit envelope after authorization/privacy assessment."""

    def plan(
        self,
        request: MarketSupplyAggregateQueryAuditRequest,
    ) -> MarketSupplyAggregateQueryAuditEnvelope:
        if request.authorization.result is not MarketSupplyAuthorizationResult.PERMITTED:
            return MarketSupplyAggregateQueryAuditEnvelope(
                audit_owner_organization_id=request.audit_owner_organization_id,
                requester_organization_id=request.requester_organization_id,
                beneficiary_organization_id=request.beneficiary_organization_id,
                policy_id=request.policy_id,
                access_purpose=request.access_purpose,
                field_scope_profile=request.field_scope_profile,
                query_fingerprint=request.query_fingerprint,
                recorded_at=request.recorded_at,
                outcome=_authorization_outcome(request.authorization.reason),
                external_disposition=MarketSupplyAuditExternalDisposition.UNIFORM_NOT_RELEASED,
                authorization_reason=request.authorization.reason.value,
                privacy_reasons=(),
                grant_id=request.grant_id,
            )

        if request.privacy is None:
            raise ValueError("privacy assessment e obrigatorio quando autorizacao permite.")

        if request.privacy.decision is AggregationPrivacyDecision.SUPPRESSED:
            return MarketSupplyAggregateQueryAuditEnvelope(
                audit_owner_organization_id=request.audit_owner_organization_id,
                requester_organization_id=request.requester_organization_id,
                beneficiary_organization_id=request.beneficiary_organization_id,
                policy_id=request.policy_id,
                access_purpose=request.access_purpose,
                field_scope_profile=request.field_scope_profile,
                query_fingerprint=request.query_fingerprint,
                recorded_at=request.recorded_at,
                outcome=MarketSupplyAuditOutcome.SUPPRESSED_BY_PRIVACY,
                external_disposition=MarketSupplyAuditExternalDisposition.UNIFORM_NOT_RELEASED,
                authorization_reason=request.authorization.reason.value,
                privacy_reasons=tuple(reason.value for reason in request.privacy.reasons),
                grant_id=request.grant_id,
            )

        return MarketSupplyAggregateQueryAuditEnvelope(
            audit_owner_organization_id=request.audit_owner_organization_id,
            requester_organization_id=request.requester_organization_id,
            beneficiary_organization_id=request.beneficiary_organization_id,
            policy_id=request.policy_id,
            access_purpose=request.access_purpose,
            field_scope_profile=request.field_scope_profile,
            query_fingerprint=request.query_fingerprint,
            recorded_at=request.recorded_at,
            outcome=MarketSupplyAuditOutcome.RELEASED,
            external_disposition=MarketSupplyAuditExternalDisposition.RELEASE_AGGREGATE,
            authorization_reason=request.authorization.reason.value,
            privacy_reasons=tuple(reason.value for reason in request.privacy.reasons),
            grant_id=request.grant_id,
        )


@dataclass(frozen=True, slots=True)
class MarketSupplyQueryAuditRecord:
    """Immutable audit record for a Market Supply query attempt.

    This is an application-level contract for F3.2. It intentionally stores
    digests and decision metadata, not sensitive subject payloads.
    """

    audit_id: TypedId
    audit_owner_organization_id: OrganizationId
    requester_organization_id: OrganizationId
    beneficiary_organization_id: OrganizationId
    access_purpose: str
    authorization_context_digest: str
    policy_id: TypedId
    policy_version: int
    privacy_profile_id: str
    privacy_profile_version: int
    candidate_population_digest: str
    population_digest: str | None
    query_fingerprint: AggregationQueryFingerprint
    reference_time: datetime
    knowledge_cutoff: datetime
    requested_at: datetime
    evaluated_at: datetime
    disclosure_state: DisclosureDecisionState
    decision_reason_codes: tuple[str, ...]
    outcome: MarketSupplyAuditOutcome
    external_disposition: MarketSupplyAuditExternalDisposition
    result_digest: str | None
    revocation_state: MarketSupplyRevocationState
    correlation_id: TypedId
    idempotency_reference: str
    semantic_request_digest: str
    grant_id: UUID | None = None

    def __post_init__(self) -> None:
        if self.audit_id.entity_type != "market_supply_query_audit":
            raise ValueError("audit_id deve ter entity_type 'market_supply_query_audit'.")
        if self.policy_id.entity_type != "policy":
            raise ValueError("policy_id deve ter entity_type 'policy'.")
        if self.correlation_id.entity_type != "correlation":
            raise ValueError("correlation_id deve ter entity_type 'correlation'.")
        for field_name in (
            "access_purpose",
            "authorization_context_digest",
            "privacy_profile_id",
            "candidate_population_digest",
            "idempotency_reference",
            "semantic_request_digest",
        ):
            if not getattr(self, field_name).strip():
                raise ValueError(f"{field_name} deve ser texto nao vazio.")
        if self.policy_version < 1:
            raise ValueError("policy_version deve ser inteiro >= 1.")
        if self.privacy_profile_version < 1:
            raise ValueError("privacy_profile_version deve ser inteiro >= 1.")
        if self.population_digest is not None and not self.population_digest.strip():
            raise ValueError("population_digest deve ser texto nao vazio quando informado.")
        if not self.decision_reason_codes:
            raise ValueError("decision_reason_codes deve conter ao menos um codigo.")
        for reason in self.decision_reason_codes:
            if not reason.strip():
                raise ValueError("decision_reason_codes nao aceita valor vazio.")
        for field_name in (
            "reference_time",
            "knowledge_cutoff",
            "requested_at",
            "evaluated_at",
        ):
            require_utc(getattr(self, field_name), field_name=field_name)
        if self.query_fingerprint.requester_organization_id != self.requester_organization_id:
            raise ValueError("query_fingerprint requester diverge do audit record.")
        if self.query_fingerprint.beneficiary_organization_id != self.beneficiary_organization_id:
            raise ValueError("query_fingerprint beneficiary diverge do audit record.")
        if self.query_fingerprint.access_purpose != self.access_purpose:
            raise ValueError("query_fingerprint access_purpose diverge do audit record.")
        if self.outcome is MarketSupplyAuditOutcome.RELEASED:
            if (
                self.external_disposition
                is not MarketSupplyAuditExternalDisposition.RELEASE_AGGREGATE
            ):
                raise ValueError("resultado released exige external disposition RELEASE_AGGREGATE.")
            if not self.result_digest or not self.result_digest.strip():
                raise ValueError("resultado released exige result_digest.")
        elif (
            self.external_disposition
            is not MarketSupplyAuditExternalDisposition.UNIFORM_NOT_RELEASED
        ):
            raise ValueError("resultado nao liberado exige external disposition uniforme.")

    @classmethod
    def from_envelope(
        cls,
        *,
        audit_id: TypedId,
        envelope: MarketSupplyAggregateQueryAuditEnvelope,
        policy_version: int,
        privacy_profile_id: str,
        authorization_context_digest: str,
        candidate_population_digest: str,
        reference_time: datetime,
        knowledge_cutoff: datetime,
        requested_at: datetime,
        disclosure_decision: DisclosureDecision,
        result_digest: str | None,
        revocation_state: MarketSupplyRevocationState,
        correlation_id: TypedId,
        idempotency_reference: str,
        semantic_request_digest: str,
        population_digest: str | None = None,
    ) -> "MarketSupplyQueryAuditRecord":
        if disclosure_decision.query_fingerprint != envelope.query_fingerprint:
            raise ValueError("disclosure_decision query_fingerprint diverge do envelope.")
        if disclosure_decision.candidate_population_digest != candidate_population_digest:
            raise ValueError("disclosure_decision population digest diverge do audit record.")
        return cls(
            audit_id=audit_id,
            audit_owner_organization_id=envelope.audit_owner_organization_id,
            requester_organization_id=envelope.requester_organization_id,
            beneficiary_organization_id=envelope.beneficiary_organization_id,
            access_purpose=envelope.access_purpose,
            authorization_context_digest=authorization_context_digest,
            policy_id=envelope.policy_id,
            policy_version=policy_version,
            privacy_profile_id=privacy_profile_id,
            privacy_profile_version=disclosure_decision.privacy_policy_version,
            candidate_population_digest=candidate_population_digest,
            population_digest=population_digest,
            query_fingerprint=envelope.query_fingerprint,
            reference_time=reference_time,
            knowledge_cutoff=knowledge_cutoff,
            requested_at=requested_at,
            evaluated_at=disclosure_decision.evaluated_at,
            disclosure_state=disclosure_decision.state,
            decision_reason_codes=disclosure_decision.reason_codes,
            outcome=envelope.outcome,
            external_disposition=envelope.external_disposition,
            result_digest=result_digest,
            revocation_state=revocation_state,
            correlation_id=correlation_id,
            idempotency_reference=idempotency_reference,
            semantic_request_digest=semantic_request_digest,
            grant_id=envelope.grant_id,
        )

    def record_digest(self) -> str:
        return hashlib.sha256(
            _SERIALIZER.serialize(
                canonicalize_for_hash(
                    {
                        "schema": "titan.market_supply.query_audit_record",
                        "version": 1,
                        "audit_id": str(self.audit_id.value),
                        "audit_owner_organization_id": str(
                            self.audit_owner_organization_id.value,
                        ),
                        "requester_organization_id": str(
                            self.requester_organization_id.value,
                        ),
                        "beneficiary_organization_id": str(
                            self.beneficiary_organization_id.value,
                        ),
                        "access_purpose": self.access_purpose,
                        "authorization_context_digest": self.authorization_context_digest,
                        "policy_id": str(self.policy_id.value),
                        "policy_version": self.policy_version,
                        "privacy_profile_id": self.privacy_profile_id,
                        "privacy_profile_version": self.privacy_profile_version,
                        "candidate_population_digest": self.candidate_population_digest,
                        "population_digest": self.population_digest,
                        "query_fingerprint": _query_fingerprint_digest_input(
                            self.query_fingerprint,
                        ),
                        "reference_time": self.reference_time,
                        "knowledge_cutoff": self.knowledge_cutoff,
                        "requested_at": self.requested_at,
                        "evaluated_at": self.evaluated_at,
                        "disclosure_state": self.disclosure_state.value,
                        "decision_reason_codes": self.decision_reason_codes,
                        "outcome": self.outcome.value,
                        "external_disposition": self.external_disposition.value,
                        "result_digest": self.result_digest,
                        "revocation_state": self.revocation_state.value,
                        "correlation_id": str(self.correlation_id.value),
                        "idempotency_reference": self.idempotency_reference,
                        "semantic_request_digest": self.semantic_request_digest,
                        "grant_id": None if self.grant_id is None else str(self.grant_id),
                    },
                ),
            ),
        ).hexdigest()


class MarketSupplyQueryAuditRepositoryPort(Protocol):
    def append(self, record: MarketSupplyQueryAuditRecord) -> None: ...

    def get(self, audit_id: TypedId) -> MarketSupplyQueryAuditRecord | None: ...

    def find_related(
        self,
        *,
        requester_organization_id: OrganizationId,
        beneficiary_organization_id: OrganizationId,
        access_purpose: str,
        policy_context_digest: str,
    ) -> tuple[MarketSupplyQueryAuditRecord, ...]: ...

    def find_related_query_fingerprints(
        self,
        *,
        requester_organization_id: OrganizationId,
        beneficiary_organization_id: OrganizationId,
        access_purpose: str,
        policy_context_digest: str,
    ) -> tuple[AggregationQueryFingerprint, ...]: ...


class InMemoryMarketSupplyQueryAuditRepository:
    """Append-only in-memory implementation used by tests and future orchestration."""

    def __init__(self) -> None:
        self._records: dict[TypedId, MarketSupplyQueryAuditRecord] = {}
        self._order: list[TypedId] = []

    def append(self, record: MarketSupplyQueryAuditRecord) -> None:
        if record.audit_id in self._records:
            raise ValueError("Market Supply audit record ja existe; append-only violado.")
        self._records[record.audit_id] = record
        self._order.append(record.audit_id)

    def get(self, audit_id: TypedId) -> MarketSupplyQueryAuditRecord | None:
        return self._records.get(audit_id)

    def find_related(
        self,
        *,
        requester_organization_id: OrganizationId,
        beneficiary_organization_id: OrganizationId,
        access_purpose: str,
        policy_context_digest: str,
    ) -> tuple[MarketSupplyQueryAuditRecord, ...]:
        return tuple(
            record
            for audit_id in self._order
            for record in (self._records[audit_id],)
            if record.requester_organization_id == requester_organization_id
            and record.beneficiary_organization_id == beneficiary_organization_id
            and record.access_purpose == access_purpose
            and record.query_fingerprint.policy_context_digest == policy_context_digest
        )

    def find_related_query_fingerprints(
        self,
        *,
        requester_organization_id: OrganizationId,
        beneficiary_organization_id: OrganizationId,
        access_purpose: str,
        policy_context_digest: str,
    ) -> tuple[AggregationQueryFingerprint, ...]:
        return tuple(
            record.query_fingerprint
            for record in self.find_related(
                requester_organization_id=requester_organization_id,
                beneficiary_organization_id=beneficiary_organization_id,
                access_purpose=access_purpose,
                policy_context_digest=policy_context_digest,
            )
        )


def _query_fingerprint_digest_input(
    fingerprint: AggregationQueryFingerprint,
) -> dict[str, object]:
    return {
        "requester_organization_id": str(fingerprint.requester_organization_id.value),
        "beneficiary_organization_id": str(fingerprint.beneficiary_organization_id.value),
        "access_purpose": fingerprint.access_purpose,
        "policy_context_digest": fingerprint.policy_context_digest,
        "filter_fingerprint": fingerprint.filter_fingerprint,
        "result_subject_count": fingerprint.result_subject_count,
        "requested_at": fingerprint.requested_at,
    }


def _authorization_outcome(
    reason: MarketSupplyAuthorizationReason,
) -> MarketSupplyAuditOutcome:
    if reason is MarketSupplyAuthorizationReason.PURPOSE_MISMATCH:
        return MarketSupplyAuditOutcome.PURPOSE_MISMATCH
    if reason is MarketSupplyAuthorizationReason.REVOKED_GRANT:
        return MarketSupplyAuditOutcome.GRANT_REVOKED
    return MarketSupplyAuditOutcome.DENIED_BY_AUTHORIZATION
