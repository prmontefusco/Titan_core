"""Modelo de domínio para governança humana de decisões (ADR-0016).

Propostas, overrides e contestações de decisões automatizadas.

ou sofrer intervenção autorizada (override). Toda intervenção exige perfil de
autoridade credenciada e razão justificada, preservando a decisão original intacta.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from packages.core_domain.decision import DecisionResult
from packages.core_domain.decision_authority import DecisionEmissionMethod
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference
from packages.shared_kernel.temporal import require_utc


class GovernanceStatus(StrEnum):
    PENDENTE = "PENDENTE"
    APROVADA = "APROVADA"
    REJEITADA = "REJEITADA"
    CANCELADA = "CANCELADA"


@dataclass(frozen=True, slots=True)
class DecisionAuthorityProfile:
    """Perfil resolvido pelo servidor para emitir Decision oficial."""

    authority_id: TypedId
    organization_id: OrganizationId
    principal_reference: UniversalReference
    role_name: str
    purpose: str
    emission_method: DecisionEmissionMethod = DecisionEmissionMethod.HUMAN
    approvals_required: int = 0
    max_delegated_severity: str = "CRITICAL"
    is_active: bool = True
    valid_from: datetime | None = None
    valid_to: datetime | None = None

    def __post_init__(self) -> None:
        if self.authority_id.entity_type != "authority_profile":
            raise ValueError("authority_id deve ser do tipo 'authority_profile'.")
        if not isinstance(self.organization_id, OrganizationId):
            raise TypeError("organization_id deve ser OrganizationId.")
        if not isinstance(self.role_name, str) or not self.role_name.strip():
            raise ValueError("role_name deve ser uma string não vazia.")
        if not isinstance(self.purpose, str) or not self.purpose.strip():
            raise ValueError("purpose deve ser uma string não vazia.")
        if self.approvals_required < 0:
            raise ValueError("approvals_required não pode ser negativo.")
        if self.valid_from is not None:
            require_utc(self.valid_from, field_name="valid_from")
        if self.valid_to is not None:
            require_utc(self.valid_to, field_name="valid_to")
        if (
            self.valid_from is not None
            and self.valid_to is not None
            and self.valid_to < self.valid_from
        ):
            raise ValueError("valid_to não pode ser anterior a valid_from.")

    def can_issue_at(
        self,
        issued_at: datetime,
        *,
        expected_method: DecisionEmissionMethod,
    ) -> bool:
        require_utc(issued_at, field_name="issued_at")
        if not self.is_active or self.emission_method is not expected_method:
            return False
        if self.valid_from is not None and issued_at < self.valid_from:
            return False
        if self.valid_to is not None and issued_at > self.valid_to:
            return False
        return self.approvals_required == 0


@dataclass(frozen=True, slots=True)
class DecisionProposal:
    """Proposta de decisão gerada quando a avaliação exige revisão humana (ADR-0016)."""

    proposal_id: TypedId
    organization_id: OrganizationId
    evaluation_id: TypedId
    proposed_result: DecisionResult
    justification_required: bool
    status: GovernanceStatus
    created_at: datetime
    reviewed_at: datetime | None = None
    reviewer_authority_id: TypedId | None = None

    def __post_init__(self) -> None:
        if self.proposal_id.entity_type != "decision_proposal":
            raise ValueError("proposal_id deve ser do tipo 'decision_proposal'.")
        if self.evaluation_id.entity_type != "evaluation":
            raise ValueError("evaluation_id deve ser do tipo 'evaluation'.")
        if not isinstance(self.organization_id, OrganizationId):
            raise TypeError("organization_id deve ser OrganizationId.")
        require_utc(self.created_at, field_name="created_at")
        if self.reviewed_at is not None:
            require_utc(self.reviewed_at, field_name="reviewed_at")


@dataclass(frozen=True, slots=True)
class DecisionOverride:
    """Intervenção autorizada (override) sobre uma decisão automatizada anterior."""

    override_id: TypedId
    organization_id: OrganizationId
    original_decision_id: TypedId
    authority_profile: DecisionAuthorityProfile
    new_result: DecisionResult
    mandatory_reason: str
    applied_at: datetime

    def __post_init__(self) -> None:
        if self.override_id.entity_type != "decision_override":
            raise ValueError("override_id deve ser do tipo 'decision_override'.")
        if self.original_decision_id.entity_type != "decision":
            raise ValueError("original_decision_id deve ser do tipo 'decision'.")
        if not isinstance(self.organization_id, OrganizationId):
            raise TypeError("organization_id deve ser OrganizationId.")
        if not isinstance(self.mandatory_reason, str) or not self.mandatory_reason.strip():
            raise ValueError("Toda intervenção (override) exige razão obrigatória não vazia.")
        if not self.authority_profile.is_active:
            raise ValueError("A autoridade credenciada deve estar ativa para aplicar override.")
        require_utc(self.applied_at, field_name="applied_at")


@dataclass(frozen=True, slots=True)
class ContestationRecord:
    """Registro formal de contestação emitido por sujeito ou organização afetada."""

    contestation_id: TypedId
    organization_id: OrganizationId
    decision_id: TypedId
    contested_by: UniversalReference
    grounds_description: str
    status: GovernanceStatus
    filed_at: datetime
    resolved_at: datetime | None = None
    resolution_notes: str = ""

    def __post_init__(self) -> None:
        if self.contestation_id.entity_type != "contestation":
            raise ValueError("contestation_id deve ser do tipo 'contestation'.")
        if self.decision_id.entity_type != "decision":
            raise ValueError("decision_id deve ser do tipo 'decision'.")
        if not isinstance(self.organization_id, OrganizationId):
            raise TypeError("organization_id deve ser OrganizationId.")
        if not isinstance(self.grounds_description, str) or not self.grounds_description.strip():
            raise ValueError("Toda contestação exige descrição dos fundamentos.")
        require_utc(self.filed_at, field_name="filed_at")
        if self.resolved_at is not None:
            require_utc(self.resolved_at, field_name="resolved_at")
