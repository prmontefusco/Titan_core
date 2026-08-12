"""Caso de uso para reprodução histórica de Evaluation (ADR-0052 §10.1).

Implementa o `HistoricalReproduction` já formalizado em `DOMAIN.md`: reexecuta as
Rules exatas de uma Evaluation preservada sobre o `FactSnapshot` que ela já
congelou, sem consultar fato, Policy ou conhecimento posterior — o snapshot
preservado é a única entrada, nunca o estado atual do domínio.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from packages.core_application.evaluation_service import RuleEvaluationEngine
from packages.core_domain.evaluation import (
    Evaluation,
    aggregate_outcome,
    compute_context_hash,
    compute_evaluation_hash,
)
from packages.core_domain.historical_reproduction import ReproductionReport
from packages.core_domain.rule import Rule
from packages.shared_kernel import Clock, SystemClock, TypedId


@dataclass(frozen=True, slots=True)
class HistoricalReproductionService:
    engine: RuleEvaluationEngine
    clock: Clock = SystemClock()

    def reproduce(
        self,
        evaluation: Evaluation,
        rules: Sequence[Rule],
    ) -> ReproductionReport:
        """Reexecuta `rules` sobre o snapshot preservado e compara com o original.

        `rules` deve conter exatamente as versões que `evaluation.rule_versions`
        registrou — nem mais, nem menos, nem outra versão: reprodução verifica o
        que aconteceu, não o que aconteceria com regras diferentes (isso seria
        `CounterfactualSimulation`, um conceito distinto).
        """
        expected = set(evaluation.rule_versions)
        provided = {(rule.code, rule.version) for rule in rules}
        if provided != expected:
            raise ValueError(
                "HistoricalReproduction exige exatamente as Rules e versões que a "
                "Evaluation original registrou em rule_versions, nem mais nem menos."
            )

        ordered_rules = sorted(rules, key=lambda r: (r.code, r.version, str(r.rule_id.value)))
        rule_results = tuple(
            self.engine.evaluate(rule, evaluation.fact_snapshot) for rule in ordered_rules
        )
        reproduced_outcome = aggregate_outcome(rule_results)

        context_hash = compute_context_hash(
            policy_id=evaluation.policy_id,
            policy_version=evaluation.policy_version,
            purpose=evaluation.purpose,
            engine_version=self.engine.engine_version,
            rule_versions=tuple((rule.code, rule.version) for rule in ordered_rules),
            normative_basis_snapshot_digest=(
                evaluation.normative_basis_snapshot.snapshot_digest
                if evaluation.normative_basis_snapshot is not None
                else None
            ),
        )
        evaluation_hash = compute_evaluation_hash(
            context_hash=context_hash,
            subject_id=evaluation.subject_id,
            snapshot_hash=evaluation.fact_snapshot.snapshot_hash,
            rule_results=rule_results,
            outcome=reproduced_outcome,
        )

        divergences: list[str] = []
        context_hash_matches = context_hash == evaluation.context_hash
        if not context_hash_matches:
            divergences.append(
                "context_hash divergente: a semântica reexecutada (Policy/Rules/"
                "motor/finalidade) difere da original."
            )
        evaluation_hash_matches = evaluation_hash == evaluation.evaluation_hash
        if not evaluation_hash_matches:
            divergences.append(
                "evaluation_hash divergente: a reexecução não reproduz o "
                "resultado técnico original."
            )
        outcome_matches = reproduced_outcome == evaluation.outcome
        if not outcome_matches:
            divergences.append(
                f"outcome divergente: original={evaluation.outcome.value}, "
                f"reproduzido={reproduced_outcome.value}."
            )
        return ReproductionReport(
            report_id=TypedId.new("reproduction_report"),
            organization_id=evaluation.organization_id,
            evaluation_id=evaluation.evaluation_id,
            reproduced_at=self.clock.now(),
            context_hash_matches=context_hash_matches,
            evaluation_hash_matches=evaluation_hash_matches,
            outcome_matches=outcome_matches,
            original_outcome=evaluation.outcome,
            reproduced_outcome=reproduced_outcome,
            divergences=tuple(divergences),
            limitations=(
                *evaluation.fact_snapshot.knowledge_limitations,
                *evaluation.normative_limitations,
            ),
        )
