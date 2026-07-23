"""Testes unitários do agregado Evaluation e da agregação de resultados (Passo 6.5)."""

from datetime import UTC, datetime

import pytest

from packages.core_domain.evaluation import (
    Evaluation,
    EvaluationOutcome,
    RuleResult,
    RuleResultStatus,
    aggregate_outcome,
    compute_evaluation_hash,
)
from packages.core_domain.facts import Fact, FactSnapshot
from packages.core_domain.rule import SeverityLevel
from packages.shared_kernel import OrganizationId, TypedId


def _result(status: RuleResultStatus, org_id: OrganizationId, subject_id: TypedId) -> RuleResult:
    return RuleResult.create(
        rule_id=TypedId.new("rule"),
        rule_version=1,
        organization_id=org_id,
        subject_id=subject_id,
        status=status,
        severity=SeverityLevel.BLOCKING,
        reason=f"Resultado {status.value}.",
        evaluated_at=datetime.now(UTC),
        snapshot_hash="snap",
        inputs_hash=f"hash-{status.value}",
    )


def _snapshot(org_id: OrganizationId, subject_id: TypedId, as_of: datetime) -> FactSnapshot:
    return FactSnapshot.create(
        organization_id=org_id,
        target_id=subject_id,
        as_of=as_of,
        facts=[Fact.create(fact_type="sanitary.attestation", payload={"r": 1}, observed_at=as_of)],
    )


def _evaluation(
    org_id: OrganizationId,
    subject_id: TypedId,
    snapshot: FactSnapshot,
    results: tuple[RuleResult, ...],
) -> Evaluation:
    outcome = aggregate_outcome(results)
    policy_id = TypedId.new("policy")
    return Evaluation(
        evaluation_id=TypedId.new("evaluation"),
        organization_id=org_id,
        subject_id=subject_id,
        purpose="CONFORMIDADE_SANITARIA",
        policy_id=policy_id,
        policy_version=1,
        fact_snapshot=snapshot,
        rule_results=results,
        outcome=outcome,
        evaluated_at=snapshot.as_of,
        engine_version=1,
        evaluation_hash=compute_evaluation_hash(
            policy_id=policy_id,
            policy_version=1,
            subject_id=subject_id,
            purpose="CONFORMIDADE_SANITARIA",
            snapshot_hash=snapshot.snapshot_hash,
            rule_results=results,
            outcome=outcome,
            engine_version=1,
        ),
    )


def test_violation_prevails_over_gaps() -> None:
    org_id = OrganizationId.new()
    subject_id = TypedId.new("batch")
    results = (
        _result(RuleResultStatus.ATENDIDA, org_id, subject_id),
        _result(RuleResultStatus.PENDENTE, org_id, subject_id),
        _result(RuleResultStatus.NAO_ATENDIDA, org_id, subject_id),
    )
    assert aggregate_outcome(results) == EvaluationOutcome.CONDICOES_NAO_SATISFEITAS


def test_pending_prevails_over_indeterminate() -> None:
    org_id = OrganizationId.new()
    subject_id = TypedId.new("batch")
    results = (
        _result(RuleResultStatus.INDETERMINADA, org_id, subject_id),
        _result(RuleResultStatus.PENDENTE, org_id, subject_id),
    )
    assert aggregate_outcome(results) == EvaluationOutcome.INFORMACAO_INSUFICIENTE


def test_all_satisfied_yields_conditions_met() -> None:
    org_id = OrganizationId.new()
    subject_id = TypedId.new("batch")
    results = (
        _result(RuleResultStatus.ATENDIDA, org_id, subject_id),
        _result(RuleResultStatus.NAO_APLICAVEL, org_id, subject_id),
    )
    assert aggregate_outcome(results) == EvaluationOutcome.CONDICOES_SATISFEITAS


def test_nothing_verified_is_never_reported_as_compliant() -> None:
    org_id = OrganizationId.new()
    subject_id = TypedId.new("batch")

    # Sem nenhuma regra executada, nada foi verificado.
    assert aggregate_outcome(()) == EvaluationOutcome.INDETERMINADO

    # Somente regras não aplicáveis: nada foi efetivamente checado.
    only_na = (_result(RuleResultStatus.NAO_APLICAVEL, org_id, subject_id),)
    assert aggregate_outcome(only_na) == EvaluationOutcome.INDETERMINADO


def test_evaluation_requires_purpose_and_matching_snapshot() -> None:
    org_id = OrganizationId.new()
    subject_id = TypedId.new("batch")
    now = datetime.now(UTC)
    snapshot = _snapshot(org_id, subject_id, now)
    results = (_result(RuleResultStatus.ATENDIDA, org_id, subject_id),)

    base = _evaluation(org_id, subject_id, snapshot, results)

    with pytest.raises(ValueError, match="finalidade"):
        Evaluation(
            evaluation_id=base.evaluation_id,
            organization_id=org_id,
            subject_id=subject_id,
            purpose="   ",
            policy_id=base.policy_id,
            policy_version=1,
            fact_snapshot=snapshot,
            rule_results=results,
            outcome=base.outcome,
            evaluated_at=now,
            engine_version=1,
            evaluation_hash=base.evaluation_hash,
        )

    # O snapshot precisa descrever o mesmo Subject da Evaluation.
    outro_snapshot = _snapshot(org_id, TypedId.new("batch"), now)
    with pytest.raises(ValueError, match="deve descrever o Subject"):
        Evaluation(
            evaluation_id=base.evaluation_id,
            organization_id=org_id,
            subject_id=subject_id,
            purpose="CONFORMIDADE_SANITARIA",
            policy_id=base.policy_id,
            policy_version=1,
            fact_snapshot=outro_snapshot,
            rule_results=results,
            outcome=base.outcome,
            evaluated_at=now,
            engine_version=1,
            evaluation_hash=base.evaluation_hash,
        )


def test_evaluation_is_immutable_and_self_verifiable() -> None:
    org_id = OrganizationId.new()
    subject_id = TypedId.new("batch")
    now = datetime.now(UTC)
    snapshot = _snapshot(org_id, subject_id, now)
    results = (_result(RuleResultStatus.ATENDIDA, org_id, subject_id),)

    evaluation = _evaluation(org_id, subject_id, snapshot, results)

    assert evaluation.is_reproducible()
    with pytest.raises(AttributeError):
        evaluation.outcome = EvaluationOutcome.INDETERMINADO  # type: ignore[misc]


def test_evaluation_hash_ignores_result_identity_but_not_content() -> None:
    org_id = OrganizationId.new()
    subject_id = TypedId.new("batch")
    now = datetime.now(UTC)
    snapshot = _snapshot(org_id, subject_id, now)
    policy_id = TypedId.new("policy")
    rule_id = TypedId.new("rule")

    def _fixed_result(status: RuleResultStatus) -> RuleResult:
        return RuleResult.create(
            rule_id=rule_id,
            rule_version=1,
            organization_id=org_id,
            subject_id=subject_id,
            status=status,
            severity=SeverityLevel.BLOCKING,
            reason="Justificativa.",
            evaluated_at=now,
            snapshot_hash=snapshot.snapshot_hash,
            inputs_hash="inputs-estaveis",
        )

    def _hash(results: tuple[RuleResult, ...]) -> str:
        return compute_evaluation_hash(
            policy_id=policy_id,
            policy_version=1,
            subject_id=subject_id,
            purpose="CONFORMIDADE_SANITARIA",
            snapshot_hash=snapshot.snapshot_hash,
            rule_results=results,
            outcome=aggregate_outcome(results),
            engine_version=1,
        )

    atendida_a = _fixed_result(RuleResultStatus.ATENDIDA)
    atendida_b = _fixed_result(RuleResultStatus.ATENDIDA)
    # Instâncias distintas com o mesmo conteúdo produzem o mesmo hash.
    assert atendida_a.result_id != atendida_b.result_id
    assert _hash((atendida_a,)) == _hash((atendida_b,))

    # Conteúdo diferente muda o hash.
    assert _hash((atendida_a,)) != _hash((_fixed_result(RuleResultStatus.NAO_ATENDIDA),))
