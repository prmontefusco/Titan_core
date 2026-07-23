"""Testes unitários do modelo de domínio para RuleResult e hash de entradas (Passo 6.4)."""

from datetime import UTC, datetime

import pytest

from packages.core_domain.evaluation import (
    RuleResult,
    RuleResultStatus,
    compute_rule_inputs_hash,
)
from packages.core_domain.rule import SeverityLevel
from packages.shared_kernel import OrganizationId, TypedId


def _make_result(**overrides: object) -> RuleResult:
    base: dict[str, object] = {
        "rule_id": TypedId.new("rule"),
        "rule_version": 1,
        "organization_id": OrganizationId.new(),
        "subject_id": TypedId.new("batch"),
        "status": RuleResultStatus.ATENDIDA,
        "severity": SeverityLevel.BLOCKING,
        "reason": "Todas as evidências exigidas estão presentes.",
        "evaluated_at": datetime.now(UTC),
        "snapshot_hash": "abc123",
        "inputs_hash": "def456",
    }
    base.update(overrides)
    return RuleResult.create(**base)  # type: ignore[arg-type]


def test_rule_result_requires_justification() -> None:
    with pytest.raises(ValueError, match="justificativa"):
        _make_result(reason="   ")


def test_rule_result_rejects_invalid_typed_ids() -> None:
    with pytest.raises(ValueError, match="result_id deve ser do tipo 'rule_result'"):
        RuleResult(
            result_id=TypedId.new("batch"),
            rule_id=TypedId.new("rule"),
            rule_version=1,
            organization_id=OrganizationId.new(),
            subject_id=TypedId.new("batch"),
            status=RuleResultStatus.ATENDIDA,
            severity=SeverityLevel.INFO,
            reason="ok",
            corrective_action="",
            missing_evidence_types=(),
            evaluated_at=datetime.now(UTC),
            snapshot_hash="h",
            inputs_hash="i",
        )


def test_rule_result_is_immutable() -> None:
    result = _make_result()
    with pytest.raises(AttributeError):
        result.status = RuleResultStatus.NAO_ATENDIDA  # type: ignore[misc]


def test_inputs_hash_is_deterministic_and_order_independent() -> None:
    rule_id = TypedId.new("rule")
    subject_id = TypedId.new("batch")

    h1 = compute_rule_inputs_hash(
        rule_id=rule_id,
        rule_version=2,
        subject_id=subject_id,
        snapshot_hash="snap-xyz",
        available_evidence_types=["b.type", "a.type", "A.TYPE"],
    )
    h2 = compute_rule_inputs_hash(
        rule_id=rule_id,
        rule_version=2,
        subject_id=subject_id,
        snapshot_hash="snap-xyz",
        available_evidence_types=["a.type", "b.type"],
    )

    assert h1 == h2
    assert len(h1) == 64


def test_inputs_hash_changes_with_rule_version() -> None:
    rule_id = TypedId.new("rule")
    subject_id = TypedId.new("batch")
    common = {
        "rule_id": rule_id,
        "subject_id": subject_id,
        "snapshot_hash": "snap-xyz",
        "available_evidence_types": ["a.type"],
    }
    h_v1 = compute_rule_inputs_hash(rule_version=1, **common)  # type: ignore[arg-type]
    h_v2 = compute_rule_inputs_hash(rule_version=2, **common)  # type: ignore[arg-type]
    assert h_v1 != h_v2
