"""Testes de aplicacao para governanca de regras (ADR-0043)."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from packages.core_application.rule_governance_service import RuleGovernanceService
from packages.core_domain.rule import ComparisonOperator, Rule, RuleCondition, SeverityLevel
from packages.core_domain.rule_governance import (
    RuleIdentity,
    RuleSourceType,
    RuleTimelineEvent,
    RuleTimelineEventType,
)
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference


@dataclass
class InMemoryRuleIdentityRepository:
    identities: dict[tuple[OrganizationId, str], RuleIdentity] = field(default_factory=dict)
    by_id: dict[TypedId, RuleIdentity] = field(default_factory=dict)

    def save(self, identity: RuleIdentity) -> None:
        self.identities[(identity.organization_id, identity.code)] = identity
        self.by_id[identity.rule_identity_id] = identity

    def get_by_id(self, rule_identity_id: TypedId) -> RuleIdentity | None:
        return self.by_id.get(rule_identity_id)

    def get_by_organization_and_code(
        self, organization_id: OrganizationId, code: str
    ) -> RuleIdentity | None:
        return self.identities.get((organization_id, code))


@dataclass
class InMemoryRuleTimelineRepository:
    events: list[RuleTimelineEvent] = field(default_factory=list)

    def append(self, event: RuleTimelineEvent) -> None:
        self.events.append(event)


@dataclass
class InMemoryRuleVersionRepository:
    rules: dict[tuple[OrganizationId, TypedId, str, int], Rule] = field(default_factory=dict)

    def save(self, rule: Rule) -> None:
        self.rules[(rule.organization_id, rule.policy_id, rule.code, rule.version)] = rule

    def get_by_policy_code_and_version(
        self,
        organization_id: OrganizationId,
        policy_id: TypedId,
        code: str,
        version: int,
    ) -> Rule | None:
        return self.rules.get((organization_id, policy_id, code, version))


def _actor(org_id: OrganizationId) -> UniversalReference:
    return UniversalReference(
        target_id=TypedId(entity_type="actor", value=uuid4()),
        organization_id=org_id,
        contract_version=1,
    )


def test_create_rule_identity_records_initial_timeline_event() -> None:
    org_id = OrganizationId.new()
    identities = InMemoryRuleIdentityRepository()
    timeline = InMemoryRuleTimelineRepository()
    service = RuleGovernanceService(identities=identities, timeline=timeline)
    actor = _actor(org_id)
    occurred_at = datetime(2026, 7, 26, tzinfo=UTC)

    identity = service.create_identity(
        organization_id=org_id,
        code=" Rule-Carencia-Farmacologica ",
        purpose="ELEGIBILIDADE_FARMACOLOGICA",
        scope="livestock.animal",
        source_type=RuleSourceType.INTERNAL_POLICY,
        actor=actor,
        vertical="Livestock",
        description="Regra propria do frigorifico.",
        occurred_at=occurred_at,
    )

    assert (
        identities.get_by_organization_and_code(org_id, "rule-carencia-farmacologica") == identity
    )
    assert len(timeline.events) == 1
    event = timeline.events[0]
    assert event.event_type is RuleTimelineEventType.RULE_IDENTITY_CREATED
    assert event.rule_identity_id == identity.rule_identity_id
    assert event.actor == actor
    assert event.occurred_at == occurred_at


def test_create_rule_identity_rejects_duplicate_code_in_same_organization() -> None:
    org_id = OrganizationId.new()
    service = RuleGovernanceService(
        identities=InMemoryRuleIdentityRepository(),
        timeline=InMemoryRuleTimelineRepository(),
    )
    actor = _actor(org_id)

    service.create_identity(
        organization_id=org_id,
        code="rule-carencia",
        purpose="ELEGIBILIDADE",
        scope="livestock.animal",
        source_type=RuleSourceType.INTERNAL_POLICY,
        actor=actor,
    )

    with pytest.raises(ValueError, match="Ja existe uma identidade de regra"):
        service.create_identity(
            organization_id=org_id,
            code=" RULE-CARENCIA ",
            purpose="ELEGIBILIDADE",
            scope="livestock.animal",
            source_type=RuleSourceType.INTERNAL_POLICY,
            actor=actor,
        )


def test_same_rule_code_can_exist_in_different_organizations() -> None:
    org_a = OrganizationId.new()
    org_b = OrganizationId.new()
    identities = InMemoryRuleIdentityRepository()
    service = RuleGovernanceService(
        identities=identities,
        timeline=InMemoryRuleTimelineRepository(),
    )

    rule_a = service.create_identity(
        organization_id=org_a,
        code="rule-carencia",
        purpose="ELEGIBILIDADE",
        scope="livestock.animal",
        source_type=RuleSourceType.INTERNAL_POLICY,
        actor=_actor(org_a),
    )
    rule_b = service.create_identity(
        organization_id=org_b,
        code="rule-carencia",
        purpose="ELEGIBILIDADE",
        scope="livestock.animal",
        source_type=RuleSourceType.INTERNAL_POLICY,
        actor=_actor(org_b),
    )

    assert rule_a.rule_identity_id != rule_b.rule_identity_id
    assert len(identities.identities) == 2


def test_publish_rule_version_uses_identity_code_and_records_timeline() -> None:
    org_id = OrganizationId.new()
    identities = InMemoryRuleIdentityRepository()
    timeline = InMemoryRuleTimelineRepository()
    rules = InMemoryRuleVersionRepository()
    service = RuleGovernanceService(identities=identities, timeline=timeline, rules=rules)
    actor = _actor(org_id)
    identity = service.create_identity(
        organization_id=org_id,
        code="rule-carencia",
        purpose="ELEGIBILIDADE",
        scope="livestock.animal",
        source_type=RuleSourceType.INTERNAL_POLICY,
        actor=actor,
    )
    policy_id = TypedId.new("policy")
    condition = RuleCondition(
        fact_type="livestock.withdrawal",
        payload_key="in_withdrawal",
        operator=ComparisonOperator.EQUALS,
        expected_value=False,
    )

    rule = service.publish_rule_version(
        organization_id=org_id,
        rule_identity_id=identity.rule_identity_id,
        policy_id=policy_id,
        name="Carencia farmacologica",
        actor=actor,
        severity=SeverityLevel.BLOCKING,
        conditions=(condition,),
    )

    assert rule.code == identity.code
    assert rule.policy_id == policy_id
    assert rule.version == 1
    assert rules.get_by_policy_code_and_version(org_id, policy_id, identity.code, 1) == rule
    assert [event.event_type for event in timeline.events] == [
        RuleTimelineEventType.RULE_IDENTITY_CREATED,
        RuleTimelineEventType.RULE_VERSION_DRAFTED,
        RuleTimelineEventType.RULE_VERSION_PUBLISHED,
    ]
    assert timeline.events[-1].rule_version_id == rule.rule_id


def test_publish_rule_version_rejects_duplicate_version_for_policy() -> None:
    org_id = OrganizationId.new()
    service = RuleGovernanceService(
        identities=InMemoryRuleIdentityRepository(),
        timeline=InMemoryRuleTimelineRepository(),
        rules=InMemoryRuleVersionRepository(),
    )
    actor = _actor(org_id)
    identity = service.create_identity(
        organization_id=org_id,
        code="rule-carencia",
        purpose="ELEGIBILIDADE",
        scope="livestock.animal",
        source_type=RuleSourceType.INTERNAL_POLICY,
        actor=actor,
    )
    policy_id = TypedId.new("policy")
    service.publish_rule_version(
        organization_id=org_id,
        rule_identity_id=identity.rule_identity_id,
        policy_id=policy_id,
        name="Carencia farmacologica",
        actor=actor,
    )

    with pytest.raises(ValueError, match="Ja existe uma versao publicada"):
        service.publish_rule_version(
            organization_id=org_id,
            rule_identity_id=identity.rule_identity_id,
            policy_id=policy_id,
            name="Carencia farmacologica v1 duplicada",
            actor=actor,
        )
