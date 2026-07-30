"""Testes unitários do contrato de execução determinística de Rules (ADR-0050)."""

from datetime import UTC, datetime

import pytest

from packages.core_domain.rule_execution import (
    RuleExecutionContext,
    RuleExecutionFailure,
    TechnicalFailureCategory,
)
from packages.shared_kernel import OrganizationId, TypedId


def _context(**overrides: object) -> RuleExecutionContext:
    base: dict[str, object] = {
        "rule_id": TypedId.new("rule"),
        "rule_version": 1,
        "organization_id": OrganizationId.new(),
        "subject_id": TypedId.new("batch"),
        "snapshot_hash": "abc123",
        "reference_time": datetime.now(UTC),
        "knowledge_cutoff": datetime.now(UTC),
        "engine_version": 1,
    }
    base.update(overrides)
    return RuleExecutionContext(**base)  # type: ignore[arg-type]


def test_context_requires_rule_typed_id() -> None:
    with pytest.raises(ValueError, match="rule_id deve ser do tipo 'rule'"):
        _context(rule_id=TypedId.new("policy"))


def test_context_rejects_rule_version_below_one() -> None:
    with pytest.raises(ValueError, match="rule_version"):
        _context(rule_version=0)


def test_context_rejects_empty_snapshot_hash() -> None:
    with pytest.raises(ValueError, match="snapshot_hash"):
        _context(snapshot_hash="   ")


def test_context_rejects_negative_resource_limit() -> None:
    with pytest.raises(ValueError, match="max_conditions_evaluated"):
        _context(max_conditions_evaluated=-1)


def test_context_accepts_optional_policy_reference() -> None:
    context = _context(policy_id=TypedId.new("policy"), policy_version=2, purpose="AUDITORIA")
    assert context.policy_id is not None
    assert context.policy_version == 2
    assert context.purpose == "AUDITORIA"


def test_context_policy_id_must_be_policy_typed_id_when_informed() -> None:
    with pytest.raises(ValueError, match="policy_id"):
        _context(policy_id=TypedId.new("rule"))


def test_context_without_resource_limit_is_valid() -> None:
    context = _context(max_conditions_evaluated=None)
    assert context.max_conditions_evaluated is None


def test_execution_failure_carries_category_and_message() -> None:
    failure = RuleExecutionFailure(
        TechnicalFailureCategory.RUNTIME_ERROR, "falha simulada de runtime"
    )

    assert failure.category is TechnicalFailureCategory.RUNTIME_ERROR
    assert failure.message == "falha simulada de runtime"
    assert str(failure) == "falha simulada de runtime"


def test_technical_failure_categories_match_adr_0050_vocabulary() -> None:
    expected = {
        "success",
        "timeout",
        "resource_limit",
        "invalid_input",
        "runtime_error",
        "contract_violation",
        "unsupported_version",
    }
    assert {c.value for c in TechnicalFailureCategory} == expected
