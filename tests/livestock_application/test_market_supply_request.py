from datetime import UTC, datetime, timedelta

import pytest

from packages.core_application import IdempotencyConflict, IdempotencyService
from packages.core_application.idempotency import IdempotencyRequest, StoredIdempotencyResult
from packages.core_domain import CanonicalPayload
from packages.livestock_application.market_supply_request import (
    MARKET_SUPPLY_AGGREGATE_ASSESSMENT_OPERATION,
    CommercialDemandContext,
    MarketSupplyIdempotencyGate,
    MarketSupplyRequestIdentity,
)
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)
WINDOW_FROM = datetime(2026, 9, 1, 0, 0, tzinfo=UTC)
WINDOW_UNTIL = datetime(2026, 10, 15, 0, 0, tzinfo=UTC)


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


def _identity(
    *,
    reference_time: datetime = NOW,
    knowledge_cutoff: datetime = NOW,
    idempotency_key: str = "market-supply-key-1",
    buyer_organization_id: OrganizationId | None = None,
) -> MarketSupplyRequestIdentity:
    return MarketSupplyRequestIdentity(
        buyer_organization_id=buyer_organization_id or OrganizationId.new(),
        purpose="MARKET_SUPPLY_AGGREGATE_ASSESSMENT",
        policy_id=TypedId.new("policy"),
        policy_version=1,
        demand_context_digest="demand:sha256:abc",
        candidate_criteria_digest="criteria:sha256:def",
        reference_time=reference_time,
        knowledge_cutoff=knowledge_cutoff,
        idempotency_key=idempotency_key,
    )


def _demand_context(
    *,
    buyer_organization_id: OrganizationId | None = None,
    policy_id: TypedId | None = None,
    requested_quantity: int = 8000,
    commercial_window_from: datetime = WINDOW_FROM,
    commercial_window_until: datetime = WINDOW_UNTIL,
) -> CommercialDemandContext:
    return CommercialDemandContext(
        buyer_organization_id=buyer_organization_id or OrganizationId.new(),
        purpose="MARKET_SUPPLY_AGGREGATE_ASSESSMENT",
        policy_id=policy_id or TypedId.new("policy"),
        policy_version=1,
        requested_quantity=requested_quantity,
        commercial_window_from=commercial_window_from,
        commercial_window_until=commercial_window_until,
    )


def test_commercial_demand_context_digest_is_stable_and_contextual() -> None:
    buyer_organization_id = OrganizationId.new()
    policy_id = TypedId.new("policy")
    original = _demand_context(
        buyer_organization_id=buyer_organization_id,
        policy_id=policy_id,
    )
    same = _demand_context(
        buyer_organization_id=buyer_organization_id,
        policy_id=policy_id,
    )
    changed_quantity = _demand_context(
        buyer_organization_id=buyer_organization_id,
        policy_id=policy_id,
        requested_quantity=7000,
    )

    assert same.demand_context_digest() == original.demand_context_digest()
    assert changed_quantity.demand_context_digest() != original.demand_context_digest()


def test_commercial_demand_context_rejects_invalid_quantity_and_window() -> None:
    with pytest.raises(ValueError, match="requested_quantity"):
        _demand_context(requested_quantity=0)

    with pytest.raises(ValueError, match="commercial_window_from"):
        _demand_context(commercial_window_from=datetime(2026, 9, 1, 0, 0))

    with pytest.raises(ValueError, match="commercial_window_until"):
        _demand_context(commercial_window_until=WINDOW_FROM)


def test_commercial_demand_context_builds_request_identity_without_persistence() -> None:
    buyer_organization_id = OrganizationId.new()
    policy_id = TypedId.new("policy")
    demand = _demand_context(
        buyer_organization_id=buyer_organization_id,
        policy_id=policy_id,
    )

    identity = demand.to_request_identity(
        candidate_criteria_digest="criteria:sha256:def",
        reference_time=NOW,
        knowledge_cutoff=NOW,
        idempotency_key="market-supply-key-from-demand",
    )

    assert identity.buyer_organization_id == buyer_organization_id
    assert identity.purpose == demand.purpose
    assert identity.policy_id == policy_id
    assert identity.policy_version == demand.policy_version
    assert identity.demand_context_digest == demand.demand_context_digest()
    assert identity.candidate_criteria_digest == "criteria:sha256:def"
    assert identity.reference_time == NOW
    assert identity.knowledge_cutoff == NOW


def test_semantic_digest_is_stable_for_same_market_supply_request_identity() -> None:
    identity = _identity()

    assert identity.semantic_digest() == identity.semantic_digest()


def test_same_idempotency_key_with_different_temporal_coordinates_is_distinct() -> None:
    original = _identity(idempotency_key="same-key")
    changed_reference_time = _identity(
        reference_time=NOW - timedelta(days=1),
        idempotency_key="same-key",
    )
    changed_knowledge_cutoff = _identity(
        knowledge_cutoff=NOW - timedelta(days=1),
        idempotency_key="same-key",
    )

    assert changed_reference_time.idempotency_key == original.idempotency_key
    assert changed_knowledge_cutoff.idempotency_key == original.idempotency_key
    assert changed_reference_time.semantic_digest() != original.semantic_digest()
    assert changed_knowledge_cutoff.semantic_digest() != original.semantic_digest()


def test_request_identity_requires_policy_and_utc_temporal_coordinates() -> None:
    with pytest.raises(ValueError, match="policy_id"):
        MarketSupplyRequestIdentity(
            buyer_organization_id=OrganizationId.new(),
            purpose="MARKET_SUPPLY_AGGREGATE_ASSESSMENT",
            policy_id=TypedId.new("animal"),
            policy_version=1,
            demand_context_digest="demand",
            candidate_criteria_digest="criteria",
            reference_time=NOW,
            knowledge_cutoff=NOW,
            idempotency_key="key",
        )

    with pytest.raises(ValueError, match="reference_time"):
        _identity(reference_time=datetime(2026, 8, 28, 12, 0))


def test_request_identity_builds_core_idempotency_request_with_semantic_digest() -> None:
    organization_id = OrganizationId.new()
    identity = _identity(
        buyer_organization_id=organization_id,
        idempotency_key="market-supply-key-2",
    )
    principal = UniversalReference(
        target_id=TypedId.new("user"),
        organization_id=organization_id,
        contract_version=1,
    )

    request = identity.to_idempotency_request(
        principal_reference=principal,
        requested_at=NOW,
    )

    assert request.key == identity.idempotency_key
    assert request.organization_id == organization_id
    assert request.principal_reference == principal
    assert request.purpose == "MARKET_SUPPLY_AGGREGATE_ASSESSMENT"
    assert request.operation == MARKET_SUPPLY_AGGREGATE_ASSESSMENT_OPERATION
    assert request.intent_digest == bytes.fromhex(identity.semantic_digest())
    assert len(request.intent_digest) == 32


def test_request_identity_rejects_idempotency_principal_from_another_organization() -> None:
    identity = _identity()
    principal = UniversalReference(
        target_id=TypedId.new("user"),
        organization_id=OrganizationId.new(),
        contract_version=1,
    )

    with pytest.raises(ValueError, match="principal"):
        identity.to_idempotency_request(
            principal_reference=principal,
            requested_at=NOW,
        )


def test_market_supply_idempotency_gate_replays_same_semantic_request() -> None:
    organization_id = OrganizationId.new()
    identity = _identity(
        buyer_organization_id=organization_id,
        idempotency_key="market-supply-replay-key",
    )
    principal = UniversalReference(
        target_id=TypedId.new("user"),
        organization_id=organization_id,
        contract_version=1,
    )
    gate = MarketSupplyIdempotencyGate(
        service=IdempotencyService(InMemoryMarketSupplyIdempotencyStore()),
    )
    calls = 0

    def handler() -> CanonicalPayload:
        nonlocal calls
        calls += 1
        return CanonicalPayload.from_mapping(
            schema="market_supply_public_response",
            version=1,
            value={"status": "NOT_RELEASED"},
        )

    first = gate.execute(
        identity=identity,
        principal_reference=principal,
        requested_at=NOW,
        handler=handler,
    )
    second = gate.execute(
        identity=identity,
        principal_reference=principal,
        requested_at=NOW,
        handler=handler,
    )

    assert calls == 1
    assert first.replayed is False
    assert second.replayed is True
    assert second.result_canonical_bytes == first.result_canonical_bytes


def test_market_supply_idempotency_gate_conflicts_on_changed_semantic_digest() -> None:
    organization_id = OrganizationId.new()
    original = _identity(
        buyer_organization_id=organization_id,
        idempotency_key="market-supply-conflict-key",
    )
    divergent = _identity(
        buyer_organization_id=organization_id,
        idempotency_key=original.idempotency_key,
        reference_time=NOW - timedelta(days=1),
    )
    principal = UniversalReference(
        target_id=TypedId.new("user"),
        organization_id=organization_id,
        contract_version=1,
    )
    gate = MarketSupplyIdempotencyGate(
        service=IdempotencyService(InMemoryMarketSupplyIdempotencyStore()),
    )

    gate.execute(
        identity=original,
        principal_reference=principal,
        requested_at=NOW,
        handler=lambda: CanonicalPayload.from_mapping(
            schema="market_supply_public_response",
            version=1,
            value={"status": "NOT_RELEASED"},
        ),
    )

    with pytest.raises(IdempotencyConflict, match="INTENCAO_DIVERGENTE"):
        gate.execute(
            identity=divergent,
            principal_reference=principal,
            requested_at=NOW,
            handler=lambda: CanonicalPayload.from_mapping(
                schema="market_supply_public_response",
                version=1,
                value={"status": "RELEASED"},
            ),
        )
