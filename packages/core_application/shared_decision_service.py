"""Orquestracao de propostas e revisoes de BuyerPolicy compartilhada."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID

from packages.core_application.evaluation_service import EvaluationRepositoryPort
from packages.core_domain.policy_sharing import (
    SHARED_DECISION_STATUS_PROPOSTA,
    VALID_SHARED_DECISION_REVIEW_DECISIONS,
    SharedDecision,
)
from packages.shared_kernel import OrganizationId, TypedId


class AuthorizationGrantRepositoryPort(Protocol):
    def get_by_id(self, grant_id: UUID) -> Any | None: ...


class SharedDecisionRepositoryPort(Protocol):
    def save(self, decision: SharedDecision) -> None: ...

    def get_by_id(self, decision_id: TypedId) -> SharedDecision | None: ...

    def list_by_policy(self, policy_id: TypedId) -> list[SharedDecision]: ...

    def update_review(
        self,
        decision_id: TypedId,
        *,
        review_decision: str,
        review_content: str,
        reviewed_at: datetime,
        reviewed_by: str,
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class SharedDecisionService:
    """Caso de uso de proposta e revisao sobre uma Evaluation compartilhada."""

    grants: AuthorizationGrantRepositoryPort
    evaluations: EvaluationRepositoryPort
    decisions: SharedDecisionRepositoryPort
    set_organization_context: Callable[[OrganizationId], None]

    def create_proposal(
        self,
        *,
        policy_id: TypedId,
        grant_id: UUID,
        evaluation_id: TypedId,
        proposal_content: str,
        evidence_references: tuple[str, ...],
        proposer_organization_id: OrganizationId,
        created_by: str,
    ) -> SharedDecision:
        grant = self.grants.get_by_id(grant_id)
        if grant is None or grant.policy_id != policy_id:
            raise KeyError("Grant nao encontrado ou nao acessivel.")
        if grant.beneficiary_organization_id != proposer_organization_id:
            raise PermissionError("Apenas a Organization beneficiaria pode criar proposta.")
        if grant.status != "ATIVO" or grant.valid_until <= datetime.now(UTC):
            raise ValueError("Grant inativo, revogado ou expirado.")

        # ADR-0068: a Evaluation da autoavaliacao compartilhada pertence a
        # Organization que avaliou -- a beneficiaria --, e nao a dona da Policy.
        # E sob o contexto dela que a proposta confere a avaliacao que contesta;
        # o comprador revisa a alegacao sem receber o snapshot de facts junto,
        # que e o que a ADR-0065 bloqueia.
        self.set_organization_context(proposer_organization_id)
        evaluation = self.evaluations.get_by_id(evaluation_id)
        if evaluation is None or evaluation.policy_id != policy_id:
            raise KeyError("Evaluation nao encontrada ou nao acessivel.")
        if evaluation.organization_id != proposer_organization_id:
            raise PermissionError("So a propria avaliacao pode ser contestada.")

        now = datetime.now(UTC)
        decision = SharedDecision(
            decision_id=TypedId.new("shared_decision"),
            grant_id=grant.grant_id,
            evaluation_id=evaluation_id,
            policy_id=policy_id,
            proposer_organization_id=proposer_organization_id,
            proposal_content=proposal_content,
            proposal_evidence_references=evidence_references,
            proposed_at=now,
            reviewer_organization_id=grant.owner_organization_id,
            status=SHARED_DECISION_STATUS_PROPOSTA,
            created_by=created_by,
            record_owner_organization_id=grant.owner_organization_id,
        )
        self.decisions.save(decision)
        return decision

    def review_proposal(
        self,
        *,
        decision_id: TypedId,
        policy_id: TypedId,
        review_decision: str,
        review_content: str,
        reviewer_organization_id: OrganizationId,
        reviewed_by: str,
    ) -> SharedDecision:
        if review_decision not in VALID_SHARED_DECISION_REVIEW_DECISIONS:
            raise ValueError("review_decision invalida.")

        current = self.decisions.get_by_id(decision_id)
        if current is None:
            raise KeyError("SharedDecision nao encontrada.")
        if current.policy_id != policy_id:
            raise KeyError("SharedDecision nao encontrada.")
        if current.reviewer_organization_id != reviewer_organization_id:
            raise PermissionError("Apenas a Organization owner do grant pode revisar.")
        if current.status != SHARED_DECISION_STATUS_PROPOSTA:
            raise ValueError("SharedDecision ja revisada.")

        reviewed_at = datetime.now(UTC)
        self.decisions.update_review(
            decision_id,
            review_decision=review_decision,
            review_content=review_content,
            reviewed_at=reviewed_at,
            reviewed_by=reviewed_by,
        )
        updated = self.decisions.get_by_id(decision_id)
        assert updated is not None
        return updated

    def list_for_policy(
        self,
        *,
        policy_id: TypedId,
        organization_id: OrganizationId,
    ) -> list[SharedDecision]:
        decisions = self.decisions.list_by_policy(policy_id)
        return [
            decision
            for decision in decisions
            if organization_id
            in (decision.proposer_organization_id, decision.reviewer_organization_id)
        ]
