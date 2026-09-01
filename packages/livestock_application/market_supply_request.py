"""Semantic request identity for Market Supply operations."""

import hashlib
from binascii import unhexlify
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from packages.core_application.idempotency import (
    IdempotencyExecution,
    IdempotencyRequest,
    IdempotencyService,
)
from packages.core_domain import CanonicalPayload
from packages.shared_kernel import (
    CanonicalSerializer,
    OrganizationId,
    TypedId,
    UniversalReference,
    canonicalize_for_hash,
)
from packages.shared_kernel.temporal import require_utc

_SERIALIZER = CanonicalSerializer()

MARKET_SUPPLY_AGGREGATE_ASSESSMENT_OPERATION = "livestock.market_supply.aggregate_assessment"


@dataclass(frozen=True, slots=True)
class CommercialDemandContext:
    """Transient commercial intent context for Market Supply F3.

    This is not Policy, Evidence, Evaluation, Decision or a persisted aggregate.
    It only contributes commercial coordinates to the semantic request digest.
    """

    buyer_organization_id: OrganizationId
    purpose: str
    policy_id: TypedId
    policy_version: int
    requested_quantity: int
    commercial_window_from: datetime
    commercial_window_until: datetime

    def __post_init__(self) -> None:
        if not self.purpose.strip():
            raise ValueError("purpose deve ser texto nao vazio.")
        if self.policy_id.entity_type != "policy":
            raise ValueError("policy_id deve ter entity_type 'policy'.")
        if self.policy_version < 1:
            raise ValueError("policy_version deve ser inteiro >= 1.")
        if self.requested_quantity < 1:
            raise ValueError("requested_quantity deve ser inteiro >= 1.")
        require_utc(self.commercial_window_from, field_name="commercial_window_from")
        require_utc(self.commercial_window_until, field_name="commercial_window_until")
        if self.commercial_window_until <= self.commercial_window_from:
            raise ValueError("commercial_window_until deve ser posterior a commercial_window_from.")

    def demand_context_digest(self) -> str:
        return hashlib.sha256(
            _SERIALIZER.serialize(
                canonicalize_for_hash(
                    {
                        "schema": "titan.market_supply.commercial_demand_context",
                        "version": 1,
                        "buyer_organization_id": str(self.buyer_organization_id.value),
                        "purpose": self.purpose,
                        "policy_id": str(self.policy_id.value),
                        "policy_version": self.policy_version,
                        "requested_quantity": self.requested_quantity,
                        "commercial_window_from": self.commercial_window_from,
                        "commercial_window_until": self.commercial_window_until,
                    },
                ),
            ),
        ).hexdigest()

    def to_request_identity(
        self,
        *,
        candidate_criteria_digest: str,
        reference_time: datetime,
        knowledge_cutoff: datetime,
        idempotency_key: str,
    ) -> "MarketSupplyRequestIdentity":
        return MarketSupplyRequestIdentity(
            buyer_organization_id=self.buyer_organization_id,
            purpose=self.purpose,
            policy_id=self.policy_id,
            policy_version=self.policy_version,
            demand_context_digest=self.demand_context_digest(),
            candidate_criteria_digest=candidate_criteria_digest,
            reference_time=reference_time,
            knowledge_cutoff=knowledge_cutoff,
            idempotency_key=idempotency_key,
        )


@dataclass(frozen=True, slots=True)
class MarketSupplyRequestIdentity:
    """Canonical identity for Market Supply idempotency.

    The idempotency key is not enough on its own. It is bound to the semantic
    request coordinates so a repeated key with changed meaning can be rejected
    before population resolution or disclosure.
    """

    buyer_organization_id: OrganizationId
    purpose: str
    policy_id: TypedId
    policy_version: int
    demand_context_digest: str
    candidate_criteria_digest: str
    reference_time: datetime
    knowledge_cutoff: datetime
    idempotency_key: str

    def __post_init__(self) -> None:
        if not self.purpose.strip():
            raise ValueError("purpose deve ser texto nao vazio.")
        if self.policy_id.entity_type != "policy":
            raise ValueError("policy_id deve ter entity_type 'policy'.")
        if self.policy_version < 1:
            raise ValueError("policy_version deve ser inteiro >= 1.")
        if not self.demand_context_digest.strip():
            raise ValueError("demand_context_digest deve ser texto nao vazio.")
        if not self.candidate_criteria_digest.strip():
            raise ValueError("candidate_criteria_digest deve ser texto nao vazio.")
        if not self.idempotency_key.strip():
            raise ValueError("idempotency_key deve ser texto nao vazio.")
        require_utc(self.reference_time, field_name="reference_time")
        require_utc(self.knowledge_cutoff, field_name="knowledge_cutoff")

    def semantic_digest(self) -> str:
        return hashlib.sha256(
            _SERIALIZER.serialize(
                canonicalize_for_hash(
                    {
                        "schema": "titan.market_supply.request_identity",
                        "version": 1,
                        "buyer_organization_id": str(self.buyer_organization_id.value),
                        "purpose": self.purpose,
                        "policy_id": str(self.policy_id.value),
                        "policy_version": self.policy_version,
                        "demand_context_digest": self.demand_context_digest,
                        "candidate_criteria_digest": self.candidate_criteria_digest,
                        "reference_time": self.reference_time,
                        "knowledge_cutoff": self.knowledge_cutoff,
                        "idempotency_key": self.idempotency_key,
                    },
                ),
            ),
        ).hexdigest()

    def to_idempotency_request(
        self,
        *,
        principal_reference: UniversalReference,
        requested_at: datetime,
        operation: str = MARKET_SUPPLY_AGGREGATE_ASSESSMENT_OPERATION,
    ) -> IdempotencyRequest:
        return IdempotencyRequest(
            key=self.idempotency_key,
            organization_id=self.buyer_organization_id,
            principal_reference=principal_reference,
            purpose=self.purpose,
            operation=operation,
            intent_digest=unhexlify(self.semantic_digest()),
            requested_at=requested_at,
        )


@dataclass(frozen=True, slots=True)
class MarketSupplyIdempotencyGate:
    """Market Supply adapter over the authoritative Core idempotency service."""

    service: IdempotencyService

    def execute(
        self,
        *,
        identity: MarketSupplyRequestIdentity,
        principal_reference: UniversalReference,
        requested_at: datetime,
        handler: Callable[[], CanonicalPayload],
    ) -> IdempotencyExecution:
        return self.service.execute(
            identity.to_idempotency_request(
                principal_reference=principal_reference,
                requested_at=requested_at,
            ),
            handler,
        )
