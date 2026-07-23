"""Testes unitários do domínio de Decision e DecisionReason (Passo 6.6)."""

from datetime import UTC, datetime

import pytest

from packages.core_domain.decision import (
    Decision,
    DecisionReason,
    DecisionReasonCode,
    DecisionResult,
    compute_decision_hash,
)
from packages.core_domain.rule import SeverityLevel
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference


def _reason() -> DecisionReason:
    return DecisionReason(
        code=DecisionReasonCode.REGRA_NAO_ATENDIDA,
        message="Regra 'rule-atestado' não atendida.",
        rule_code="rule-atestado",
        rule_id=TypedId.new("rule"),
        rule_version=1,
        severity=SeverityLevel.BLOCKING,
        corrective_action="Reemitir o atestado.",
    )


def _decision(reasons: tuple[DecisionReason, ...]) -> Decision:
    org_id = OrganizationId.new()
    subject_id = TypedId.new("batch")
    policy_id = TypedId.new("policy")
    return Decision(
        decision_id=TypedId.new("decision"),
        organization_id=org_id,
        subject_id=subject_id,
        purpose="CONFORMIDADE_SANITARIA",
        evaluation_id=TypedId.new("evaluation"),
        evaluation_hash="eval-hash",
        policy_id=policy_id,
        policy_version=1,
        result=DecisionResult.REJEITADA,
        reasons=reasons,
        snapshot_hash="snap-hash",
        issued_at=datetime.now(UTC),
        engine_version=1,
        decision_hash=compute_decision_hash(
            evaluation_hash="eval-hash",
            policy_id=policy_id,
            policy_version=1,
            subject_id=subject_id,
            purpose="CONFORMIDADE_SANITARIA",
            result=DecisionResult.REJEITADA,
            reasons=reasons,
            engine_version=1,
        ),
    )


def test_decision_requires_at_least_one_reason() -> None:
    with pytest.raises(ValueError, match="ao menos uma DecisionReason"):
        _decision(())


def test_reason_requires_human_message() -> None:
    with pytest.raises(ValueError, match="mensagem humana"):
        DecisionReason(code=DecisionReasonCode.REGRA_ATENDIDA, message="   ")


def test_decision_is_immutable_and_self_verifiable() -> None:
    decision = _decision((_reason(),))
    assert decision.is_reproducible()
    with pytest.raises(AttributeError):
        decision.result = DecisionResult.APROVADA  # type: ignore[misc]


def test_reason_roundtrips_through_dict() -> None:
    original = DecisionReason(
        code=DecisionReasonCode.EVIDENCIA_PENDENTE,
        message="Aguardando laudo.",
        rule_code="rule-laudo",
        rule_id=TypedId.new("rule"),
        rule_version=2,
        severity=SeverityLevel.CRITICAL,
        corrective_action="Anexar laudo.",
        missing_evidence_types=("laudo_laboratorial",),
        evidence_references=(
            UniversalReference(
                target_id=TypedId.new("evidence"),
                organization_id=OrganizationId.new(),
                contract_version=1,
            ),
        ),
    )
    assert DecisionReason.from_dict(original.to_dict()) == original


def test_reason_without_rule_roundtrips() -> None:
    original = DecisionReason(
        code=DecisionReasonCode.NENHUMA_REGRA_APLICAVEL,
        message="Nenhuma regra executada.",
    )
    restored = DecisionReason.from_dict(original.to_dict())
    assert restored == original
    assert restored.rule_id is None
    assert restored.severity is None


def test_decision_hash_ignores_message_but_not_code() -> None:
    rule_id = TypedId.new("rule")
    subject_id = TypedId.new("batch")
    policy_id = TypedId.new("policy")

    def _hash(code: DecisionReasonCode, message: str) -> str:
        return compute_decision_hash(
            evaluation_hash="eval-hash",
            policy_id=policy_id,
            policy_version=1,
            subject_id=subject_id,
            purpose="CONFORMIDADE",
            result=DecisionResult.REJEITADA,
            reasons=(
                DecisionReason(
                    code=code, message=message, rule_code="rule-a", rule_id=rule_id, rule_version=1
                ),
            ),
            engine_version=1,
        )

    # A mensagem humana pode ser traduzida sem alterar o contrato da decisão.
    assert _hash(DecisionReasonCode.REGRA_NAO_ATENDIDA, "Não atendida.") == _hash(
        DecisionReasonCode.REGRA_NAO_ATENDIDA, "Not satisfied."
    )
    # O código é contrato: mudá-lo muda a decisão.
    assert _hash(DecisionReasonCode.REGRA_NAO_ATENDIDA, "x") != _hash(
        DecisionReasonCode.REGRA_INDETERMINADA, "x"
    )
