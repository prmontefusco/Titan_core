"""Prova temporal do catálogo sintético MARKET_TEST_A (ADR-0061)."""

from dataclasses import dataclass, field
from datetime import UTC, datetime

from packages.core_domain.policy import Policy, PolicyStatus
from packages.core_domain.rule import Rule, SeverityLevel
from packages.livestock_application.internal_test_normative_basis import (
    MARKET_TEST_A_CODE,
    MARKET_TEST_A_PURPOSE,
    InternalTestNormativeBasis,
    PersistedInternalTestNormativeBasisSnapshotProvider,
)
from packages.shared_kernel import OrganizationId, TypedId

T0 = datetime(2026, 1, 1, tzinfo=UTC)
T1 = datetime(2026, 7, 1, tzinfo=UTC)


@dataclass
class InMemoryCatalog:
    items: list[InternalTestNormativeBasis] = field(default_factory=list)

    def save(self, item: InternalTestNormativeBasis) -> None:
        self.items.append(item)

    def list_by_policy(
        self, organization_id: OrganizationId, policy_id: TypedId
    ) -> list[InternalTestNormativeBasis]:
        return [
            item
            for item in self.items
            if item.organization_id == organization_id and item.policy_id == policy_id
        ]


def _policy(org: OrganizationId, *, version: int = 1) -> Policy:
    return Policy(
        policy_id=TypedId.new("policy"),
        organization_id=org,
        code=MARKET_TEST_A_CODE,
        name="Mercado sintético A",
        description="Somente para testes internos.",
        version=version,
        status=PolicyStatus.PUBLISHED,
        valid_from=T0 if version == 1 else T1,
        valid_to=T1 if version == 1 else None,
        published_at=T0,
    )


def _rule(policy: Policy) -> Rule:
    return Rule(
        rule_id=TypedId.new("rule"),
        policy_id=policy.policy_id,
        organization_id=policy.organization_id,
        code="market-test-a-rule",
        name="Regra sintética",
        description="Não representa requisito externo.",
        severity=SeverityLevel.BLOCKING,
        normative_source="material interno sintético",
    )


def _basis(
    policy: Policy, *, version: int = 1, known_at: datetime = T0
) -> InternalTestNormativeBasis:
    return InternalTestNormativeBasis(
        normative_basis_id=TypedId.new("normative_basis"),
        organization_id=policy.organization_id,
        code="TEST-BASIS-A",
        version=version,
        policy_id=policy.policy_id,
        policy_code=policy.code,
        policy_version=policy.version,
        purpose=MARKET_TEST_A_PURPOSE,
        valid_from=policy.valid_from or T0,
        valid_until=policy.valid_to,
        known_at=known_at,
        approved_by="SYSTEM:INTERNAL_TEST_CATALOG",
        approved_at=T0,
        instrument_code="TEST-BASIS-A",
        instrument_version=str(version),
        provision="synthetic-market-test",
        content_digest=("a" if version == 1 else "b") * 64,
        limitations=("SYNTHETIC_MATERIAL",),
    )


def test_selects_exactly_one_known_basis_and_builds_internal_snapshot() -> None:
    org = OrganizationId.new()
    policy = _policy(org)
    rule = _rule(policy)
    catalog = InMemoryCatalog()
    catalog.save(_basis(policy))

    snapshot = PersistedInternalTestNormativeBasisSnapshotProvider(catalog).select(
        policy=policy,
        rules=(rule,),
        purpose=MARKET_TEST_A_PURPOSE,
        reference_time=datetime(2026, 5, 1, tzinfo=UTC),
        knowledge_cutoff=datetime(2026, 5, 1, tzinfo=UTC),
    )

    assert snapshot is not None
    assert snapshot.normative_basis_code == "TEST-BASIS-A"
    assert snapshot.references[0].source_classification.value == "internal_test"
    assert "RECOGNITION_BOUNDARY:INTERNAL_ONLY" in snapshot.limitations
    assert "MARKET_ELIGIBILITY_ASSESSMENT_NOT_EXPORT_AUTHORIZATION" in snapshot.limitations


def test_known_later_or_ambiguous_basis_fails_closed() -> None:
    org = OrganizationId.new()
    policy = _policy(org)
    rule = _rule(policy)
    catalog = InMemoryCatalog()
    provider = PersistedInternalTestNormativeBasisSnapshotProvider(catalog)
    catalog.save(_basis(policy, known_at=datetime(2026, 6, 1, tzinfo=UTC)))

    assert (
        provider.select(
            policy=policy,
            rules=(rule,),
            purpose=MARKET_TEST_A_PURPOSE,
            reference_time=datetime(2026, 5, 1, tzinfo=UTC),
            knowledge_cutoff=datetime(2026, 5, 1, tzinfo=UTC),
        )
        is None
    )

    catalog.save(_basis(policy, version=2, known_at=T0))
    assert (
        provider.select(
            policy=policy,
            rules=(rule,),
            purpose=MARKET_TEST_A_PURPOSE,
            reference_time=datetime(2026, 5, 1, tzinfo=UTC),
            knowledge_cutoff=datetime(2026, 6, 1, tzinfo=UTC),
        )
        is None
    )


def test_basis_interval_is_semiopen() -> None:
    org = OrganizationId.new()
    policy = _policy(org)
    basis = _basis(policy)

    assert basis.applies_at(datetime(2026, 6, 30, 23, 59, tzinfo=UTC))
    assert not basis.applies_at(T1)
