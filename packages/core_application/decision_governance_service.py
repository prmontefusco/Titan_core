"""Serviço de aplicação para governança humana de decisões (ADR-0016, ADR-0054)."""

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Protocol

from packages.core_application.decision_service import DecisionService
from packages.core_domain.decision import Decision, DecisionResult
from packages.core_domain.decision_authority import DecisionEmissionMethod
from packages.core_domain.decision_governance import (
    ContestationRecord,
    DecisionAuthorityProfile,
    DecisionOverride,
    DecisionProposal,
    DecisionReview,
    GovernanceStatus,
    ReviewConclusion,
)
from packages.core_domain.evaluation import Evaluation
from packages.shared_kernel import TypedId, UniversalReference


class DecisionGovernanceRepositoryPort(Protocol):
    def save_proposal(self, proposal: DecisionProposal) -> None: ...
    def get_proposal(self, proposal_id: TypedId) -> DecisionProposal | None: ...

    def save_review(self, review: DecisionReview) -> None: ...
    def get_review(self, review_id: TypedId) -> DecisionReview | None: ...
    def list_reviews_by_proposal(self, proposal_id: TypedId) -> list[DecisionReview]: ...

    def save_override(self, override: DecisionOverride) -> None: ...
    def get_override(self, override_id: TypedId) -> DecisionOverride | None: ...

    def save_contestation(self, contestation: ContestationRecord) -> None: ...
    def get_contestation(self, contestation_id: TypedId) -> ContestationRecord | None: ...


@dataclass(frozen=True, slots=True)
class DecisionGovernanceService:
    """Orquestra propostas de decisão, revisão humana, overrides e contestações.

    Persistência é opcional para preservar o uso em memória nos testes de domínio,
    mas quando existe permite revalidar a trilha de proposta/revisão sem depender
    do estado corrente do chamador.
    """

    repository: DecisionGovernanceRepositoryPort | None = None
    decision_service: DecisionService = DecisionService()

    def create_proposal(
        self,
        evaluation: Evaluation,
        created_at: datetime | None = None,
    ) -> DecisionProposal:
        """Cria a DecisionProposal a partir de uma Evaluation (ADR-0054 §5).

        Usa a mesma derivação de resultado e razões que `DecisionService.decide()`
        usaria para emissão automática -- a proposta mostra ao revisor exatamente
        o que o motor concluiria, sem emitir Decision oficial.
        """
        if not evaluation.is_reproducible():
            raise ValueError(
                "Evaluation não reproduzível: o conteúdo preservado não confere "
                "com o hash registrado."
            )
        now = created_at or datetime.now(UTC)
        proposal = DecisionProposal(
            proposal_id=TypedId.new("decision_proposal"),
            organization_id=evaluation.organization_id,
            evaluation_id=evaluation.evaluation_id,
            evaluation_hash=evaluation.evaluation_hash,
            proposed_result=self.decision_service.derive_result(evaluation),
            proposed_reasons=self.decision_service.build_reasons(evaluation),
            purpose=evaluation.purpose,
            justification_required=True,
            created_at=now,
        )
        if self.repository is not None:
            self.repository.save_proposal(proposal)
        return proposal

    def record_review(
        self,
        proposal: DecisionProposal,
        reviewer_reference: UniversalReference,
        reviewer_authority: DecisionAuthorityProfile,
        conclusion: ReviewConclusion,
        reasoning: str,
        reviewed_at: datetime | None = None,
    ) -> DecisionReview:
        """Registra a conclusão de um revisor sobre uma proposta (ADR-0054 §6).

        Autoridade de revisar não implica autoridade de emitir (ADR-0053
        invariante 7) -- `reviewer_authority` só precisa pertencer à mesma
        Organization da proposta; validar que ela pode *emitir* fica a cargo de
        `emit_after_approval`, no momento da emissão.
        """
        if reviewer_authority.organization_id != proposal.organization_id:
            raise ValueError(
                "A autoridade revisora deve pertencer à mesma Organization da proposta."
            )
        now = reviewed_at or datetime.now(UTC)
        review = DecisionReview(
            review_id=TypedId.new("decision_review"),
            organization_id=proposal.organization_id,
            proposal_id=proposal.proposal_id,
            reviewer_reference=reviewer_reference,
            reviewer_authority_id=reviewer_authority.authority_id,
            conclusion=conclusion,
            reasoning=reasoning.strip(),
            reviewed_at=now,
        )
        if self.repository is not None:
            self.repository.save_review(review)
        return review

    def emit_after_approval(
        self,
        evaluation: Evaluation,
        proposal: DecisionProposal,
        review: DecisionReview,
        authority_profile: DecisionAuthorityProfile,
        issued_at: datetime | None = None,
    ) -> Decision:
        return self.emit_after_approvals(
            evaluation=evaluation,
            proposal=proposal,
            reviews=[review],
            authority_profile=authority_profile,
            issued_at=issued_at,
        )

    def emit_after_approvals(
        self,
        evaluation: Evaluation,
        proposal: DecisionProposal,
        reviews: list[DecisionReview],
        authority_profile: DecisionAuthorityProfile,
        issued_at: datetime | None = None,
    ) -> Decision:
        """Emite a Decision humana depois de uma DecisionReview aprovadora.

        Fecha o ciclo da ADR-0054 §3: Evaluation -> DecisionProposal -> uma ou
        mais DecisionReviews -> revalidação -> Decision autorizada. Revalida que
        as reviews referenciam exatamente esta proposta, que a proposta referencia
        exatamente esta Evaluation (pelo hash, não só pelo id), que só há
        aprovações e que a quantidade mínima exigida foi satisfeita.
        """
        if proposal.evaluation_id != evaluation.evaluation_id:
            raise ValueError("A proposta não referencia esta Evaluation.")
        if proposal.evaluation_hash != evaluation.evaluation_hash:
            raise ValueError(
                "A Evaluation mudou desde que a proposta foi criada: material "
                "diferente exige nova proposta e nova revisão, não reaproveitamento."
            )
        self._validate_reviews_for_emission(proposal, reviews, authority_profile)
        resolved_authority = replace(authority_profile, approvals_required=0)

        return self.decision_service.decide(
            evaluation,
            resolved_authority,
            issued_at=issued_at,
            method=DecisionEmissionMethod.HUMAN,
        )

    def _validate_reviews_for_emission(
        self,
        proposal: DecisionProposal,
        reviews: list[DecisionReview],
        authority_profile: DecisionAuthorityProfile,
    ) -> None:
        if not reviews:
            raise ValueError(
                "Emissão humana exige ao menos uma review aprovadora da proposta."
            )

        required_approvals = max(1, authority_profile.approvals_required)
        seen_review_ids: set[TypedId] = set()
        seen_reviewers: set[tuple[str, str]] = set()

        for review in reviews:
            if review.review_id in seen_review_ids:
                raise ValueError("A mesma review não pode ser contada duas vezes na emissão.")
            seen_review_ids.add(review.review_id)

            if review.proposal_id != proposal.proposal_id:
                raise ValueError(
                    "A review não referencia esta proposta: revisão sobre outra "
                    "proposta não satisfaz emissão desta."
                )
            if review.organization_id != proposal.organization_id:
                raise ValueError("A review deve pertencer à mesma Organization da proposta.")
            if review.conclusion is not ReviewConclusion.APROVA:
                raise ValueError(
                    f"Review com conclusão '{review.conclusion.value}' não emite Decision "
                    "-- só aprovação satisfaz emissão."
                )

            reviewer_key = (
                review.reviewer_reference.target_id.entity_type,
                str(review.reviewer_reference.target_id.value),
            )
            if reviewer_key in seen_reviewers:
                raise ValueError(
                    "O mesmo revisor não pode satisfazer mais de uma aprovação exigida."
                )
            seen_reviewers.add(reviewer_key)

        if len(reviews) < required_approvals:
            raise ValueError(
                "A proposta ainda não possui aprovações suficientes para emissão."
            )

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
