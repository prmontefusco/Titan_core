"""Testes de aplicação para HistoricalReproductionService (ADR-0052 §10.1)."""

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from packages.core_application.evaluation_service import (
    PolicyEvaluationService,
    RuleEvaluationEngine,
)
from packages.core_application.historical_reproduction_service import (
    HistoricalReproductionService,
)
from packages.core_domain.evaluation import EvaluationOutcome
from packages.core_domain.facts import Fact, FactSnapshot
from packages.core_domain.policy import Policy
from packages.core_domain.rule import ComparisonOperator, Rule, RuleCondition
from packages.shared_kernel import OrganizationId, TypedId


def _published_policy(org_id: OrganizationId) -> Policy:
    return Policy.create_draft(
        organization_id=org_id, code="pol-reproducao", name="Política de Reprodução"
    ).publish()


def _rule(policy: Policy) -> Rule:
    return Rule.create(
        policy_id=policy.policy_id,
        organization_id=policy.organization_id,
        code="rule-atestado",
        name="rule-atestado",
        conditions=(
            RuleCondition(
                fact_type="sanitary.attestation",
                payload_key="result",
                operator=ComparisonOperator.EQUALS,
                expected_value="approved",
            ),
        ),
    )


def _snapshot(org_id: OrganizationId, subject_id: TypedId, as_of: datetime) -> FactSnapshot:
    return FactSnapshot.create(
        organization_id=org_id,
        target_id=subject_id,
        as_of=as_of,
        facts=[
            Fact.create(
                fact_type="sanitary.attestation", payload={"result": "approved"}, observed_at=as_of
            )
        ],
    )


def test_reproduction_matches_when_rules_and_snapshot_are_identical() -> None:
    org_id = OrganizationId.new()
    subject_id = TypedId.new("batch")
    now = datetime.now(UTC)
    policy = _published_policy(org_id)
    rule = _rule(policy)
    snapshot = _snapshot(org_id, subject_id, now)

    evaluation = PolicyEvaluationService(engine=RuleEvaluationEngine()).evaluate_policy(
        policy=policy, rules=[rule], snapshot=snapshot, purpose="AUDITORIA"
    )

    report = HistoricalReproductionService(engine=RuleEvaluationEngine()).reproduce(
        evaluation, rules=[rule]
    )

    assert report.matches
    assert report.divergences == ()
    assert report.context_hash_matches
    assert report.evaluation_hash_matches
    assert report.outcome_matches
    assert report.limitations
    assert report.original_outcome == EvaluationOutcome.CONDICOES_SATISFEITAS
    assert report.reproduced_outcome == EvaluationOutcome.CONDICOES_SATISFEITAS


def test_reproduction_is_deterministic_across_attempts() -> None:
    org_id = OrganizationId.new()
    subject_id = TypedId.new("batch")
    now = datetime.now(UTC)
    policy = _published_policy(org_id)
    rule = _rule(policy)
    snapshot = _snapshot(org_id, subject_id, now)

    evaluation = PolicyEvaluationService(engine=RuleEvaluationEngine()).evaluate_policy(
        policy=policy, rules=[rule], snapshot=snapshot, purpose="AUDITORIA"
    )

    service = HistoricalReproductionService(engine=RuleEvaluationEngine())
    first = service.reproduce(evaluation, rules=[rule])
    second = service.reproduce(evaluation, rules=[rule])

    assert first.matches and second.matches
    # A identidade da reprodução é estável; só o metadado observacional muda.
    assert first.report_id != second.report_id


def test_reproduction_rejects_missing_rule() -> None:
    org_id = OrganizationId.new()
    subject_id = TypedId.new("batch")
    now = datetime.now(UTC)
    policy = _published_policy(org_id)
    rule = _rule(policy)
    snapshot = _snapshot(org_id, subject_id, now)

    evaluation = PolicyEvaluationService(engine=RuleEvaluationEngine()).evaluate_policy(
        policy=policy, rules=[rule], snapshot=snapshot, purpose="AUDITORIA"
    )

    with pytest.raises(ValueError, match="exatamente as Rules e versões"):
        HistoricalReproductionService(engine=RuleEvaluationEngine()).reproduce(evaluation, rules=[])


def test_reproduction_rejects_extra_rule_not_in_original() -> None:
    org_id = OrganizationId.new()
    subject_id = TypedId.new("batch")
    now = datetime.now(UTC)
    policy = _published_policy(org_id)
    rule = _rule(policy)
    outra_regra = Rule.create(
        policy_id=policy.policy_id,
        organization_id=org_id,
        code="rule-extra",
        name="rule-extra",
    )
    snapshot = _snapshot(org_id, subject_id, now)

    evaluation = PolicyEvaluationService(engine=RuleEvaluationEngine()).evaluate_policy(
        policy=policy, rules=[rule], snapshot=snapshot, purpose="AUDITORIA"
    )

    with pytest.raises(ValueError, match="exatamente as Rules e versões"):
        HistoricalReproductionService(engine=RuleEvaluationEngine()).reproduce(
            evaluation, rules=[rule, outra_regra]
        )


def test_reproduction_rejects_different_rule_version() -> None:
    org_id = OrganizationId.new()
    subject_id = TypedId.new("batch")
    now = datetime.now(UTC)
    policy = _published_policy(org_id)
    rule = _rule(policy)
    snapshot = _snapshot(org_id, subject_id, now)

    evaluation = PolicyEvaluationService(engine=RuleEvaluationEngine()).evaluate_policy(
        policy=policy, rules=[rule], snapshot=snapshot, purpose="AUDITORIA"
    )

    nova_versao = rule.create_next_version()
    with pytest.raises(ValueError, match="exatamente as Rules e versões"):
        HistoricalReproductionService(engine=RuleEvaluationEngine()).reproduce(
            evaluation, rules=[nova_versao]
        )


def test_reproduction_detects_tampered_evaluation_hash() -> None:
    """Uma Evaluation com hash adulterado não reproduz -- e o relatório diz por quê."""
    org_id = OrganizationId.new()
    subject_id = TypedId.new("batch")
    now = datetime.now(UTC)
    policy = _published_policy(org_id)
    rule = _rule(policy)
    snapshot = _snapshot(org_id, subject_id, now)

    evaluation = PolicyEvaluationService(engine=RuleEvaluationEngine()).evaluate_policy(
        policy=policy, rules=[rule], snapshot=snapshot, purpose="AUDITORIA"
    )
    adulterada = replace(evaluation, evaluation_hash="f" * 64)
    assert not adulterada.is_reproducible()

    report = HistoricalReproductionService(engine=RuleEvaluationEngine()).reproduce(
        adulterada, rules=[rule]
    )

    assert not report.matches
    assert not report.evaluation_hash_matches
    assert report.context_hash_matches
    assert report.outcome_matches
    assert any("evaluation_hash" in d for d in report.divergences)
    # A Evaluation original -- adulterada ou não -- nunca é alterada pelo relatório.
    assert adulterada.evaluation_hash == "f" * 64


def test_reproduction_declares_temporal_limitations_when_known_at_is_approximated() -> None:
    org_id = OrganizationId.new()
    subject_id = TypedId.new("batch")
    now = datetime.now(UTC)
    policy = _published_policy(org_id)
    rule = _rule(policy)
    snapshot = FactSnapshot.create(
        organization_id=org_id,
        target_id=subject_id,
        as_of=now,
        facts=[
            Fact.create(
                fact_type="sanitary.attestation",
                payload={"result": "approved"},
                observed_at=now,
                recorded_at=now,
            )
        ],
    )

    evaluation = PolicyEvaluationService(engine=RuleEvaluationEngine()).evaluate_policy(
        policy=policy, rules=[rule], snapshot=snapshot, purpose="AUDITORIA"
    )

    report = HistoricalReproductionService(engine=RuleEvaluationEngine()).reproduce(
        evaluation, rules=[rule]
    )

    assert report.matches
    assert any("recorded_at_fallback" in d for d in report.limitations)


def test_reproduction_declares_when_normative_acceptance_is_not_available() -> None:
    org_id = OrganizationId.new()
    subject_id = TypedId.new("batch")
    now = datetime.now(UTC)
    policy = _published_policy(org_id)
    rule = _rule(policy)
    snapshot = FactSnapshot.create(
        organization_id=org_id,
        target_id=subject_id,
        as_of=now,
        facts=[
            Fact.create(
                fact_type="sanitary.attestation",
                payload={"result": "approved"},
                observed_at=now,
                known_at=now,
                accepted_at=None,
            )
        ],
    )

    evaluation = PolicyEvaluationService(engine=RuleEvaluationEngine()).evaluate_policy(
        policy=policy, rules=[rule], snapshot=snapshot, purpose="AUDITORIA"
    )

    report = HistoricalReproductionService(engine=RuleEvaluationEngine()).reproduce(
        evaluation, rules=[rule]
    )

    assert report.matches
    assert any("accepted_at" in d for d in report.limitations)
