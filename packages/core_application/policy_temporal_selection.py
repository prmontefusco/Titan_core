"""Seleção multitemporal explícita de Policy (NEXT-02, Corte 1)."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from packages.core_domain.policy import Policy, PolicyStatus
from packages.shared_kernel import OrganizationId
from packages.shared_kernel.temporal import require_utc


class PolicySelectionOutcome(StrEnum):
    SELECTED = "SELECTED"
    NOT_FOUND = "NOT_FOUND"
    AMBIGUOUS = "AMBIGUOUS"
    TEMPORAL_GAP = "TEMPORAL_GAP"


class PolicySelectionReason(StrEnum):
    POLITICA_APLICAVEL_AUSENTE = "POLITICA_APLICAVEL_AUSENTE"
    MULTIPLAS_POLITICAS_APLICAVEIS = "MULTIPLAS_POLITICAS_APLICAVEIS"
    LACUNA_TEMPORAL = "LACUNA_TEMPORAL"


@dataclass(frozen=True, slots=True)
class PolicyTemporalCandidate:
    """Entrada transitória; não é entidade nem fonte paralela de Policy."""

    policy: Policy
    purpose: str
    known_at: datetime
    knowledge_basis: str

    def __post_init__(self) -> None:
        require_utc(self.known_at, field_name="known_at")
        if not self.purpose.strip():
            raise ValueError("purpose não pode ser vazio.")
        if not self.knowledge_basis.strip():
            raise ValueError("knowledge_basis não pode ser vazio.")


@dataclass(frozen=True, slots=True)
class PolicySelectionRequest:
    organization_id: OrganizationId
    policy_code: str
    purpose: str
    reference_time: datetime
    knowledge_cutoff: datetime

    def __post_init__(self) -> None:
        require_utc(self.reference_time, field_name="reference_time")
        require_utc(self.knowledge_cutoff, field_name="knowledge_cutoff")
        if not self.policy_code.strip():
            raise ValueError("policy_code não pode ser vazio.")
        if not self.purpose.strip():
            raise ValueError("purpose não pode ser vazio.")


@dataclass(frozen=True, slots=True)
class PolicySelectionResult:
    outcome: PolicySelectionOutcome
    selected_policy: Policy | None
    candidates: tuple[Policy, ...]
    reason_codes: tuple[PolicySelectionReason, ...]
    reference_time: datetime
    knowledge_cutoff: datetime
    temporal_rule_version: int = 1
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PolicyTemporalResolver:
    def resolve(
        self,
        request: PolicySelectionRequest,
        candidates: tuple[PolicyTemporalCandidate, ...],
    ) -> PolicySelectionResult:
        matching = tuple(
            candidate
            for candidate in candidates
            if candidate.policy.organization_id == request.organization_id
            and candidate.policy.code == request.policy_code.strip().lower()
            and candidate.purpose == request.purpose.strip()
        )
        if not matching:
            return self._result(
                request,
                PolicySelectionOutcome.NOT_FOUND,
                reason=PolicySelectionReason.POLITICA_APLICAVEL_AUSENTE,
            )

        eligible = tuple(
            candidate
            for candidate in matching
            if candidate.policy.status in {PolicyStatus.PUBLISHED, PolicyStatus.SUPERSEDED}
            and candidate.known_at <= request.knowledge_cutoff
            and self._valid_at(candidate.policy, request.reference_time)
        )
        policies = tuple(candidate.policy for candidate in eligible)
        if not policies:
            return self._result(
                request,
                PolicySelectionOutcome.TEMPORAL_GAP,
                reason=PolicySelectionReason.LACUNA_TEMPORAL,
            )
        if len(policies) > 1:
            return self._result(
                request,
                PolicySelectionOutcome.AMBIGUOUS,
                candidates=policies,
                reason=PolicySelectionReason.MULTIPLAS_POLITICAS_APLICAVEIS,
            )
        return self._result(
            request,
            PolicySelectionOutcome.SELECTED,
            selected_policy=policies[0],
            candidates=policies,
        )

    @staticmethod
    def _valid_at(policy: Policy, reference_time: datetime) -> bool:
        return (policy.valid_from is None or policy.valid_from <= reference_time) and (
            policy.valid_to is None or reference_time < policy.valid_to
        )

    @staticmethod
    def _result(
        request: PolicySelectionRequest,
        outcome: PolicySelectionOutcome,
        *,
        selected_policy: Policy | None = None,
        candidates: tuple[Policy, ...] = (),
        reason: PolicySelectionReason | None = None,
    ) -> PolicySelectionResult:
        return PolicySelectionResult(
            outcome=outcome,
            selected_policy=selected_policy,
            candidates=candidates,
            reason_codes=() if reason is None else (reason,),
            reference_time=request.reference_time,
            knowledge_cutoff=request.knowledge_cutoff,
        )
