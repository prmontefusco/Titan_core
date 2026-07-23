"""Casos de uso para Execução de Regra Pura e Evaluation (ADR-0036/Passos 6.4 e 6.5)."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from packages.core_domain.evaluation import (
    Evaluation,
    RuleResult,
    RuleResultStatus,
    aggregate_outcome,
    compute_conditions_digest,
    compute_evaluation_hash,
    compute_rule_inputs_hash,
)
from packages.core_domain.facts import FactSnapshot
from packages.core_domain.policy import Policy, PolicyStatus
from packages.core_domain.rule import ConditionOutcome, Rule, RuleCondition
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference

_ACTIONABLE_STATUSES = frozenset({RuleResultStatus.NAO_ATENDIDA, RuleResultStatus.PENDENTE})


@dataclass(frozen=True, slots=True)
class RuleEvaluationEngine:
    """Motor puro e determinístico: mesma Regra + mesmo snapshot => mesmo RuleResult/hash.

    A aplicabilidade decorre da vigência da Regra; a satisfação decorre das evidências
    exigidas e das condições declarativas da Regra sobre os payloads dos Facts. Lógica
    normativa arbitrária pertence ao motor Wasm versionado do ADR-0036.
    """

    engine_version: int = 1

    def evaluate(self, rule: Rule, snapshot: FactSnapshot) -> RuleResult:
        available_evidence_types = frozenset(f.fact_type for f in snapshot.facts)

        inputs_hash = compute_rule_inputs_hash(
            rule_id=rule.rule_id,
            rule_version=rule.version,
            subject_id=snapshot.target_id,
            snapshot_hash=snapshot.snapshot_hash,
            available_evidence_types=tuple(available_evidence_types),
            conditions_digest=compute_conditions_digest(rule.conditions),
        )

        status, reason, missing = self._decide(rule, snapshot, available_evidence_types)

        return RuleResult.create(
            rule_id=rule.rule_id,
            rule_version=rule.version,
            organization_id=rule.organization_id,
            subject_id=snapshot.target_id,
            status=status,
            severity=rule.severity,
            reason=reason,
            evaluated_at=snapshot.as_of,
            snapshot_hash=snapshot.snapshot_hash,
            inputs_hash=inputs_hash,
            corrective_action=rule.corrective_action if status in _ACTIONABLE_STATUSES else "",
            missing_evidence_types=missing,
        )

    def _decide(
        self,
        rule: Rule,
        snapshot: FactSnapshot,
        available_evidence_types: frozenset[str],
    ) -> tuple[RuleResultStatus, str, tuple[str, ...]]:
        # 1. Aplicabilidade temporal: a Regra não vigora no instante do snapshot.
        as_of = snapshot.as_of
        if rule.valid_from is not None and as_of < rule.valid_from:
            return (
                RuleResultStatus.NAO_APLICAVEL,
                f"Regra '{rule.code}' entra em vigor apenas em {rule.valid_from.isoformat()}.",
                (),
            )
        if rule.valid_to is not None and as_of > rule.valid_to:
            return (
                RuleResultStatus.NAO_APLICAVEL,
                f"Regra '{rule.code}' deixou de vigorar em {rule.valid_to.isoformat()}.",
                (),
            )

        # 2. Evidências exigidas ausentes no snapshot => pendência de coleta.
        required = tuple(t.strip().lower() for t in rule.required_evidence_types)
        missing = tuple(t for t in required if t not in available_evidence_types)
        if missing:
            return (
                RuleResultStatus.PENDENTE,
                (
                    f"Regra '{rule.code}' aguarda evidências obrigatórias ausentes: "
                    f"{', '.join(missing)}."
                ),
                missing,
            )

        # 3. Condições normativas declaradas, avaliadas na ordem de declaração.
        return self._decide_conditions(rule, snapshot)

    def _decide_conditions(
        self, rule: Rule, snapshot: FactSnapshot
    ) -> tuple[RuleResultStatus, str, tuple[str, ...]]:
        violated: list[RuleCondition] = []
        absent_facts: list[RuleCondition] = []
        indeterminate: list[tuple[RuleCondition, ConditionOutcome]] = []

        for condition in rule.conditions:
            fact = snapshot.get_latest_fact_by_type(condition.fact_type)
            if fact is None:
                absent_facts.append(condition)
                continue

            outcome = condition.check(fact.payload)
            if outcome is ConditionOutcome.VIOLATED:
                violated.append(condition)
            elif outcome is not ConditionOutcome.SATISFIED:
                indeterminate.append((condition, outcome))

        # Uma violação definitiva basta para reprovar, mesmo havendo lacunas em outras
        # condições: a conjunção já é falsa independentemente do que falta.
        if violated:
            detalhes = "; ".join(c.describe() for c in violated)
            return (
                RuleResultStatus.NAO_ATENDIDA,
                f"Regra '{rule.code}' não atendida. Condições violadas: {detalhes}.",
                (),
            )

        # Lacuna é registrada com razão explícita e nunca convertida em violação.
        if absent_facts:
            tipos = tuple(dict.fromkeys(c.fact_type for c in absent_facts))
            return (
                RuleResultStatus.PENDENTE,
                (
                    f"Regra '{rule.code}' aguarda fatos ausentes para avaliar as condições: "
                    f"{', '.join(tipos)}."
                ),
                tipos,
            )

        if indeterminate:
            detalhes = "; ".join(
                f"{c.describe()} ({outcome.value})" for c, outcome in indeterminate
            )
            return (
                RuleResultStatus.INDETERMINADA,
                (
                    f"Regra '{rule.code}' indeterminada: não foi possível avaliar as condições "
                    f"a partir dos fatos disponíveis: {detalhes}."
                ),
                (),
            )

        if rule.conditions:
            return (
                RuleResultStatus.ATENDIDA,
                (
                    f"Regra '{rule.code}' atendida: evidências exigidas presentes e "
                    f"{len(rule.conditions)} condição(ões) satisfeita(s)."
                ),
                (),
            )

        return (
            RuleResultStatus.ATENDIDA,
            f"Regra '{rule.code}' atendida: todas as evidências exigidas estão presentes.",
            (),
        )


# Rascunho nunca é executável e revogada não produz nova Evaluation; substituída
# permanece executável para permitir reavaliação histórica fiel.
_EVALUABLE_POLICY_STATUSES = frozenset({PolicyStatus.PUBLISHED, PolicyStatus.SUPERSEDED})


class EvaluationRepositoryPort(Protocol):
    def save(self, evaluation: Evaluation) -> None: ...

    def get_by_id(self, evaluation_id: TypedId) -> Evaluation | None: ...

    def list_by_subject(
        self,
        organization_id: OrganizationId,
        subject_id: TypedId,
    ) -> list[Evaluation]: ...


@dataclass(frozen=True, slots=True)
class PolicyEvaluationService:
    """Executa uma Policy inteira sobre um snapshot e preserva o resultado.

    A Evaluation guarda o snapshot completo que a originou, e não apenas seu hash:
    é isso que mantém a avaliação reproduzível depois que os fatos evoluírem.
    """

    engine: RuleEvaluationEngine

    def evaluate_policy(
        self,
        policy: Policy,
        rules: Sequence[Rule],
        snapshot: FactSnapshot,
        purpose: str,
        executor_reference: UniversalReference | None = None,
        evaluated_at: datetime | None = None,
    ) -> Evaluation:
        if policy.status not in _EVALUABLE_POLICY_STATUSES:
            raise ValueError(
                f"Política em '{policy.status.value}' não pode ser avaliada: "
                "apenas políticas publicadas ou substituídas são executáveis."
            )
        if policy.organization_id != snapshot.organization_id:
            raise ValueError("A política e o snapshot devem pertencer à mesma Organization.")

        foreign = [r for r in rules if r.policy_id != policy.policy_id]
        if foreign:
            raise ValueError("Todas as regras avaliadas devem pertencer à política informada.")

        # Ordem de execução estável: o resultado não pode depender da ordem de leitura.
        ordered_rules = sorted(rules, key=lambda r: (r.code, r.version, str(r.rule_id.value)))
        rule_results = tuple(self.engine.evaluate(rule, snapshot) for rule in ordered_rules)

        outcome = aggregate_outcome(rule_results)
        evaluation_hash = compute_evaluation_hash(
            policy_id=policy.policy_id,
            policy_version=policy.version,
            subject_id=snapshot.target_id,
            purpose=purpose.strip(),
            snapshot_hash=snapshot.snapshot_hash,
            rule_results=rule_results,
            outcome=outcome,
            engine_version=self.engine.engine_version,
        )

        return Evaluation(
            evaluation_id=TypedId.new("evaluation"),
            organization_id=policy.organization_id,
            subject_id=snapshot.target_id,
            purpose=purpose.strip(),
            policy_id=policy.policy_id,
            policy_version=policy.version,
            fact_snapshot=snapshot,
            rule_results=rule_results,
            outcome=outcome,
            evaluated_at=evaluated_at or snapshot.as_of,
            engine_version=self.engine.engine_version,
            evaluation_hash=evaluation_hash,
            executor_reference=executor_reference,
            rule_versions=tuple((r.code, r.version) for r in ordered_rules),
        )
