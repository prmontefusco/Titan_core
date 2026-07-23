"""Modelo de domínio imutável para Decision explicável (ADR-0016/Passo 6.6)."""

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from packages.core_domain.facts import reference_from_dict, reference_to_dict
from packages.core_domain.rule import SeverityLevel
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference


class DecisionResult(Enum):
    """Resultado agregado da Decision.

    Revisão necessária é estado do processo, não resultado final, e por isso não
    aparece aqui.
    """

    APROVADA = "aprovada"
    REJEITADA = "rejeitada"
    APROVADA_COM_RESTRICOES = "aprovada_com_restricoes"
    INDETERMINADA = "indeterminada"


class DecisionReasonCode(Enum):
    """Código estável de razão. É contrato: a mensagem traduz, o código não muda."""

    REGRA_ATENDIDA = "regra_atendida"
    REGRA_NAO_ATENDIDA = "regra_nao_atendida"
    EVIDENCIA_PENDENTE = "evidencia_pendente"
    REGRA_INDETERMINADA = "regra_indeterminada"
    REGRA_NAO_APLICAVEL = "regra_nao_aplicavel"
    NENHUMA_REGRA_APLICAVEL = "nenhuma_regra_aplicavel"


@dataclass(frozen=True, slots=True)
class DecisionReason:
    """Razão estruturada de uma Decision.

    O código é contrato e a mensagem humana é separada, de modo que tradução ou
    redação não invertam a conclusão nem ocultem restrição material.
    """

    code: DecisionReasonCode
    message: str
    rule_code: str = ""
    rule_id: TypedId | None = None
    rule_version: int | None = None
    severity: SeverityLevel | None = None
    corrective_action: str = ""
    missing_evidence_types: tuple[str, ...] = field(default_factory=tuple)
    evidence_references: tuple[UniversalReference, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.code, DecisionReasonCode):
            raise TypeError("code deve ser um DecisionReasonCode válido.")
        if not isinstance(self.message, str) or not self.message.strip():
            raise ValueError("Toda DecisionReason exige mensagem humana não vazia.")
        if self.rule_id is not None and self.rule_id.entity_type != "rule":
            raise ValueError("rule_id deve ser do tipo 'rule'.")
        if not isinstance(self.missing_evidence_types, tuple):
            raise TypeError("missing_evidence_types deve ser uma tupla.")
        if not isinstance(self.evidence_references, tuple):
            raise TypeError("evidence_references deve ser uma tupla.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code.value,
            "message": self.message,
            "rule_code": self.rule_code,
            "rule_id": str(self.rule_id.value) if self.rule_id is not None else None,
            "rule_version": self.rule_version,
            "severity": self.severity.value if self.severity is not None else None,
            "corrective_action": self.corrective_action,
            "missing_evidence_types": list(self.missing_evidence_types),
            "evidence_references": [reference_to_dict(r) for r in self.evidence_references],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "DecisionReason":
        raw_rule_id = data.get("rule_id")
        raw_severity = data.get("severity")
        references = tuple(
            ref
            for ref in (reference_from_dict(item) for item in data.get("evidence_references", []))
            if ref is not None
        )
        return cls(
            code=DecisionReasonCode(data["code"]),
            message=data["message"],
            rule_code=data.get("rule_code", ""),
            rule_id=(
                TypedId(entity_type="rule", value=UUID(raw_rule_id))
                if raw_rule_id is not None
                else None
            ),
            rule_version=data.get("rule_version"),
            severity=SeverityLevel(raw_severity) if raw_severity is not None else None,
            corrective_action=data.get("corrective_action", ""),
            missing_evidence_types=tuple(data.get("missing_evidence_types", [])),
            evidence_references=references,
        )


def compute_decision_hash(
    evaluation_hash: str,
    policy_id: TypedId,
    policy_version: int,
    subject_id: TypedId,
    purpose: str,
    result: DecisionResult,
    reasons: Sequence[DecisionReason],
    engine_version: int,
) -> str:
    """Digest SHA-256 determinístico da Decision.

    Descreve a conclusão e sua fundamentação, permitindo reconstruir a Decision a
    partir da Evaluation preservada e confirmar igualdade.
    """
    payload = {
        "evaluation_hash": evaluation_hash,
        "policy_id": str(policy_id.value),
        "policy_version": policy_version,
        "subject_id": str(subject_id.value),
        "purpose": purpose,
        "result": result.value,
        "engine_version": engine_version,
        "reasons": sorted(
            (
                {
                    "code": r.code.value,
                    "rule_code": r.rule_code,
                    "rule_id": str(r.rule_id.value) if r.rule_id is not None else "",
                    "rule_version": r.rule_version,
                }
                for r in reasons
            ),
            key=lambda item: (item["code"], item["rule_code"], item["rule_id"]),
        ),
    }
    raw_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw_bytes).hexdigest()


@dataclass(frozen=True, slots=True)
class Decision:
    """Conclusão registrada produzida a partir de uma Evaluation.

    Decision histórica nunca muda: nova informação exige nova Evaluation e nova
    Decision. Não existe resultado sem justificativa.
    """

    decision_id: TypedId
    organization_id: OrganizationId
    subject_id: TypedId
    purpose: str
    evaluation_id: TypedId
    evaluation_hash: str
    policy_id: TypedId
    policy_version: int
    result: DecisionResult
    reasons: tuple[DecisionReason, ...]
    snapshot_hash: str
    issued_at: datetime
    engine_version: int
    decision_hash: str
    affected_subjects: tuple[UniversalReference, ...] = field(default_factory=tuple)
    evidence_references: tuple[UniversalReference, ...] = field(default_factory=tuple)
    corrective_actions: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.decision_id.entity_type != "decision":
            raise ValueError("decision_id deve ser do tipo 'decision'.")
        if self.evaluation_id.entity_type != "evaluation":
            raise ValueError("evaluation_id deve ser do tipo 'evaluation'.")
        if self.policy_id.entity_type != "policy":
            raise ValueError("policy_id deve ser do tipo 'policy'.")
        if not isinstance(self.organization_id, OrganizationId):
            raise TypeError("organization_id deve ser OrganizationId.")
        if not isinstance(self.result, DecisionResult):
            raise TypeError("result deve ser um DecisionResult válido.")
        if not isinstance(self.purpose, str) or not self.purpose.strip():
            raise ValueError("Toda Decision exige finalidade (purpose) não vazia.")
        if not isinstance(self.policy_version, int) or self.policy_version < 1:
            raise ValueError("policy_version deve ser um número inteiro >= 1.")
        if not isinstance(self.reasons, tuple):
            raise TypeError("reasons deve ser uma tupla.")
        # Invariante central da explicabilidade: não existe conclusão sem razão.
        if not self.reasons:
            raise ValueError("Toda Decision exige ao menos uma DecisionReason.")
        if not isinstance(self.decision_hash, str) or not self.decision_hash.strip():
            raise ValueError("decision_hash deve ser uma string não vazia.")

    def reasons_by_code(self, code: DecisionReasonCode) -> tuple[DecisionReason, ...]:
        return tuple(r for r in self.reasons if r.code is code)

    def recompute_hash(self) -> str:
        return compute_decision_hash(
            evaluation_hash=self.evaluation_hash,
            policy_id=self.policy_id,
            policy_version=self.policy_version,
            subject_id=self.subject_id,
            purpose=self.purpose,
            result=self.result,
            reasons=self.reasons,
            engine_version=self.engine_version,
        )

    def is_reproducible(self) -> bool:
        return self.recompute_hash() == self.decision_hash
