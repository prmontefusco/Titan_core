"""Caso de uso para emissão de Decision explicável a partir de Evaluation (Passo 6.6)."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from packages.core_domain.decision import (
    Decision,
    DecisionReason,
    DecisionReasonCode,
    DecisionResult,
    compute_decision_hash,
)
from packages.core_domain.evaluation import Evaluation, EvaluationOutcome, RuleResultStatus
from packages.core_domain.rule import SeverityLevel
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference

# Severidades que impedem aprovação. As demais podem virar restrição declarada em
# vez de reprovação total.
_BLOCKING_SEVERITIES = frozenset({SeverityLevel.BLOCKING, SeverityLevel.CRITICAL})

_STATUS_TO_REASON_CODE: dict[RuleResultStatus, DecisionReasonCode] = {
    RuleResultStatus.ATENDIDA: DecisionReasonCode.REGRA_ATENDIDA,
    RuleResultStatus.NAO_ATENDIDA: DecisionReasonCode.REGRA_NAO_ATENDIDA,
    RuleResultStatus.PENDENTE: DecisionReasonCode.EVIDENCIA_PENDENTE,
    RuleResultStatus.INDETERMINADA: DecisionReasonCode.REGRA_INDETERMINADA,
    RuleResultStatus.NAO_APLICAVEL: DecisionReasonCode.REGRA_NAO_APLICAVEL,
}


class DecisionRepositoryPort(Protocol):
    def save(self, decision: Decision) -> None: ...

    def get_by_id(self, decision_id: TypedId) -> Decision | None: ...

    def list_by_subject(
        self,
        organization_id: OrganizationId,
        subject_id: TypedId,
    ) -> list[Decision]: ...


@dataclass(frozen=True, slots=True)
class DecisionService:
    """Deriva a Decision de uma Evaluation preservada, de forma determinística.

    A Decision não reavalia nada: apenas traduz o resultado técnico da Evaluation
    em conclusão explicável. Reexecutar sobre a mesma Evaluation reproduz o mesmo
    resultado e o mesmo digest.
    """

    engine_version: int = 1

    def decide(
        self,
        evaluation: Evaluation,
        issued_at: datetime | None = None,
    ) -> Decision:
        # Uma Evaluation adulterada não pode fundamentar conclusão alguma.
        if not evaluation.is_reproducible():
            raise ValueError(
                "Evaluation não reproduzível: o conteúdo preservado não confere "
                "com o hash registrado."
            )

        result = self._derive_result(evaluation)
        reasons = self._build_reasons(evaluation)
        corrective_actions = tuple(
            dict.fromkeys(r.corrective_action for r in reasons if r.corrective_action)
        )
        evidence_references = self._collect_evidence_references(evaluation)

        decision_hash = compute_decision_hash(
            evaluation_hash=evaluation.evaluation_hash,
            policy_id=evaluation.policy_id,
            policy_version=evaluation.policy_version,
            subject_id=evaluation.subject_id,
            purpose=evaluation.purpose,
            result=result,
            reasons=reasons,
            engine_version=self.engine_version,
        )

        return Decision(
            decision_id=TypedId.new("decision"),
            organization_id=evaluation.organization_id,
            subject_id=evaluation.subject_id,
            purpose=evaluation.purpose,
            evaluation_id=evaluation.evaluation_id,
            evaluation_hash=evaluation.evaluation_hash,
            policy_id=evaluation.policy_id,
            policy_version=evaluation.policy_version,
            result=result,
            reasons=reasons,
            snapshot_hash=evaluation.fact_snapshot.snapshot_hash,
            issued_at=issued_at or evaluation.evaluated_at,
            engine_version=self.engine_version,
            decision_hash=decision_hash,
            affected_subjects=(
                UniversalReference(
                    target_id=evaluation.subject_id,
                    organization_id=evaluation.organization_id,
                    contract_version=1,
                ),
            ),
            evidence_references=evidence_references,
            corrective_actions=corrective_actions,
        )

    def _derive_result(self, evaluation: Evaluation) -> DecisionResult:
        outcome = evaluation.outcome
        if outcome is EvaluationOutcome.CONDICOES_SATISFEITAS:
            return DecisionResult.APROVADA
        if outcome is EvaluationOutcome.CONDICOES_NAO_SATISFEITAS:
            reprovadas = evaluation.results_by_status(RuleResultStatus.NAO_ATENDIDA)
            if any(r.severity in _BLOCKING_SEVERITIES for r in reprovadas):
                return DecisionResult.REJEITADA
            # Somente descumprimentos informativos ou de alerta: a conclusão é
            # aprovação com restrição declarada, nunca aprovação limpa.
            return DecisionResult.APROVADA_COM_RESTRICOES
        # Informação insuficiente, evidência conflitante, validação externa
        # pendente e revisão humana não são conclusões: são ausência de conclusão.
        return DecisionResult.INDETERMINADA

    def _build_reasons(self, evaluation: Evaluation) -> tuple[DecisionReason, ...]:
        if not evaluation.rule_results:
            return (
                DecisionReason(
                    code=DecisionReasonCode.NENHUMA_REGRA_APLICAVEL,
                    message=(
                        "Nenhuma regra foi executada para esta política: não há "
                        "conclusão de conformidade a declarar."
                    ),
                ),
            )

        reasons: list[DecisionReason] = []
        for result in evaluation.rule_results:
            reasons.append(
                DecisionReason(
                    code=_STATUS_TO_REASON_CODE[result.status],
                    message=result.reason,
                    rule_code=result.rule_code,
                    rule_id=result.rule_id,
                    rule_version=result.rule_version,
                    severity=result.severity,
                    corrective_action=result.corrective_action,
                    missing_evidence_types=result.missing_evidence_types,
                )
            )
        return tuple(reasons)

    def _collect_evidence_references(
        self, evaluation: Evaluation
    ) -> tuple[UniversalReference, ...]:
        """Reúne as evidências que sustentam os fatos avaliados, sem duplicar.

        Os fatos do snapshot já estão em ordem determinística, então a ordem das
        referências também é estável.
        """
        references: list[UniversalReference] = []
        for fact in evaluation.fact_snapshot.facts:
            reference = fact.source_reference
            if reference is not None and reference not in references:
                references.append(reference)
        return tuple(references)
