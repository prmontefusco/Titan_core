"""Testes do dominio de governanca de regras (ADR-0043)."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from packages.core_domain.rule_governance import (
    RuleAdoption,
    RuleAdoptionStatus,
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


def test_rule_adoption_links_identity_version_and_operational_scope() -> None:
    org_id = OrganizationId.new()
    identity_id = TypedId.new("rule_identity")
    rule_id = TypedId.new("rule")
    actor = _actor(org_id)

    adoption = RuleAdoption.adopt(
        organization_id=org_id,
        rule_identity_id=identity_id,
        rule_version_id=rule_id,
        purpose="compra-abate",
        scope="fornecedores-diretos",
        adopted_by=actor,
        reason="Politica comercial vigente.",
    )

    assert adoption.adoption_id.entity_type == "rule_adoption"
    assert adoption.rule_identity_id == identity_id
    assert adoption.rule_version_id == rule_id
    assert adoption.status is RuleAdoptionStatus.ACTIVE
    assert adoption.adopted_by == actor


def test_rule_adoption_can_be_superseded_without_losing_identity() -> None:
    org_id = OrganizationId.new()
    actor = _actor(org_id)
    adoption = RuleAdoption.adopt(
        organization_id=org_id,
        rule_identity_id=TypedId.new("rule_identity"),
        rule_version_id=TypedId.new("rule"),
        purpose="compra-abate",
        scope="fornecedores-diretos",
        adopted_by=actor,
        reason="Versao inicial.",
    )

    superseded = adoption.supersede(
        adopted_by=actor,
        reason="Norma interna revisada.",
        adopted_at=datetime(2026, 7, 27, tzinfo=UTC),
    )

    assert superseded.adoption_id == adoption.adoption_id
    assert superseded.rule_identity_id == adoption.rule_identity_id
    assert superseded.status is RuleAdoptionStatus.SUPERSEDED
    assert superseded.reason == "Norma interna revisada."


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
