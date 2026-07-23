"""Serviço de aplicação para governança humana de decisões (ADR-0016)."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from packages.core_domain.decision import Decision, DecisionResult
from packages.core_domain.decision_governance import (
    ContestationRecord,
    DecisionAuthorityProfile,
    DecisionOverride,
    DecisionProposal,
    GovernanceStatus,
)
from packages.core_domain.evaluation import Evaluation
from packages.shared_kernel import TypedId, UniversalReference


class DecisionGovernanceRepositoryPort(Protocol):
    def save_proposal(self, proposal: DecisionProposal) -> None: ...
    def get_proposal(self, proposal_id: TypedId) -> DecisionProposal | None: ...

    def save_override(self, override: DecisionOverride) -> None: ...
    def get_override(self, override_id: TypedId) -> DecisionOverride | None: ...

    def save_contestation(self, contestation: ContestationRecord) -> None: ...
    def get_contestation(self, contestation_id: TypedId) -> ContestationRecord | None: ...


@dataclass(frozen=True, slots=True)
class DecisionGovernanceService:
    """Orquestra propostas de decisão, intervenções autorizadas (overrides) e contestações."""

    repository: DecisionGovernanceRepositoryPort | None = None

    def create_proposal(
        self,
        evaluation: Evaluation,
        proposed_result: DecisionResult,
        created_at: datetime | None = None,
    ) -> DecisionProposal:
        now = created_at or datetime.now(UTC)
        proposal = DecisionProposal(
            proposal_id=TypedId.new("decision_proposal"),
            organization_id=evaluation.organization_id,
            evaluation_id=evaluation.evaluation_id,
            proposed_result=proposed_result,
            justification_required=True,
            status=GovernanceStatus.PENDENTE,
            created_at=now,
        )
        if self.repository is not None:
            self.repository.save_proposal(proposal)
        return proposal

    def apply_override(
        self,
        original_decision: Decision,
        authority_profile: DecisionAuthorityProfile,
        new_result: DecisionResult,
        mandatory_reason: str,
        applied_at: datetime | None = None,
    ) -> DecisionOverride:
        now = applied_at or datetime.now(UTC)

        if original_decision.organization_id != authority_profile.organization_id:
            raise ValueError(
                "A autoridade credenciada deve pertencer à mesma Organization da decisão."
            )

        override = DecisionOverride(
            override_id=TypedId.new("decision_override"),
            organization_id=original_decision.organization_id,
            original_decision_id=original_decision.decision_id,
            authority_profile=authority_profile,
            new_result=new_result,
            mandatory_reason=mandatory_reason,
            applied_at=now,
        )

        if self.repository is not None:
            self.repository.save_override(override)
        return override

    def file_contestation(
        self,
        decision: Decision,
        contested_by: UniversalReference,
        grounds_description: str,
        filed_at: datetime | None = None,
    ) -> ContestationRecord:
        now = filed_at or datetime.now(UTC)
        contestation = ContestationRecord(
            contestation_id=TypedId.new("contestation"),
            organization_id=decision.organization_id,
            decision_id=decision.decision_id,
            contested_by=contested_by,
            grounds_description=grounds_description,
            status=GovernanceStatus.PENDENTE,
            filed_at=now,
        )
        if self.repository is not None:
            self.repository.save_contestation(contestation)
        return contestation
