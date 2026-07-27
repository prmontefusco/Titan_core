"""Testes PostgreSQL com RLS para governanca de regras (ADR-0043)."""

import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import Connection, create_engine, text

from packages.core_application.policy_service import PolicyService
from packages.core_application.rule_governance_service import RuleGovernanceService
from packages.core_domain.rule import ComparisonOperator, RuleCondition
from packages.core_domain.rule_governance import (
    RuleAdoptionStatus,
    RuleSourceType,
    RuleTimelineEventType,
)
from packages.core_infrastructure.persistence.policy import TransactionalPolicyRepository
from packages.core_infrastructure.persistence.rule import TransactionalRuleRepository
from packages.core_infrastructure.persistence.rule_governance import (
    TransactionalRuleAdoptionRepository,
    TransactionalRuleIdentityRepository,
    TransactionalRuleTimelineRepository,
)
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference


def _actor(org_id: OrganizationId) -> UniversalReference:
    return UniversalReference(
        target_id=TypedId(entity_type="actor", value=uuid4()),
        organization_id=org_id,
        contract_version=1,
    )


def db_connection() -> Iterator[Connection]:
    db_url = os.getenv(
        "TITAN_DATABASE_URL",
        "postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan",
    )
    engine = create_engine(db_url, pool_pre_ping=True)
    with engine.connect() as conn:
        with conn.begin():
            yield conn


def test_rule_governance_persistence_and_rls() -> None:
    for connection in db_connection():
        org_1 = OrganizationId.new()
        org_2 = OrganizationId.new()
        connection.execute(
            text(
                """
                INSERT INTO core_identity.organizations (
                    organization_id,
                    record_owner_organization_id
                )
                VALUES
                    (:org_1, :org_1),
                    (:org_2, :org_2)
                """
            ),
            {"org_1": org_1.value, "org_2": org_2.value},
        )
        connection.execute(
            text("SELECT set_config('titan.organization_id', :org_id, true)"),
            {"org_id": str(org_1.value)},
        )

        identity_repository = TransactionalRuleIdentityRepository(connection)
        timeline_repository = TransactionalRuleTimelineRepository(connection)
        rule_repository = TransactionalRuleRepository(connection)
        adoption_repository = TransactionalRuleAdoptionRepository(connection)
        service = RuleGovernanceService(
            identities=identity_repository,
            timeline=timeline_repository,
            rules=rule_repository,
            adoptions=adoption_repository,
        )
        actor = _actor(org_1)
        occurred_at = datetime(2026, 7, 26, tzinfo=UTC)
        policy = PolicyService(repository=TransactionalPolicyRepository(connection)).create_draft(
            organization_id=org_1,
            code="pol-elegibilidade",
            name="Elegibilidade",
        )

        identity = service.create_identity(
            organization_id=org_1,
            code="rule-carencia-farmacologica",
            purpose="ELEGIBILIDADE_FARMACOLOGICA",
            scope="livestock.animal",
            source_type=RuleSourceType.INTERNAL_POLICY,
            actor=actor,
            vertical="livestock",
            description="Regra propria do frigorifico.",
            occurred_at=occurred_at,
        )

        reloaded = identity_repository.get_by_organization_and_code(
            org_1,
            "rule-carencia-farmacologica",
        )
        assert reloaded == identity

        events = timeline_repository.list_by_identity(org_1, identity.rule_identity_id)
        assert len(events) == 1
        assert events[0].event_type is RuleTimelineEventType.RULE_IDENTITY_CREATED
        assert events[0].actor == actor
        assert events[0].occurred_at == occurred_at

        rule = service.publish_rule_version(
            organization_id=org_1,
            rule_identity_id=identity.rule_identity_id,
            policy_id=policy.policy_id,
            name="Carencia farmacologica",
            actor=actor,
            conditions=(
                RuleCondition(
                    fact_type="livestock.withdrawal",
                    payload_key="in_withdrawal",
                    operator=ComparisonOperator.EQUALS,
                    expected_value=False,
                ),
            ),
            occurred_at=occurred_at + timedelta(seconds=1),
        )
        persisted_rule = rule_repository.get_by_id(rule.rule_id)
        assert persisted_rule == rule

        events = timeline_repository.list_by_identity(org_1, identity.rule_identity_id)
        assert events[0].event_type is RuleTimelineEventType.RULE_IDENTITY_CREATED
        version_events = {event.event_type: event for event in events[1:]}
        assert set(version_events) == {
            RuleTimelineEventType.RULE_VERSION_DRAFTED,
            RuleTimelineEventType.RULE_VERSION_PUBLISHED,
        }
        assert (
            version_events[RuleTimelineEventType.RULE_VERSION_PUBLISHED].rule_version_id
            == rule.rule_id
        )

        adoption = service.adopt_rule_version(
            organization_id=org_1,
            rule_identity_id=identity.rule_identity_id,
            rule_version_id=rule.rule_id,
            purpose="compra-abate",
            scope="fornecedores-diretos",
            reason="Politica do frigorifico.",
            actor=actor,
            occurred_at=occurred_at + timedelta(seconds=2),
        )
        persisted_adoption = adoption_repository.get_active_by_identity_and_scope(
            org_1,
            identity.rule_identity_id,
            "compra-abate",
            "fornecedores-diretos",
        )
        assert persisted_adoption == adoption
        persisted_by_purpose = adoption_repository.get_active_by_code_purpose_and_scope(
            org_1,
            "rule-carencia-farmacologica",
            "compra-abate",
            "fornecedores-diretos",
        )
        assert persisted_by_purpose == adoption
        events = timeline_repository.list_by_identity(org_1, identity.rule_identity_id)
        assert events[-1].event_type is RuleTimelineEventType.RULE_ADOPTED
        assert events[-1].rule_version_id == rule.rule_id

        revised_rule = rule.create_next_version(name="Carencia farmacologica revisada")
        rule_repository.save(revised_rule)
        replacement = service.replace_rule_adoption(
            organization_id=org_1,
            rule_identity_id=identity.rule_identity_id,
            current_adoption_id=adoption.adoption_id,
            new_rule_version_id=revised_rule.rule_id,
            actor=actor,
            reason="Norma interna revisada.",
            occurred_at=occurred_at + timedelta(seconds=3),
        )
        persisted_old = adoption_repository.get_by_id(adoption.adoption_id)
        assert persisted_old is not None
        assert persisted_old.status is RuleAdoptionStatus.SUPERSEDED
        assert (
            adoption_repository.get_active_by_identity_and_scope(
                org_1,
                identity.rule_identity_id,
                "compra-abate",
                "fornecedores-diretos",
            )
            == replacement
        )
        events = timeline_repository.list_by_identity(org_1, identity.rule_identity_id)
        assert events[-1].event_type is RuleTimelineEventType.RULE_ADOPTION_CHANGED
        assert events[-1].rule_version_id == revised_rule.rule_id

        connection.execute(
            text("SELECT set_config('titan.organization_id', :org_id, true)"),
            {"org_id": str(org_2.value)},
        )

        org_2_identity_repository = TransactionalRuleIdentityRepository(connection)
        org_2_timeline_repository = TransactionalRuleTimelineRepository(connection)
        org_2_adoption_repository = TransactionalRuleAdoptionRepository(connection)
        assert (
            org_2_identity_repository.get_by_organization_and_code(
                org_2,
                "rule-carencia-farmacologica",
            )
            is None
        )
        assert org_2_timeline_repository.list_by_identity(org_2, identity.rule_identity_id) == []
        assert (
            org_2_adoption_repository.get_active_by_identity_and_scope(
                org_2,
                identity.rule_identity_id,
                "compra-abate",
                "fornecedores-diretos",
            )
            is None
        )
        assert (
            org_2_adoption_repository.get_active_by_code_purpose_and_scope(
                org_2,
                "rule-carencia-farmacologica",
                "compra-abate",
                "fornecedores-diretos",
            )
            is None
        )
