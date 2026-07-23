"""Testes de aplicação para a emissão de Decision explicável (Passo 6.6)."""

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from packages.core_application.decision_service import DecisionService
from packages.core_application.evaluation_service import (
    PolicyEvaluationService,
    RuleEvaluationEngine,
)
from packages.core_domain.decision import DecisionReasonCode, DecisionResult
from packages.core_domain.evaluation import Evaluation, EvaluationOutcome
from packages.core_domain.facts import Fact, FactSnapshot
from packages.core_domain.policy import Policy
from packages.core_domain.rule import ComparisonOperator, Rule, RuleCondition, SeverityLevel
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference


def _policy(org_id: OrganizationId) -> Policy:
    return Policy.create_draft(
        organization_id=org_id, code="pol-sanitaria", name="Política Sanitária"
    ).publish()


def _rule(policy: Policy, code: str, severity: SeverityLevel, expected: str = "approved") -> Rule:
    return Rule.create(
        policy_id=policy.policy_id,
        organization_id=policy.organization_id,
        code=code,
        name=code,
        severity=severity,
        conditions=(
            RuleCondition(
                fact_type="sanitary.attestation",
                payload_key="result",
                operator=ComparisonOperator.EQUALS,
                expected_value=expected,
            ),
        ),
        corrective_action="Reemitir o atestado sanitário.",
    )


def _snapshot(
    org_id: OrganizationId,
    subject_id: TypedId,
    as_of: datetime,
    result: str,
    source_reference: UniversalReference | None = None,
) -> FactSnapshot:
    return FactSnapshot.create(
        organization_id=org_id,
        target_id=subject_id,
        as_of=as_of,
        facts=[
            Fact.create(
                fact_type="sanitary.attestation",
                payload={"result": result},
                observed_at=as_of,
                source_reference=source_reference,
            )
        ],
    )


def _evaluate(policy: Policy, rules: list[Rule], snapshot: FactSnapshot) -> Evaluation:
    service = PolicyEvaluationService(engine=RuleEvaluationEngine())
    return service.evaluate_policy(
        policy=policy, rules=rules, snapshot=snapshot, purpose="CONFORMIDADE_SANITARIA"
    )


def test_satisfied_conditions_produce_approval_with_reasons() -> None:
    org_id = OrganizationId.new()
    subject_id = TypedId.new("batch")
    now = datetime.now(UTC)
    policy = _policy(org_id)
    rule = _rule(policy, "rule-atestado", SeverityLevel.BLOCKING)

    evaluation = _evaluate(policy, [rule], _snapshot(org_id, subject_id, now, "approved"))
    decision = DecisionService().decide(evaluation)

    assert decision.result == DecisionResult.APROVADA
    assert decision.reasons  # nunca existe conclusão sem justificativa
    assert decision.reasons_by_code(DecisionReasonCode.REGRA_ATENDIDA)
    assert decision.reasons[0].rule_code == "rule-atestado"
    assert decision.corrective_actions == ()
    assert decision.is_reproducible()


def test_blocking_failure_produces_rejection_with_corrective_action() -> None:
    org_id = OrganizationId.new()
    subject_id = TypedId.new("batch")
    now = datetime.now(UTC)
    policy = _policy(org_id)
    rule = _rule(policy, "rule-atestado", SeverityLevel.BLOCKING)

    evaluation = _evaluate(policy, [rule], _snapshot(org_id, subject_id, now, "rejected"))
    decision = DecisionService().decide(evaluation)

    assert decision.result == DecisionResult.REJEITADA
    razoes = decision.reasons_by_code(DecisionReasonCode.REGRA_NAO_ATENDIDA)
    assert len(razoes) == 1
    assert razoes[0].severity == SeverityLevel.BLOCKING
    assert decision.corrective_actions == ("Reemitir o atestado sanitário.",)


def test_non_blocking_failure_produces_approval_with_restrictions() -> None:
    org_id = OrganizationId.new()
    subject_id = TypedId.new("batch")
    now = datetime.now(UTC)
    policy = _policy(org_id)
    rule = _rule(policy, "rule-recomendacao", SeverityLevel.WARNING)

    evaluation = _evaluate(policy, [rule], _snapshot(org_id, subject_id, now, "rejected"))
    decision = DecisionService().decide(evaluation)

    assert evaluation.outcome == EvaluationOutcome.CONDICOES_NAO_SATISFEITAS
    # Descumprimento apenas informativo não reprova, mas também não aprova limpo.
    assert decision.result == DecisionResult.APROVADA_COM_RESTRICOES
    assert decision.corrective_actions == ("Reemitir o atestado sanitário.",)


def test_insufficient_information_is_never_an_approval() -> None:
    org_id = OrganizationId.new()
    subject_id = TypedId.new("batch")
    now = datetime.now(UTC)
    policy = _policy(org_id)
    rule = Rule.create(
        policy_id=policy.policy_id,
        organization_id=org_id,
        code="rule-laudo",
        name="Laudo obrigatório",
        severity=SeverityLevel.BLOCKING,
        required_evidence_types=("laudo_laboratorial",),
        corrective_action="Anexar o laudo laboratorial.",
    )

    evaluation = _evaluate(policy, [rule], _snapshot(org_id, subject_id, now, "approved"))
    decision = DecisionService().decide(evaluation)

    assert evaluation.outcome == EvaluationOutcome.INFORMACAO_INSUFICIENTE
    assert decision.result == DecisionResult.INDETERMINADA
    pendentes = decision.reasons_by_code(DecisionReasonCode.EVIDENCIA_PENDENTE)
    assert pendentes[0].missing_evidence_types == ("laudo_laboratorial",)


def test_decision_without_any_rule_states_that_nothing_was_verified() -> None:
    org_id = OrganizationId.new()
    subject_id = TypedId.new("batch")
    now = datetime.now(UTC)
    policy = _policy(org_id)

    evaluation = _evaluate(policy, [], _snapshot(org_id, subject_id, now, "approved"))
    decision = DecisionService().decide(evaluation)

    assert decision.result == DecisionResult.INDETERMINADA
    assert decision.reasons_by_code(DecisionReasonCode.NENHUMA_REGRA_APLICAVEL)


def test_decision_cites_evidence_backing_the_facts() -> None:
    org_id = OrganizationId.new()
    subject_id = TypedId.new("batch")
    now = datetime.now(UTC)
    policy = _policy(org_id)
    evidence_ref = UniversalReference(
        target_id=TypedId.new("evidence"), organization_id=org_id, contract_version=1
    )

    evaluation = _evaluate(
        policy,
        [_rule(policy, "rule-atestado", SeverityLevel.BLOCKING)],
        _snapshot(org_id, subject_id, now, "approved", source_reference=evidence_ref),
    )
    decision = DecisionService().decide(evaluation)

    assert decision.evidence_references == (evidence_ref,)
    assert decision.affected_subjects[0].target_id == subject_id


def test_decision_is_deterministic_and_reconstructible_from_evaluation() -> None:
    org_id = OrganizationId.new()
    subject_id = TypedId.new("batch")
    now = datetime.now(UTC)
    policy = _policy(org_id)
    rule = _rule(policy, "rule-atestado", SeverityLevel.BLOCKING)
    evaluation = _evaluate(policy, [rule], _snapshot(org_id, subject_id, now, "rejected"))

    service = DecisionService()
    primeira = service.decide(evaluation)
    segunda = service.decide(evaluation)

    # A identidade muda a cada emissão, mas a conclusão e o digest não.
    assert primeira.decision_id != segunda.decision_id
    assert primeira.decision_hash == segunda.decision_hash
    assert primeira.result == segunda.result


def test_tampered_evaluation_cannot_ground_a_decision() -> None:
    org_id = OrganizationId.new()
    subject_id = TypedId.new("batch")
    now = datetime.now(UTC)
    policy = _policy(org_id)
    rule = _rule(policy, "rule-atestado", SeverityLevel.BLOCKING)
    evaluation = _evaluate(policy, [rule], _snapshot(org_id, subject_id, now, "rejected"))

    # Alguém troca o resultado sem recalcular o hash preservado.
    adulterada = replace(evaluation, outcome=EvaluationOutcome.CONDICOES_SATISFEITAS)
    assert not adulterada.is_reproducible()

    with pytest.raises(ValueError, match="não reproduzível"):
        DecisionService().decide(adulterada)
