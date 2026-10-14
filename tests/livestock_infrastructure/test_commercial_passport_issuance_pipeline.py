from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from pytest import MonkeyPatch

from packages.livestock_application.commercial_passport import (
    CommercialOpportunity,
    CommercialOpportunityKind,
    CommercialPassportContext,
)
from packages.livestock_infrastructure.persistence import commercial_passport as module
from packages.livestock_infrastructure.persistence.commercial_passport import (
    TransactionalPropertyCommercialPassportIssuancePipeline,
)
from packages.shared_kernel import OrganizationId, TypedId


def _context() -> CommercialPassportContext:
    instant = datetime(2026, 10, 14, tzinfo=UTC)
    return CommercialPassportContext(
        organization_id=OrganizationId.new(),
        property_id=TypedId.new("rural_property"),
        reference_time=instant,
        knowledge_cutoff=instant,
        evaluated_at=instant,
    )


def _opportunity() -> CommercialOpportunity:
    return CommercialOpportunity(
        code="internal-synthetic",
        kind=CommercialOpportunityKind.MARKET,
        name="Internal synthetic opportunity",
        purpose="internal-synthetic",
        policy_id=TypedId.new("policy"),
        policy_version=1,
    )


class _DecisionRepository:
    def __init__(self, decisions: list[object]) -> None:
        self.decisions = decisions

    def list_by_subject(self, *_args: object) -> list[object]:
        return self.decisions


class _EvaluationRepository:
    def __init__(self, evaluation: object | None) -> None:
        self.evaluation = evaluation

    def get_by_id(self, _evaluation_id: object) -> object | None:
        return self.evaluation


def test_formal_issuance_fails_closed_without_exact_decision(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(
        module, "TransactionalDecisionRepository", lambda _c: _DecisionRepository([])
    )
    pipeline = TransactionalPropertyCommercialPassportIssuancePipeline(
        connection=object(),  # type: ignore[arg-type]
        opportunity=_opportunity(),
    )

    with pytest.raises(ValueError, match="exata ausente"):
        pipeline.issue_property_passport(
            context=_context(),
            audience="internal",
            issued_at=datetime(2026, 10, 14, tzinfo=UTC),
        )


def test_formal_issuance_fails_closed_with_two_exact_decisions(monkeypatch: MonkeyPatch) -> None:
    context = _context()
    opportunity = _opportunity()
    evaluation_id = TypedId.new("evaluation")
    evaluation = SimpleNamespace(
        organization_id=context.organization_id,
        subject_id=context.property_id,
        purpose=opportunity.purpose,
        policy_id=opportunity.policy_id,
        policy_version=opportunity.policy_version,
        evaluation_hash="evaluation-hash",
        normative_basis_snapshot=SimpleNamespace(
            reference_time=context.reference_time,
            knowledge_cutoff=context.knowledge_cutoff,
        ),
    )
    decision = SimpleNamespace(
        organization_id=context.organization_id,
        subject_id=context.property_id,
        purpose=opportunity.purpose,
        policy_id=opportunity.policy_id,
        policy_version=opportunity.policy_version,
        evaluation_id=evaluation_id,
        evaluation_hash=evaluation.evaluation_hash,
    )
    monkeypatch.setattr(
        module,
        "TransactionalDecisionRepository",
        lambda _c: _DecisionRepository([decision, decision]),
    )
    monkeypatch.setattr(
        module,
        "TransactionalEvaluationRepository",
        lambda _c: _EvaluationRepository(evaluation),
    )
    pipeline = TransactionalPropertyCommercialPassportIssuancePipeline(
        connection=object(),  # type: ignore[arg-type]
        opportunity=opportunity,
    )

    with pytest.raises(ValueError, match="exata ambígua"):
        pipeline.issue_property_passport(
            context=context,
            audience="internal",
            issued_at=datetime(2026, 10, 14, tzinfo=UTC),
        )
