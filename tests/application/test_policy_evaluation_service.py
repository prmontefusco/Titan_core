"""Testes de aplicação para o PolicyEvaluationService (Passo 6.5)."""

from datetime import UTC, datetime, timedelta

import pytest

from packages.core_application.evaluation_service import (
    PolicyEvaluationService,
    RuleEvaluationEngine,
)
from packages.core_domain.evaluation import EvaluationOutcome, RuleResultStatus
from packages.core_domain.facts import Fact, FactSnapshot
from packages.core_domain.policy import Policy
from packages.core_domain.rule import ComparisonOperator, Rule, RuleCondition, SeverityLevel
from packages.shared_kernel import OrganizationId, TypedId


def _published_policy(org_id: OrganizationId) -> Policy:
    return Policy.create_draft(
        organization_id=org_id,
        code="pol-sanitaria-lotes",
        name="Política de Sanidade dos Lotes",
    ).publish()


def _rule(
    policy: Policy,
    code: str,
    conditions: tuple[RuleCondition, ...] = (),
    required: tuple[str, ...] = (),
) -> Rule:
    return Rule.create(
        policy_id=policy.policy_id,
        organization_id=policy.organization_id,
        code=code,
        name=code,
        description="",
        severity=SeverityLevel.BLOCKING,
        required_evidence_types=required,
        conditions=conditions,
        corrective_action="Providenciar o documento faltante.",
    )


def _snapshot(
    org_id: OrganizationId,
    subject_id: TypedId,
    as_of: datetime,
    payloads: dict[str, dict[str, object]],
) -> FactSnapshot:
    return FactSnapshot.create(
        organization_id=org_id,
        target_id=subject_id,
        as_of=as_of,
        facts=[
            Fact.create(fact_type=ft, payload=payload, observed_at=as_of)
            for ft, payload in payloads.items()
        ],
    )


def _service() -> PolicyEvaluationService:
    return PolicyEvaluationService(engine=RuleEvaluationEngine())


def test_policy_evaluation_aggregates_all_rules() -> None:
    org_id = OrganizationId.new()
    subject_id = TypedId.new("batch")
    now = datetime.now(UTC)
    policy = _published_policy(org_id)

    aprovada = _rule(
        policy,
        "rule-atestado",
        conditions=(
            RuleCondition(
                fact_type="sanitary.attestation",
                payload_key="result",
                operator=ComparisonOperator.EQUALS,
                expected_value="approved",
            ),
        ),
    )
    reprovada = _rule(
        policy,
        "rule-peso-minimo",
        conditions=(
            RuleCondition(
                fact_type="livestock.weight_record",
                payload_key="average_weight_kg",
                operator=ComparisonOperator.GREATER_OR_EQUAL,
                expected_value=450,
            ),
        ),
    )

    snapshot = _snapshot(
        org_id,
        subject_id,
        now,
        {
            "sanitary.attestation": {"result": "approved"},
            "livestock.weight_record": {"average_weight_kg": 380},
        },
    )

    evaluation = _service().evaluate_policy(
        policy=policy,
        rules=[aprovada, reprovada],
        snapshot=snapshot,
        purpose="CONFORMIDADE_SANITARIA",
    )

    assert len(evaluation.rule_results) == 2
    assert evaluation.outcome == EvaluationOutcome.CONDICOES_NAO_SATISFEITAS
    assert len(evaluation.results_by_status(RuleResultStatus.ATENDIDA)) == 1
    assert len(evaluation.results_by_status(RuleResultStatus.NAO_ATENDIDA)) == 1
    assert evaluation.is_reproducible()
    assert evaluation.policy_version == policy.version
    assert ("rule-atestado", 1) in evaluation.rule_versions


def test_evaluation_survives_later_fact_changes() -> None:
    org_id = OrganizationId.new()
    subject_id = TypedId.new("batch")
    t0 = datetime.now(UTC)
    policy = _published_policy(org_id)
    rule = _rule(
        policy,
        "rule-atestado",
        conditions=(
            RuleCondition(
                fact_type="sanitary.attestation",
                payload_key="result",
                operator=ComparisonOperator.EQUALS,
                expected_value="approved",
            ),
        ),
    )

    snapshot_t0 = _snapshot(
        org_id, subject_id, t0, {"sanitary.attestation": {"result": "approved"}}
    )
    service = _service()
    evaluation_t0 = service.evaluate_policy(
        policy=policy,
        rules=[rule],
        snapshot=snapshot_t0,
        purpose="CONFORMIDADE_SANITARIA",
    )
    assert evaluation_t0.outcome == EvaluationOutcome.CONDICOES_SATISFEITAS

    # Os fatos mudam depois: o atestado passa a estar reprovado.
    snapshot_t1 = _snapshot(
        org_id,
        subject_id,
        t0 + timedelta(days=30),
        {"sanitary.attestation": {"result": "rejected"}},
    )
    evaluation_t1 = service.evaluate_policy(
        policy=policy,
        rules=[rule],
        snapshot=snapshot_t1,
        purpose="CONFORMIDADE_SANITARIA",
    )
    assert evaluation_t1.outcome == EvaluationOutcome.CONDICOES_NAO_SATISFEITAS

    # A avaliação anterior permanece intacta e reproduzível a partir do que preservou.
    assert evaluation_t0.outcome == EvaluationOutcome.CONDICOES_SATISFEITAS
    assert evaluation_t0.is_reproducible()
    assert evaluation_t0.fact_snapshot.snapshot_hash == snapshot_t0.snapshot_hash
    assert evaluation_t0.evaluation_hash != evaluation_t1.evaluation_hash


def test_evaluation_is_deterministic_regardless_of_rule_order() -> None:
    org_id = OrganizationId.new()
    subject_id = TypedId.new("batch")
    now = datetime.now(UTC)
    policy = _published_policy(org_id)
    r1 = _rule(policy, "rule-a", required=("sanitary.attestation",))
    r2 = _rule(policy, "rule-b", required=("transport.gta",))

    snapshot = _snapshot(
        org_id,
        subject_id,
        now,
        {"sanitary.attestation": {"result": "approved"}, "transport.gta": {"numero": "1"}},
    )

    service = _service()
    direta = service.evaluate_policy(
        policy=policy, rules=[r1, r2], snapshot=snapshot, purpose="CONFORMIDADE"
    )
    invertida = service.evaluate_policy(
        policy=policy, rules=[r2, r1], snapshot=snapshot, purpose="CONFORMIDADE"
    )

    assert direta.evaluation_hash == invertida.evaluation_hash
    assert direta.evaluation_id != invertida.evaluation_id


def test_draft_policy_cannot_be_evaluated() -> None:
    org_id = OrganizationId.new()
    subject_id = TypedId.new("batch")
    now = datetime.now(UTC)
    draft = Policy.create_draft(organization_id=org_id, code="pol-rascunho", name="Rascunho")
    snapshot = _snapshot(org_id, subject_id, now, {"x.y": {"a": 1}})

    with pytest.raises(ValueError, match="não pode ser avaliada"):
        _service().evaluate_policy(
            policy=draft, rules=[], snapshot=snapshot, purpose="CONFORMIDADE"
        )


def test_revoked_policy_cannot_produce_new_evaluation() -> None:
    org_id = OrganizationId.new()
    subject_id = TypedId.new("batch")
    now = datetime.now(UTC)
    revogada = _published_policy(org_id).revoke()
    snapshot = _snapshot(org_id, subject_id, now, {"x.y": {"a": 1}})

    with pytest.raises(ValueError, match="não pode ser avaliada"):
        _service().evaluate_policy(
            policy=revogada, rules=[], snapshot=snapshot, purpose="CONFORMIDADE"
        )


def test_superseded_policy_remains_evaluable_for_historical_replay() -> None:
    org_id = OrganizationId.new()
    subject_id = TypedId.new("batch")
    now = datetime.now(UTC)
    substituida = _published_policy(org_id).supersede()
    snapshot = _snapshot(org_id, subject_id, now, {"x.y": {"a": 1}})

    evaluation = _service().evaluate_policy(
        policy=substituida, rules=[], snapshot=snapshot, purpose="REAVALIACAO_HISTORICA"
    )
    assert evaluation.outcome == EvaluationOutcome.INDETERMINADO


def test_rule_from_another_policy_is_rejected() -> None:
    org_id = OrganizationId.new()
    subject_id = TypedId.new("batch")
    now = datetime.now(UTC)
    policy = _published_policy(org_id)
    outra = _published_policy(org_id)
    snapshot = _snapshot(org_id, subject_id, now, {"x.y": {"a": 1}})

    with pytest.raises(ValueError, match="devem pertencer à política"):
        _service().evaluate_policy(
            policy=policy,
            rules=[_rule(outra, "rule-intrusa")],
            snapshot=snapshot,
            purpose="CONFORMIDADE",
        )


def test_snapshot_from_another_organization_is_rejected() -> None:
    org_id = OrganizationId.new()
    outra_org = OrganizationId.new()
    subject_id = TypedId.new("batch")
    now = datetime.now(UTC)
    policy = _published_policy(org_id)
    snapshot = _snapshot(outra_org, subject_id, now, {"x.y": {"a": 1}})

    with pytest.raises(ValueError, match="mesma Organization"):
        _service().evaluate_policy(
            policy=policy, rules=[], snapshot=snapshot, purpose="CONFORMIDADE"
        )
