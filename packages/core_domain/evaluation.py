"""Modelo de domínio imutável para Execução de Regra e Evaluation (ADR-0036/Passos 6.4 e 6.5)."""

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from packages.core_domain.facts import FactSnapshot
from packages.core_domain.rule import RuleCondition, SeverityLevel
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference


class RuleResultStatus(Enum):
    ATENDIDA = "atendida"
    NAO_ATENDIDA = "nao_atendida"
    PENDENTE = "pendente"
    NAO_APLICAVEL = "nao_aplicavel"
    INDETERMINADA = "indeterminada"


class EvaluationOutcome(Enum):
    """Resultado técnico agregado da Evaluation, anterior a qualquer Decision.

    Não autoriza operação, não publica conclusão e não substitui DecisionResult.
    """

    CONDICOES_SATISFEITAS = "condicoes_satisfeitas"
    CONDICOES_NAO_SATISFEITAS = "condicoes_nao_satisfeitas"
    INFORMACAO_INSUFICIENTE = "informacao_insuficiente"
    EVIDENCIA_CONFLITANTE = "evidencia_conflitante"
    VALIDACAO_EXTERNA_PENDENTE = "validacao_externa_pendente"
    REVISAO_HUMANA_NECESSARIA = "revisao_humana_necessaria"
    INDETERMINADO = "indeterminado"


def compute_conditions_digest(conditions: Sequence[RuleCondition]) -> str:
    """Digest SHA-256 estável das condições normativas declaradas pela regra."""
    payload = [c.to_dict() for c in conditions]
    raw_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw_bytes).hexdigest()


def compute_rule_inputs_hash(
    rule_id: TypedId,
    rule_version: int,
    subject_id: TypedId,
    snapshot_hash: str,
    available_evidence_types: Sequence[str],
    conditions_digest: str = "",
) -> str:
    """Hash SHA-256 determinístico das entradas relevantes da execução da regra."""
    payload = {
        "rule_id": str(rule_id.value),
        "rule_version": rule_version,
        "subject_id": str(subject_id.value),
        "snapshot_hash": snapshot_hash,
        "available_evidence_types": sorted({t.strip().lower() for t in available_evidence_types}),
        "conditions_digest": conditions_digest,
    }
    raw_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw_bytes).hexdigest()


@dataclass(frozen=True, slots=True)
class RuleResult:
    result_id: TypedId
    rule_id: TypedId
    rule_version: int
    organization_id: OrganizationId
    subject_id: TypedId
    status: RuleResultStatus
    severity: SeverityLevel
    reason: str
    corrective_action: str
    missing_evidence_types: tuple[str, ...]
    evaluated_at: datetime
    snapshot_hash: str
    inputs_hash: str

    def __post_init__(self) -> None:
        if self.result_id.entity_type != "rule_result":
            raise ValueError("result_id deve ser do tipo 'rule_result'.")
        if self.rule_id.entity_type != "rule":
            raise ValueError("rule_id deve ser do tipo 'rule'.")
        if not isinstance(self.rule_version, int) or self.rule_version < 1:
            raise ValueError("rule_version deve ser um número inteiro >= 1.")
        if not isinstance(self.organization_id, OrganizationId):
            raise TypeError("organization_id deve ser OrganizationId.")
        if not isinstance(self.subject_id, TypedId):
            raise TypeError("subject_id deve ser TypedId.")
        if not isinstance(self.status, RuleResultStatus):
            raise TypeError("status deve ser um RuleResultStatus válido.")
        if not isinstance(self.severity, SeverityLevel):
            raise TypeError("severity deve ser um SeverityLevel válido.")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("Todo RuleResult exige justificativa (reason) não vazia.")
        if not isinstance(self.missing_evidence_types, tuple):
            raise TypeError("missing_evidence_types deve ser uma tupla.")
        if not isinstance(self.evaluated_at, datetime):
            raise TypeError("evaluated_at deve ser um datetime.")
        if not isinstance(self.inputs_hash, str) or not self.inputs_hash.strip():
            raise ValueError("inputs_hash deve ser uma string não vazia.")

    @classmethod
    def create(
        cls,
        rule_id: TypedId,
        rule_version: int,
        organization_id: OrganizationId,
        subject_id: TypedId,
        status: RuleResultStatus,
        severity: SeverityLevel,
        reason: str,
        evaluated_at: datetime,
        snapshot_hash: str,
        inputs_hash: str,
        corrective_action: str = "",
        missing_evidence_types: tuple[str, ...] = (),
    ) -> "RuleResult":
        return cls(
            result_id=TypedId.new("rule_result"),
            rule_id=rule_id,
            rule_version=rule_version,
            organization_id=organization_id,
            subject_id=subject_id,
            status=status,
            severity=severity,
            reason=reason.strip(),
            corrective_action=corrective_action.strip(),
            missing_evidence_types=missing_evidence_types,
            evaluated_at=evaluated_at,
            snapshot_hash=snapshot_hash,
            inputs_hash=inputs_hash,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "result_id": str(self.result_id.value),
            "rule_id": str(self.rule_id.value),
            "rule_version": self.rule_version,
            "organization_id": str(self.organization_id.value),
            "subject_id": {
                "entity_type": self.subject_id.entity_type,
                "value": str(self.subject_id.value),
            },
            "status": self.status.value,
            "severity": self.severity.value,
            "reason": self.reason,
            "corrective_action": self.corrective_action,
            "missing_evidence_types": list(self.missing_evidence_types),
            "evaluated_at": self.evaluated_at.isoformat(),
            "snapshot_hash": self.snapshot_hash,
            "inputs_hash": self.inputs_hash,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "RuleResult":
        subject = data["subject_id"]
        return cls(
            result_id=TypedId(entity_type="rule_result", value=UUID(data["result_id"])),
            rule_id=TypedId(entity_type="rule", value=UUID(data["rule_id"])),
            rule_version=data["rule_version"],
            organization_id=OrganizationId(UUID(data["organization_id"])),
            subject_id=TypedId(entity_type=subject["entity_type"], value=UUID(subject["value"])),
            status=RuleResultStatus(data["status"]),
            severity=SeverityLevel(data["severity"]),
            reason=data["reason"],
            corrective_action=data["corrective_action"],
            missing_evidence_types=tuple(data["missing_evidence_types"]),
            evaluated_at=datetime.fromisoformat(data["evaluated_at"]),
            snapshot_hash=data["snapshot_hash"],
            inputs_hash=data["inputs_hash"],
        )


# Precedência de agregação: uma reprovação definitiva prevalece sobre lacunas, pois a
# conjunção das regras já é falsa; entre lacunas, a pendência (acionável) precede a
# indeterminação. Espelha a precedência aplicada dentro de uma única regra.
_OUTCOME_PRECEDENCE: tuple[tuple[RuleResultStatus, EvaluationOutcome], ...] = (
    (RuleResultStatus.NAO_ATENDIDA, EvaluationOutcome.CONDICOES_NAO_SATISFEITAS),
    (RuleResultStatus.PENDENTE, EvaluationOutcome.INFORMACAO_INSUFICIENTE),
    (RuleResultStatus.INDETERMINADA, EvaluationOutcome.INDETERMINADO),
)


def aggregate_outcome(rule_results: Sequence["RuleResult"]) -> EvaluationOutcome:
    """Agrega RuleResults no resultado técnico da Evaluation.

    Ausência de regra aplicável não é conformidade: quando nada foi efetivamente
    verificado, o resultado é `INDETERMINADO`, nunca `CONDICOES_SATISFEITAS`.
    """
    present = {r.status for r in rule_results}
    for status, outcome in _OUTCOME_PRECEDENCE:
        if status in present:
            return outcome
    if RuleResultStatus.ATENDIDA in present:
        return EvaluationOutcome.CONDICOES_SATISFEITAS
    return EvaluationOutcome.INDETERMINADO


def compute_evaluation_hash(
    policy_id: TypedId,
    policy_version: int,
    subject_id: TypedId,
    purpose: str,
    snapshot_hash: str,
    rule_results: Sequence["RuleResult"],
    outcome: EvaluationOutcome,
    engine_version: int,
) -> str:
    """Hash SHA-256 determinístico e reproduzível da Evaluation completa."""
    payload = {
        "policy_id": str(policy_id.value),
        "policy_version": policy_version,
        "subject_id": str(subject_id.value),
        "purpose": purpose,
        "snapshot_hash": snapshot_hash,
        "outcome": outcome.value,
        "engine_version": engine_version,
        # A identidade do RuleResult varia a cada execução e é omitida de propósito:
        # o hash descreve o conteúdo avaliado, não a instância produzida.
        "rule_results": sorted(
            (
                {
                    "rule_id": str(r.rule_id.value),
                    "rule_version": r.rule_version,
                    "status": r.status.value,
                    "inputs_hash": r.inputs_hash,
                }
                for r in rule_results
            ),
            key=lambda item: (item["rule_id"], item["rule_version"]),
        ),
    }
    raw_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw_bytes).hexdigest()


@dataclass(frozen=True, slots=True)
class Evaluation:
    """Execução registrada de uma Policy e suas Rules sobre um snapshot delimitado.

    Preserva o snapshot completo dos fatos junto com os resultados, de modo que a
    avaliação permaneça reproduzível mesmo depois que os fatos evoluírem. Evaluation
    histórica nunca é alterada: mudanças futuras produzem nova Evaluation.
    """

    evaluation_id: TypedId
    organization_id: OrganizationId
    subject_id: TypedId
    purpose: str
    policy_id: TypedId
    policy_version: int
    fact_snapshot: FactSnapshot
    rule_results: tuple[RuleResult, ...]
    outcome: EvaluationOutcome
    evaluated_at: datetime
    engine_version: int
    evaluation_hash: str
    executor_reference: UniversalReference | None = None
    rule_versions: tuple[tuple[str, int], ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.evaluation_id.entity_type != "evaluation":
            raise ValueError("evaluation_id deve ser do tipo 'evaluation'.")
        if self.policy_id.entity_type != "policy":
            raise ValueError("policy_id deve ser do tipo 'policy'.")
        if not isinstance(self.organization_id, OrganizationId):
            raise TypeError("organization_id deve ser OrganizationId.")
        if not isinstance(self.policy_version, int) or self.policy_version < 1:
            raise ValueError("policy_version deve ser um número inteiro >= 1.")
        if not isinstance(self.purpose, str) or not self.purpose.strip():
            raise ValueError("Toda Evaluation exige finalidade (purpose) não vazia.")
        if not isinstance(self.fact_snapshot, FactSnapshot):
            raise TypeError("fact_snapshot deve ser um FactSnapshot.")
        if not isinstance(self.rule_results, tuple):
            raise TypeError("rule_results deve ser uma tupla.")
        if not isinstance(self.outcome, EvaluationOutcome):
            raise TypeError("outcome deve ser um EvaluationOutcome válido.")
        if not isinstance(self.evaluation_hash, str) or not self.evaluation_hash.strip():
            raise ValueError("evaluation_hash deve ser uma string não vazia.")
        if self.fact_snapshot.organization_id != self.organization_id:
            raise ValueError("O snapshot deve pertencer à Organization da Evaluation.")
        if self.fact_snapshot.target_id != self.subject_id:
            raise ValueError("O snapshot deve descrever o Subject da Evaluation.")

    def results_by_status(self, status: RuleResultStatus) -> tuple[RuleResult, ...]:
        return tuple(r for r in self.rule_results if r.status is status)

    def recompute_hash(self) -> str:
        """Recalcula o hash a partir do conteúdo preservado, para auditoria."""
        return compute_evaluation_hash(
            policy_id=self.policy_id,
            policy_version=self.policy_version,
            subject_id=self.subject_id,
            purpose=self.purpose,
            snapshot_hash=self.fact_snapshot.snapshot_hash,
            rule_results=self.rule_results,
            outcome=self.outcome,
            engine_version=self.engine_version,
        )

    def is_reproducible(self) -> bool:
        return self.recompute_hash() == self.evaluation_hash
