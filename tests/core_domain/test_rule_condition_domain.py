"""Testes unitários das condições normativas declarativas da Rule (Passo 6.4)."""

import pytest

from packages.core_domain.rule import (
    ComparisonOperator,
    ConditionOutcome,
    RuleCondition,
)


def _condition(**overrides: object) -> RuleCondition:
    base: dict[str, object] = {
        "fact_type": "sanitary.attestation",
        "payload_key": "result",
        "operator": ComparisonOperator.EQUALS,
        "expected_value": "approved",
    }
    base.update(overrides)
    return RuleCondition(**base)  # type: ignore[arg-type]


def test_condition_normalizes_fact_type_and_key() -> None:
    condition = _condition(fact_type="  Sanitary.Attestation  ", payload_key="  result  ")
    assert condition.fact_type == "sanitary.attestation"
    assert condition.payload_key == "result"


def test_condition_rejects_empty_fact_type_and_key() -> None:
    with pytest.raises(ValueError, match="fact_type da condição"):
        _condition(fact_type="   ")
    with pytest.raises(ValueError, match="payload_key da condição"):
        _condition(payload_key="   ")


def test_condition_satisfied_and_violated() -> None:
    condition = _condition()
    assert condition.check({"result": "approved"}) is ConditionOutcome.SATISFIED
    assert condition.check({"result": "rejected"}) is ConditionOutcome.VIOLATED


def test_condition_reports_missing_key_as_gap_not_violation() -> None:
    condition = _condition()
    assert condition.check({"outro_campo": 1}) is ConditionOutcome.KEY_MISSING


def test_ordering_operator_requires_numeric_expected_value() -> None:
    with pytest.raises(TypeError, match="exige um valor esperado numérico"):
        _condition(operator=ComparisonOperator.GREATER_OR_EQUAL, expected_value="dez")


def test_ordering_operator_on_non_numeric_payload_is_incomparable() -> None:
    condition = _condition(
        fact_type="livestock.weight_record",
        payload_key="average_weight_kg",
        operator=ComparisonOperator.GREATER_OR_EQUAL,
        expected_value=450,
    )
    assert condition.check({"average_weight_kg": 480}) is ConditionOutcome.SATISFIED
    assert condition.check({"average_weight_kg": 400}) is ConditionOutcome.VIOLATED
    assert condition.check({"average_weight_kg": "quatrocentos"}) is ConditionOutcome.INCOMPARABLE


def test_boolean_payload_is_not_compared_as_number() -> None:
    condition = _condition(
        payload_key="quarantine_cleared",
        operator=ComparisonOperator.GREATER_THAN,
        expected_value=0,
    )
    # True não deve ser tratado como 1 em comparação de ordem.
    assert condition.check({"quarantine_cleared": True}) is ConditionOutcome.INCOMPARABLE


def test_membership_operators_require_non_empty_list() -> None:
    with pytest.raises(TypeError, match="exige uma lista de valores esperados"):
        _condition(operator=ComparisonOperator.IN, expected_value="approved")
    with pytest.raises(ValueError, match="exige ao menos um valor esperado"):
        _condition(operator=ComparisonOperator.IN, expected_value=[])


def test_membership_operators_evaluate_and_normalize_to_tuple() -> None:
    condition = _condition(
        operator=ComparisonOperator.IN,
        expected_value=["approved", "approved_with_warning"],
    )
    assert condition.expected_value == ("approved", "approved_with_warning")
    assert condition.check({"result": "approved_with_warning"}) is ConditionOutcome.SATISFIED
    assert condition.check({"result": "rejected"}) is ConditionOutcome.VIOLATED

    negated = _condition(operator=ComparisonOperator.NOT_IN, expected_value=["rejected"])
    assert negated.check({"result": "approved"}) is ConditionOutcome.SATISFIED
    assert negated.check({"result": "rejected"}) is ConditionOutcome.VIOLATED


def test_condition_roundtrips_through_dict() -> None:
    original = _condition(
        operator=ComparisonOperator.IN,
        expected_value=["approved", "approved_with_warning"],
        description="Atestado sanitário aprovado",
    )
    restored = RuleCondition.from_dict(original.to_dict())
    assert restored == original


def test_describe_prefers_declared_description() -> None:
    assert _condition(description="Atestado aprovado").describe() == "Atestado aprovado"
    assert "sanitary.attestation.result" in _condition().describe()
