"""Modelo de domínio imutável para Execução de Regra Pura (ADR-0036/Passo 6.4)."""

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from packages.core_domain.rule import RuleCondition, SeverityLevel
from packages.shared_kernel import OrganizationId, TypedId


class RuleResultStatus(Enum):
    ATENDIDA = "atendida"
    NAO_ATENDIDA = "nao_atendida"
    PENDENTE = "pendente"
    NAO_APLICAVEL = "nao_aplicavel"
    INDETERMINADA = "indeterminada"


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
