"""Contrato de execução determinística e isolada de Rules (ADR-0050).

`RuleExecutionContext` delimita o que uma execução pode enxergar; falha técnica
classificada substitui exceção crua não classificada, sem nunca virar `RuleResult`
conclusivo — misturar as duas faria uma indisponibilidade parecer conformidade.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from packages.shared_kernel import OrganizationId, TypedId


class TechnicalFailureCategory(Enum):
    """Categoria técnica de uma tentativa de execução (ADR-0050 §11).

    Vocabulário de aplicação, não enum persistido do Core: a própria ADR-0050 diz
    que sua persistência genérica exige definição formal própria no DOMAIN.md.
    """

    SUCCESS = "success"
    TIMEOUT = "timeout"
    RESOURCE_LIMIT = "resource_limit"
    INVALID_INPUT = "invalid_input"
    RUNTIME_ERROR = "runtime_error"
    CONTRACT_VIOLATION = "contract_violation"
    UNSUPPORTED_VERSION = "unsupported_version"


class RuleExecutionFailure(Exception):
    """Falha técnica classificada durante a execução de uma Rule.

    Nunca produz `RuleResult`: resultado normativo e falha técnica são conclusões
    distintas (ADR-0050 §11), e um `TIMEOUT`/`RUNTIME_ERROR` jamais deve virar
    `NAO_ATENDIDA` por conveniência de quem chama.
    """

    def __init__(self, category: TechnicalFailureCategory, message: str) -> None:
        super().__init__(message)
        self.category = category
        self.message = message


@dataclass(frozen=True, slots=True)
class RuleExecutionContext:
    """Contrato delimitado de uma execução de Rule (ADR-0050 §6).

    Contrato de aplicação, não entidade normativa persistida do Core — a própria
    ADR-0050 declara isso explicitamente para esta fase ("não nova entidade
    normativa persistida do Core nesta fase").
    """

    rule_id: TypedId
    rule_version: int
    organization_id: OrganizationId
    subject_id: TypedId
    snapshot_hash: str
    reference_time: datetime
    knowledge_cutoff: datetime
    engine_version: int
    policy_id: TypedId | None = None
    policy_version: int | None = None
    purpose: str | None = None
    max_conditions_evaluated: int | None = None

    def __post_init__(self) -> None:
        if self.rule_id.entity_type != "rule":
            raise ValueError("rule_id deve ser do tipo 'rule'.")
        if not isinstance(self.rule_version, int) or self.rule_version < 1:
            raise ValueError("rule_version deve ser um número inteiro >= 1.")
        if not isinstance(self.organization_id, OrganizationId):
            raise TypeError("organization_id deve ser OrganizationId.")
        if not isinstance(self.subject_id, TypedId):
            raise TypeError("subject_id deve ser TypedId.")
        if not isinstance(self.snapshot_hash, str) or not self.snapshot_hash.strip():
            raise ValueError("snapshot_hash deve ser uma string não vazia.")
        if not isinstance(self.reference_time, datetime):
            raise TypeError("reference_time deve ser um datetime.")
        if not isinstance(self.knowledge_cutoff, datetime):
            raise TypeError("knowledge_cutoff deve ser um datetime.")
        if self.policy_id is not None and self.policy_id.entity_type != "policy":
            raise ValueError("policy_id, quando informado, deve ser do tipo 'policy'.")
        if self.max_conditions_evaluated is not None and self.max_conditions_evaluated < 0:
            raise ValueError("max_conditions_evaluated não pode ser negativo.")
