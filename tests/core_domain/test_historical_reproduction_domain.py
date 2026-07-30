"""Testes unitários do domínio de ReproductionReport (ADR-0052)."""

from datetime import UTC, datetime

import pytest

from packages.core_domain.evaluation import EvaluationOutcome
from packages.core_domain.historical_reproduction import ReproductionReport
from packages.shared_kernel import OrganizationId, TypedId


def _report(**overrides: object) -> ReproductionReport:
    base: dict[str, object] = {
        "report_id": TypedId.new("reproduction_report"),
        "organization_id": OrganizationId.new(),
        "evaluation_id": TypedId.new("evaluation"),
        "reproduced_at": datetime.now(UTC),
        "context_hash_matches": True,
        "evaluation_hash_matches": True,
        "outcome_matches": True,
        "original_outcome": EvaluationOutcome.CONDICOES_SATISFEITAS,
        "reproduced_outcome": EvaluationOutcome.CONDICOES_SATISFEITAS,
    }
    base.update(overrides)
    return ReproductionReport(**base)  # type: ignore[arg-type]


def test_report_requires_reproduction_report_typed_id() -> None:
    with pytest.raises(ValueError, match="report_id deve ser do tipo 'reproduction_report'"):
        _report(report_id=TypedId.new("evaluation"))


def test_report_requires_evaluation_typed_id() -> None:
    with pytest.raises(ValueError, match="evaluation_id deve ser do tipo 'evaluation'"):
        _report(evaluation_id=TypedId.new("decision"))


def test_matching_report_has_no_divergences() -> None:
    report = _report()
    assert report.matches
    assert report.divergences == ()


def test_matching_report_cannot_carry_divergences() -> None:
    with pytest.raises(ValueError, match="não pode carregar divergências"):
        _report(divergences=("algo estranho",))


def test_divergent_report_requires_at_least_one_description() -> None:
    with pytest.raises(ValueError, match="exige ao menos uma descrição"):
        _report(outcome_matches=False)


def test_divergent_report_reports_matches_false() -> None:
    report = _report(
        outcome_matches=False,
        reproduced_outcome=EvaluationOutcome.CONDICOES_NAO_SATISFEITAS,
        divergences=("outcome divergente.",),
    )
    assert not report.matches
