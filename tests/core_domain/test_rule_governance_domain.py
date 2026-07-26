"""Testes do dominio de governanca de regras (ADR-0043)."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from packages.core_domain.rule_governance import (
    RuleIdentity,
    RuleSourceType,
    RuleTimelineEvent,
    RuleTimelineEventType,
)
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference


def _actor(org_id: OrganizationId) -> UniversalReference:
    return UniversalReference(
        target_id=TypedId(entity_type="actor", value=uuid4()),
        organization_id=org_id,
        contract_version=1,
    )


def test_rule_identity_preserves_stable_identity_for_versions() -> None:
    org_id = OrganizationId.new()
    actor = _actor(org_id)

    identity = RuleIdentity.create(
        organization_id=org_id,
        code=" Rule-Carencia-Farmacologica ",
        purpose="ELEGIBILIDADE_FARMACOLOGICA",
        scope="livestock.animal",
        source_type=RuleSourceType.INTERNAL_POLICY,
        created_by=actor,
        vertical="Livestock",
        description="Regra operacional do frigorifico.",
    )

    assert identity.rule_identity_id.entity_type == "rule_identity"
    assert identity.organization_id == org_id
    assert identity.code == "rule-carencia-farmacologica"
    assert identity.vertical == "livestock"
    assert identity.created_by == actor


def test_rule_identity_rejects_missing_governance_fields() -> None:
    org_id = OrganizationId.new()

    with pytest.raises(ValueError, match="purpose deve ser uma string nao vazia"):
        RuleIdentity.create(
            organization_id=org_id,
            code="rule-carencia",
            purpose=" ",
            scope="livestock.animal",
            source_type=RuleSourceType.INTERNAL_POLICY,
            created_by=_actor(org_id),
        )


def test_rule_timeline_event_records_version_lifecycle() -> None:
    org_id = OrganizationId.new()
    actor = _actor(org_id)
    rule_identity_id = TypedId.new("rule_identity")
    rule_version_id = TypedId.new("rule")
    occurred_at = datetime(2026, 7, 26, tzinfo=UTC)

    event = RuleTimelineEvent.record(
        organization_id=org_id,
        rule_identity_id=rule_identity_id,
        event_type=RuleTimelineEventType.RULE_VERSION_PUBLISHED,
        actor=actor,
        rule_version_id=rule_version_id,
        occurred_at=occurred_at,
    )

    assert event.event_id.entity_type == "rule_timeline_event"
    assert event.rule_identity_id == rule_identity_id
    assert event.rule_version_id == rule_version_id
    assert event.event_type is RuleTimelineEventType.RULE_VERSION_PUBLISHED
    assert event.occurred_at == occurred_at


def test_rule_timeline_version_event_requires_rule_version() -> None:
    org_id = OrganizationId.new()

    with pytest.raises(ValueError, match="rule_version_published exige rule_version_id"):
        RuleTimelineEvent.record(
            organization_id=org_id,
            rule_identity_id=TypedId.new("rule_identity"),
            event_type=RuleTimelineEventType.RULE_VERSION_PUBLISHED,
            actor=_actor(org_id),
        )


def test_rule_timeline_destructive_event_requires_reason() -> None:
    org_id = OrganizationId.new()

    with pytest.raises(ValueError, match="rule_version_revoked exige reason explicita"):
        RuleTimelineEvent.record(
            organization_id=org_id,
            rule_identity_id=TypedId.new("rule_identity"),
            event_type=RuleTimelineEventType.RULE_VERSION_REVOKED,
            actor=_actor(org_id),
            rule_version_id=TypedId.new("rule"),
        )
