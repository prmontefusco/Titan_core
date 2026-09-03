"""Market optionality projection for policy-versioned temporal readiness.

F1 is intentionally application-only and transient. It derives an option state
from canonical Evaluation/Decision material; it does not execute Rules, emit
Decision, persist artifacts, forecast future eligibility, or mutate Animal.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from packages.core_domain.decision import Decision, DecisionResult
from packages.core_domain.evaluation import Evaluation, RuleResultStatus
from packages.livestock_application.market_readiness import (
    MARKET_ELIGIBILITY_RESULT_BOUNDARY,
    MarketReadinessContext,
    MarketReadinessInput,
    MarketReadinessService,
    MarketReadinessStatus,
)
from packages.shared_kernel import OrganizationId, TypedId
from packages.shared_kernel.temporal import require_utc


class MarketOptionState(StrEnum):
    """Derived optionality state, distinct from Evaluation/Decision/Readiness."""

    OPTION_OPEN = "OPTION_OPEN"
    OPTION_AT_RISK = "OPTION_AT_RISK"
    MISSING_EVIDENCE = "MISSING_EVIDENCE"
    UNKNOWN = "UNKNOWN"
    POLICY_UNAVAILABLE = "POLICY_UNAVAILABLE"
    REASSESSMENT_REQUIRED = "REASSESSMENT_REQUIRED"
    TEMPORARILY_INCOMPATIBLE = "TEMPORARILY_INCOMPATIBLE"
    IRREVERSIBLY_INCOMPATIBLE = "IRREVERSIBLY_INCOMPATIBLE"
    NOT_EVALUATED = "NOT_EVALUATED"


class MarketOptionReversibility(StrEnum):
    NOT_APPLICABLE = "NOT_APPLICABLE"
    POTENTIALLY_RESOLVABLE = "POTENTIALLY_RESOLVABLE"
    TEMPORARY = "TEMPORARY"
    IRREVERSIBLE = "IRREVERSIBLE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class MarketOptionContext:
    organization_id: OrganizationId
    subject_id: TypedId
    market_purpose: str
    policy_id: TypedId
    policy_version: int
    reference_time: datetime
    knowledge_cutoff: datetime
    target_window_from: datetime | None = None
    target_window_until: datetime | None = None
    result_boundary: str = MARKET_ELIGIBILITY_RESULT_BOUNDARY

    def __post_init__(self) -> None:
        if self.subject_id.entity_type != "animal":
            raise ValueError("F1 de Market Optionality aceita somente subject_id do tipo 'animal'.")
        if self.policy_id.entity_type != "policy":
            raise ValueError("policy_id deve ter entity_type 'policy'.")
        if not isinstance(self.policy_version, int) or self.policy_version < 1:
            raise ValueError("policy_version deve ser inteiro >= 1.")
        if not isinstance(self.market_purpose, str) or not self.market_purpose.strip():
            raise ValueError("market_purpose deve ser texto não vazio.")
        require_utc(self.reference_time, field_name="reference_time")
        require_utc(self.knowledge_cutoff, field_name="knowledge_cutoff")
        if self.knowledge_cutoff < self.reference_time:
            raise ValueError("knowledge_cutoff não pode ser anterior a reference_time.")
        if (self.target_window_from is None) != (self.target_window_until is None):
            raise ValueError(
                "target_window_from e target_window_until devem ser informados juntos."
            )
        if self.target_window_from is not None and self.target_window_until is not None:
            require_utc(self.target_window_from, field_name="target_window_from")
            require_utc(self.target_window_until, field_name="target_window_until")
            if self.target_window_from >= self.target_window_until:
                raise ValueError("target_window deve usar intervalo semiaberto não vazio.")
        if self.result_boundary != MARKET_ELIGIBILITY_RESULT_BOUNDARY:
            raise ValueError("result_boundary deve preservar a fronteira de Market Eligibility.")

    def to_readiness_context(self) -> MarketReadinessContext:
        return MarketReadinessContext(
            organization_id=self.organization_id,
            purpose=self.market_purpose,
            policy_id=self.policy_id,
            policy_version=self.policy_version,
            reference_time=self.reference_time,
            knowledge_cutoff=self.knowledge_cutoff,
        )


@dataclass(frozen=True, slots=True)
class MarketOptionAssessment:
    context: MarketOptionContext
    state: MarketOptionState
    reversibility: MarketOptionReversibility
    decision_id: TypedId | None
    evaluation_id: TypedId | None
    reason_codes: tuple[str, ...]
    missing_evidence_types: tuple[str, ...]
    limitations: tuple[str, ...]
    result_boundary: str = MARKET_ELIGIBILITY_RESULT_BOUNDARY

    @property
    def preserves_option(self) -> bool:
        return self.state is MarketOptionState.OPTION_OPEN


@dataclass(frozen=True, slots=True)
class MarketOptionAssessmentService:
    """Maps canonical conclusions to optionality without reinterpreting truth."""

    readiness_service: MarketReadinessService = MarketReadinessService()

    def assess(
        self,
        *,
        context: MarketOptionContext,
        decision: Decision | None = None,
        evaluation: Evaluation | None = None,
        policy_available: bool = True,
    ) -> MarketOptionAssessment:
        if not policy_available:
            if decision is not None or evaluation is not None:
                raise ValueError(
                    "policy unavailable não deve ser combinado com Decision/Evaluation."
                )
            return _assessment(
                context=context,
                state=MarketOptionState.POLICY_UNAVAILABLE,
                reversibility=MarketOptionReversibility.UNKNOWN,
                reason_codes=("POLICY_UNAVAILABLE",),
            )

        readiness = self.readiness_service.build_report(
            context=context.to_readiness_context(),
            inputs=(MarketReadinessInput(context.subject_id, decision, evaluation),),
        ).entries[0]

        if decision is None or evaluation is None:
            return _assessment(
                context=context,
                state=MarketOptionState.NOT_EVALUATED,
                reversibility=MarketOptionReversibility.UNKNOWN,
                reason_codes=readiness.reason_codes,
            )

        missing = _missing_evidence_types(evaluation)
        if missing:
            return _assessment(
                context=context,
                state=MarketOptionState.MISSING_EVIDENCE,
                reversibility=MarketOptionReversibility.POTENTIALLY_RESOLVABLE,
                decision=decision,
                evaluation=evaluation,
                reason_codes=(*readiness.reason_codes, "MISSING_EVIDENCE"),
                missing_evidence_types=missing,
                limitations=readiness.limitations,
            )

        if readiness.status is MarketReadinessStatus.READY:
            return _assessment(
                context=context,
                state=MarketOptionState.OPTION_OPEN,
                reversibility=MarketOptionReversibility.NOT_APPLICABLE,
                decision=decision,
                evaluation=evaluation,
                reason_codes=readiness.reason_codes,
            )
        if readiness.status is MarketReadinessStatus.CONDITIONED:
            return _assessment(
                context=context,
                state=MarketOptionState.OPTION_AT_RISK,
                reversibility=MarketOptionReversibility.POTENTIALLY_RESOLVABLE,
                decision=decision,
                evaluation=evaluation,
                reason_codes=readiness.reason_codes,
            )
        if readiness.status is MarketReadinessStatus.REASSESSMENT_REQUIRED:
            return _assessment(
                context=context,
                state=MarketOptionState.REASSESSMENT_REQUIRED,
                reversibility=MarketOptionReversibility.UNKNOWN,
                decision=decision,
                evaluation=evaluation,
                reason_codes=readiness.reason_codes,
                limitations=readiness.limitations,
            )
        if readiness.status is MarketReadinessStatus.INDETERMINATE:
            return _assessment(
                context=context,
                state=MarketOptionState.UNKNOWN,
                reversibility=MarketOptionReversibility.UNKNOWN,
                decision=decision,
                evaluation=evaluation,
                reason_codes=readiness.reason_codes,
                limitations=readiness.limitations,
            )
        if decision.result is DecisionResult.REJEITADA:
            irreversible = _has_irreversible_marker(
                (
                    *(reason.code.value for reason in decision.reasons),
                    *(reason.message for reason in decision.reasons),
                    *readiness.reason_codes,
                    *readiness.limitations,
                ),
            )
            return _assessment(
                context=context,
                state=(
                    MarketOptionState.IRREVERSIBLY_INCOMPATIBLE
                    if irreversible
                    else MarketOptionState.TEMPORARILY_INCOMPATIBLE
                ),
                reversibility=(
                    MarketOptionReversibility.IRREVERSIBLE
                    if irreversible
                    else MarketOptionReversibility.TEMPORARY
                ),
                decision=decision,
                evaluation=evaluation,
                reason_codes=readiness.reason_codes,
                limitations=readiness.limitations,
            )
        return _assessment(
            context=context,
            state=MarketOptionState.UNKNOWN,
            reversibility=MarketOptionReversibility.UNKNOWN,
            decision=decision,
            evaluation=evaluation,
            reason_codes=readiness.reason_codes,
            limitations=readiness.limitations,
        )


def _assessment(
    *,
    context: MarketOptionContext,
    state: MarketOptionState,
    reversibility: MarketOptionReversibility,
    decision: Decision | None = None,
    evaluation: Evaluation | None = None,
    reason_codes: tuple[str, ...] = (),
    missing_evidence_types: tuple[str, ...] = (),
    limitations: tuple[str, ...] = (),
) -> MarketOptionAssessment:
    return MarketOptionAssessment(
        context=context,
        state=state,
        reversibility=reversibility,
        decision_id=None if decision is None else decision.decision_id,
        evaluation_id=None if evaluation is None else evaluation.evaluation_id,
        reason_codes=tuple(dict.fromkeys(reason_codes)),
        missing_evidence_types=tuple(sorted(set(missing_evidence_types))),
        limitations=tuple(dict.fromkeys(limitations)),
    )


def _missing_evidence_types(evaluation: Evaluation) -> tuple[str, ...]:
    values: list[str] = []
    for result in evaluation.rule_results:
        if result.status is RuleResultStatus.PENDENTE:
            values.extend(result.missing_evidence_types)
    return tuple(sorted(set(values)))


def _has_irreversible_marker(codes: Iterable[str]) -> bool:
    return any("IRREVERSIBLE" in code.upper() for code in codes)
