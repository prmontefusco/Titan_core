"""Testes da derivacao pura de origem de Policy (ADR-0064, BuyerPolicy Fase 1)."""

from dataclasses import dataclass, field
from uuid import uuid4

from packages.core_application.policy_origin import (
    is_buyer_policy_origin,
    resolve_policy_origin,
)
from packages.core_domain.rule import Rule
from packages.core_domain.rule_governance import RuleIdentity, RuleSourceType
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference


@dataclass
class InMemoryRuleIdentityLookup:
    identities: dict[tuple[OrganizationId, str], RuleIdentity] = field(default_factory=dict)

    def add(self, identity: RuleIdentity) -> None:
        self.identities[(identity.organization_id, identity.code)] = identity

    def get_by_organization_and_code(
        self, organization_id: OrganizationId, code: str
    ) -> RuleIdentity | None:
        return self.identities.get((organization_id, code))


def _actor(org_id: OrganizationId) -> UniversalReference:
    return UniversalReference(
        target_id=TypedId(entity_type="actor", value=uuid4()),
        organization_id=org_id,
        contract_version=1,
    )


def _identity(org_id: OrganizationId, code: str, source_type: RuleSourceType) -> RuleIdentity:
    return RuleIdentity.create(
        organization_id=org_id,
        code=code,
        purpose="COMPRA",
        scope="livestock.animal",
        source_type=source_type,
        created_by=_actor(org_id),
    )


def _rule(org_id: OrganizationId, policy_id: TypedId, code: str) -> Rule:
    return Rule.create(
        policy_id=policy_id,
        organization_id=org_id,
        code=code,
        name=f"Regra {code}",
    )


def test_resolve_policy_origin_is_none_for_empty_policy() -> None:
    org_id = OrganizationId.new()
    origin = resolve_policy_origin(org_id, [], InMemoryRuleIdentityLookup())

    assert origin.homogeneous is False
    assert origin.source_type is None


def test_resolve_policy_origin_finds_shared_internal_policy_source_type() -> None:
    org_id = OrganizationId.new()
    policy_id = TypedId.new("policy")
    lookup = InMemoryRuleIdentityLookup()
    lookup.add(_identity(org_id, "rule-a", RuleSourceType.INTERNAL_POLICY))
    lookup.add(_identity(org_id, "rule-b", RuleSourceType.INTERNAL_POLICY))
    rules = [_rule(org_id, policy_id, "rule-a"), _rule(org_id, policy_id, "rule-b")]

    origin = resolve_policy_origin(org_id, rules, lookup)

    assert origin.homogeneous is True
    assert origin.source_type is RuleSourceType.INTERNAL_POLICY
    assert is_buyer_policy_origin(origin) is True


def test_resolve_policy_origin_rejects_heterogeneous_source_types() -> None:
    org_id = OrganizationId.new()
    policy_id = TypedId.new("policy")
    lookup = InMemoryRuleIdentityLookup()
    lookup.add(_identity(org_id, "rule-interna", RuleSourceType.INTERNAL_POLICY))
    lookup.add(_identity(org_id, "rule-lei", RuleSourceType.LAW))
    rules = [_rule(org_id, policy_id, "rule-interna"), _rule(org_id, policy_id, "rule-lei")]

    origin = resolve_policy_origin(org_id, rules, lookup)

    assert origin.homogeneous is False
    assert origin.source_type is None
    assert is_buyer_policy_origin(origin) is False


def test_resolve_policy_origin_treats_missing_identity_as_non_homogeneous() -> None:
    org_id = OrganizationId.new()
    policy_id = TypedId.new("policy")
    lookup = InMemoryRuleIdentityLookup()
    rules = [_rule(org_id, policy_id, "rule-sem-identidade")]

    origin = resolve_policy_origin(org_id, rules, lookup)

    assert origin.homogeneous is False
    assert origin.missing_identity_codes == ("rule-sem-identidade",)


def test_is_buyer_policy_origin_rejects_non_internal_policy_source_type() -> None:
    org_id = OrganizationId.new()
    policy_id = TypedId.new("policy")
    lookup = InMemoryRuleIdentityLookup()
    lookup.add(_identity(org_id, "rule-contrato", RuleSourceType.CONTRACT))
    rules = [_rule(org_id, policy_id, "rule-contrato")]

    origin = resolve_policy_origin(org_id, rules, lookup)

    assert origin.homogeneous is True
    assert origin.source_type is RuleSourceType.CONTRACT
    assert is_buyer_policy_origin(origin) is False
