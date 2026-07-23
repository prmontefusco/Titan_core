"""Caso de uso para Execução Determinística de uma Regra Pura (ADR-0036/Passo 6.4)."""

from dataclasses import dataclass

from packages.core_domain.evaluation import (
    RuleResult,
    RuleResultStatus,
    compute_conditions_digest,
    compute_rule_inputs_hash,
)
from packages.core_domain.facts import FactSnapshot
from packages.core_domain.rule import ConditionOutcome, Rule, RuleCondition

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
