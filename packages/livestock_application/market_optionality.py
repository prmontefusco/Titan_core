"""Market optionality projection for policy-versioned temporal readiness.

This module is intentionally application-only and transient. It derives option
states and multi-market reports from canonical Evaluation/Decision material; it
does not execute Rules, emit Decision, persist artifacts, forecast future
eligibility, or mutate Animal.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Protocol

from packages.core_domain.decision import Decision, DecisionResult
from packages.core_domain.evaluation import Evaluation, RuleResultStatus
from packages.livestock_application.market_change_impact import (
    MarketChangeImpactAssessment,
    MarketChangeImpactEntry,
    MarketChangeImpactStatus,
)
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
class MarketOptionInput:
    context: MarketOptionContext
    decision: Decision | None = None
    evaluation: Evaluation | None = None
    policy_available: bool = True


@dataclass(frozen=True, slots=True)
class MultiMarketOptionReport:
    organization_id: OrganizationId
    subject_id: TypedId
    reference_time: datetime
    knowledge_cutoff: datetime
    assessments: tuple[MarketOptionAssessment, ...]
    counts_by_state: Mapping[MarketOptionState, int]
    market_purposes: tuple[str, ...]
    target_window_from: datetime | None = None
    target_window_until: datetime | None = None
    limitations: tuple[str, ...] = (
        "MULTI_MARKET_OPTIONALITY_IS_DERIVED_NON_DECISIONAL",
        "NO_FORECAST_OR_FUTURE_ELIGIBILITY_GUARANTEE",
    )
    result_boundary: str = MARKET_ELIGIBILITY_RESULT_BOUNDARY


class MarketOptionChangeImpactState(StrEnum):
    UNCHANGED = "UNCHANGED"
    REASSESSMENT_NEEDED = "REASSESSMENT_NEEDED"
    OPTIONALITY_UNKNOWN_UNDER_REPLACEMENT = "OPTIONALITY_UNKNOWN_UNDER_REPLACEMENT"
    OPTIONALITY_PRESERVED = "OPTIONALITY_PRESERVED"
    OPTIONALITY_AT_RISK = "OPTIONALITY_AT_RISK"
    OPTIONALITY_LOST = "OPTIONALITY_LOST"
    LIMITED = "LIMITED"


class MarketOptionEventKind(StrEnum):
    TREATMENT = "TREATMENT"
    MOVEMENT = "MOVEMENT"
    DOCUMENTARY = "DOCUMENTARY"
    OTHER = "OTHER"


class MarketOptionPreservationWarningState(StrEnum):
    NO_KNOWN_OPTION_IMPACT = "NO_KNOWN_OPTION_IMPACT"
    OPTION_AT_RISK = "OPTION_AT_RISK"
    OPTION_LOSS_INDICATED = "OPTION_LOSS_INDICATED"
    IMPACT_UNKNOWN = "IMPACT_UNKNOWN"
    INSUFFICIENT_MATERIAL = "INSUFFICIENT_MATERIAL"


class MarketOptionExplanationAudience(StrEnum):
    INTERNAL_OPERATOR = "INTERNAL_OPERATOR"
    PRODUCER = "PRODUCER"
    AUDITOR = "AUDITOR"


class MarketOptionExplanationAssertion(StrEnum):
    CANONICAL_SUMMARY = "CANONICAL_SUMMARY"
    DECISION = "DECISION"
    EVALUATION = "EVALUATION"
    FORECAST = "FORECAST"
    EXTERNAL_AUTHORITY_RECOGNITION = "EXTERNAL_AUTHORITY_RECOGNITION"
    FACT_CREATION = "FACT_CREATION"
    EVIDENCE_CREATION = "EVIDENCE_CREATION"
    RULE_CREATION = "RULE_CREATION"
    OPTION_STATE_CLASSIFICATION = "OPTION_STATE_CLASSIFICATION"


class MarketOptionExplanationClaimType(StrEnum):
    STATUS = "STATUS"
    REVERSIBILITY = "REVERSIBILITY"
    REASON_CODE = "REASON_CODE"
    MISSING_INFORMATION = "MISSING_INFORMATION"
    LIMITATION = "LIMITATION"
    TEMPORAL_CONTEXT = "TEMPORAL_CONTEXT"
    AUTHORITY_BOUNDARY = "AUTHORITY_BOUNDARY"


class MarketOptionExplanationViolation(StrEnum):
    MISSING_CANONICAL_REFERENCE = "MISSING_CANONICAL_REFERENCE"
    DECISION_REFERENCE_MISMATCH = "DECISION_REFERENCE_MISMATCH"
    EVALUATION_REFERENCE_MISMATCH = "EVALUATION_REFERENCE_MISMATCH"
    POLICY_REFERENCE_MISMATCH = "POLICY_REFERENCE_MISMATCH"
    OPTION_STATE_MISMATCH = "OPTION_STATE_MISMATCH"
    INVENTED_CLAIM = "INVENTED_CLAIM"
    INVENTED_REASON_CODE = "INVENTED_REASON_CODE"
    INVENTED_MISSING_EVIDENCE_TYPE = "INVENTED_MISSING_EVIDENCE_TYPE"
    INVENTED_LIMITATION = "INVENTED_LIMITATION"
    PROHIBITED_AUTHORITATIVE_ASSERTION = "PROHIBITED_AUTHORITATIVE_ASSERTION"


@dataclass(frozen=True, slots=True)
class MarketOptionChangeImpactEntry:
    subject_id: TypedId
    decision_id: TypedId
    evaluation_id: TypedId
    impact_state: MarketOptionChangeImpactState
    previous_state: MarketOptionState | None
    replacement_state: MarketOptionState | None
    reason_codes: tuple[str, ...]
    limitations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MarketOptionChangeImpactReport:
    impact_assessment: MarketChangeImpactAssessment
    entries: tuple[MarketOptionChangeImpactEntry, ...]
    counts_by_state: Mapping[MarketOptionChangeImpactState, int]
    result_boundary: str = MARKET_ELIGIBILITY_RESULT_BOUNDARY


@dataclass(frozen=True, slots=True)
class MarketOptionEventContext:
    organization_id: OrganizationId
    subject_id: TypedId
    event_kind: MarketOptionEventKind
    event_reference: str
    occurred_or_proposed_at: datetime
    knowledge_cutoff: datetime
    purpose: str
    welfare_or_legal_duty: bool = False

    def __post_init__(self) -> None:
        if self.subject_id.entity_type != "animal":
            raise ValueError("Market option warning aceita somente subject_id do tipo 'animal'.")
        if not self.event_reference.strip():
            raise ValueError("event_reference deve ser texto não vazio.")
        if not self.purpose.strip():
            raise ValueError("purpose deve ser texto não vazio.")
        require_utc(self.occurred_or_proposed_at, field_name="occurred_or_proposed_at")
        require_utc(self.knowledge_cutoff, field_name="knowledge_cutoff")
        if self.knowledge_cutoff < self.occurred_or_proposed_at:
            raise ValueError("knowledge_cutoff não pode ser anterior ao evento observado/proposto.")


@dataclass(frozen=True, slots=True)
class MarketOptionPreservationWarning:
    event_context: MarketOptionEventContext
    before_state: MarketOptionState | None
    after_state: MarketOptionState | None
    warning_state: MarketOptionPreservationWarningState
    reversibility: MarketOptionReversibility
    reason_codes: tuple[str, ...]
    limitations: tuple[str, ...]
    result_boundary: str = MARKET_ELIGIBILITY_RESULT_BOUNDARY


@dataclass(frozen=True, slots=True)
class MarketOptionExplanationClaim:
    claim_type: MarketOptionExplanationClaimType
    value: str
    source_reference: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not self.value.strip():
            raise ValueError("claim value deve ser texto não vazio.")
        if not isinstance(self.source_reference, str) or not self.source_reference.strip():
            raise ValueError("claim source_reference deve ser texto não vazio.")


@dataclass(frozen=True, slots=True)
class MarketOptionExplanationContext:
    assessment: MarketOptionAssessment
    audience: MarketOptionExplanationAudience
    source_references: Mapping[str, str]
    allowed_claims: tuple[MarketOptionExplanationClaim, ...]
    allowed_option_state: MarketOptionState
    allowed_reason_codes: tuple[str, ...]
    allowed_missing_evidence_types: tuple[str, ...]
    allowed_limitations: tuple[str, ...]
    limitations: tuple[str, ...] = (
        "AI_EXPLANATION_CONTEXT_IS_NOT_DECISION",
        "AI_EXPLANATION_CONTEXT_IS_NOT_EVALUATION",
        "AI_EXPLANATION_CONTEXT_IS_NOT_FORECAST",
        "AI_EXPLANATION_MUST_PRESERVE_CANONICAL_REFERENCES",
    )


@dataclass(frozen=True, slots=True)
class MarketOptionExplanationDraft:
    text: str
    decision_id: TypedId | None
    evaluation_id: TypedId | None
    policy_id: TypedId
    policy_version: int
    option_state: MarketOptionState
    referenced_claims: tuple[MarketOptionExplanationClaim, ...] = ()
    referenced_reason_codes: tuple[str, ...] = ()
    referenced_missing_evidence_types: tuple[str, ...] = ()
    referenced_limitations: tuple[str, ...] = ()
    assertions: tuple[MarketOptionExplanationAssertion, ...] = (
        MarketOptionExplanationAssertion.CANONICAL_SUMMARY,
    )

    def __post_init__(self) -> None:
        if not isinstance(self.text, str) or not self.text.strip():
            raise ValueError("explanation draft deve possuir texto não vazio.")


@dataclass(frozen=True, slots=True)
class MarketOptionExplanationValidation:
    accepted: bool
    violations: tuple[MarketOptionExplanationViolation, ...]
    limitations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MarketOptionExplanationRunContext:
    data_contract_id: str
    data_contract_version: int
    processing_activity: str
    provider_profile: str
    model_name: str

    def __post_init__(self) -> None:
        for field_name in (
            "data_contract_id",
            "processing_activity",
            "provider_profile",
            "model_name",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} deve ser texto não vazio.")
        if not isinstance(self.data_contract_version, int) or self.data_contract_version < 1:
            raise ValueError("data_contract_version deve ser inteiro >= 1.")


@dataclass(frozen=True, slots=True)
class MarketOptionExplanationResult:
    run_context: MarketOptionExplanationRunContext
    explanation_context: MarketOptionExplanationContext
    validation: MarketOptionExplanationValidation
    released_text: str | None
    canonical_fallback: Mapping[str, str]


class MarketOptionExplanationDraftProvider(Protocol):
    def draft(
        self,
        *,
        explanation_context: MarketOptionExplanationContext,
        run_context: MarketOptionExplanationRunContext,
    ) -> MarketOptionExplanationDraft: ...


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


@dataclass(frozen=True, slots=True)
class MultiMarketOptionReportService:
    """Builds deterministic transient reports across explicit market purposes."""

    assessment_service: MarketOptionAssessmentService = MarketOptionAssessmentService()

    def build_report(
        self,
        *,
        inputs: tuple[MarketOptionInput, ...],
    ) -> MultiMarketOptionReport:
        if not inputs:
            raise ValueError("inputs deve conter ao menos um mercado.")

        first = inputs[0].context
        seen_purposes: set[str] = set()
        for item in inputs:
            context = item.context
            _ensure_same_report_coordinates(first, context)
            if context.market_purpose in seen_purposes:
                raise ValueError(
                    "market_purpose duplicado torna a Policy ambígua para o relatório."
                )
            seen_purposes.add(context.market_purpose)

        assessments = tuple(
            self.assessment_service.assess(
                context=item.context,
                decision=item.decision,
                evaluation=item.evaluation,
                policy_available=item.policy_available,
            )
            for item in sorted(inputs, key=lambda candidate: candidate.context.market_purpose)
        )
        counts = {state: 0 for state in MarketOptionState}
        for assessment in assessments:
            counts[assessment.state] += 1

        return MultiMarketOptionReport(
            organization_id=first.organization_id,
            subject_id=first.subject_id,
            reference_time=first.reference_time,
            knowledge_cutoff=first.knowledge_cutoff,
            target_window_from=first.target_window_from,
            target_window_until=first.target_window_until,
            assessments=assessments,
            counts_by_state=MappingProxyType(counts),
            market_purposes=tuple(assessment.context.market_purpose for assessment in assessments),
        )


@dataclass(frozen=True, slots=True)
class MarketOptionChangeImpactService:
    """Composes NEXT-07 impact with optionality without running new Rules."""

    def build_report(
        self,
        *,
        impact_assessment: MarketChangeImpactAssessment,
        previous_assessments: tuple[MarketOptionAssessment, ...],
        replacement_assessments: tuple[MarketOptionAssessment, ...] = (),
    ) -> MarketOptionChangeImpactReport:
        previous_by_subject = _index_option_assessments(previous_assessments, "previous")
        replacement_by_subject = _index_option_assessments(replacement_assessments, "replacement")
        entries = tuple(
            self._entry(
                impact_entry=impact_entry,
                previous=previous_by_subject.get(impact_entry.subject_id),
                replacement=replacement_by_subject.get(impact_entry.subject_id),
            )
            for impact_entry in impact_assessment.entries
        )
        counts = {state: 0 for state in MarketOptionChangeImpactState}
        for entry in entries:
            counts[entry.impact_state] += 1
        return MarketOptionChangeImpactReport(
            impact_assessment=impact_assessment,
            entries=entries,
            counts_by_state=MappingProxyType(counts),
        )

    def _entry(
        self,
        *,
        impact_entry: MarketChangeImpactEntry,
        previous: MarketOptionAssessment | None,
        replacement: MarketOptionAssessment | None,
    ) -> MarketOptionChangeImpactEntry:
        if previous is not None:
            _ensure_assessment_matches_impact_entry(previous, impact_entry, "previous")
        if replacement is not None and replacement.context.subject_id != impact_entry.subject_id:
            raise ValueError("replacement assessment deve referenciar o mesmo subject_id.")

        limitations: list[str] = []
        reason_codes: list[str] = []
        if impact_entry.limitation is not None:
            limitations.append(impact_entry.limitation)
        if previous is None:
            limitations.append("PREVIOUS_OPTIONALITY_ASSESSMENT_UNAVAILABLE")
        else:
            reason_codes.extend(previous.reason_codes)

        if impact_entry.status is MarketChangeImpactStatus.UNRELATED:
            impact_state = MarketOptionChangeImpactState.UNCHANGED
            replacement_state = previous.state if previous is not None else None
        elif impact_entry.status is MarketChangeImpactStatus.LIMITED:
            impact_state = MarketOptionChangeImpactState.LIMITED
            replacement_state = None
        elif replacement is None:
            impact_state = MarketOptionChangeImpactState.REASSESSMENT_NEEDED
            replacement_state = None
            limitations.append("REPLACEMENT_OPTIONALITY_ASSESSMENT_UNAVAILABLE")
        else:
            replacement_state = replacement.state
            reason_codes.extend(replacement.reason_codes)
            limitations.extend(replacement.limitations)
            impact_state = _classify_replacement_optionality(replacement.state)

        return MarketOptionChangeImpactEntry(
            subject_id=impact_entry.subject_id,
            decision_id=impact_entry.decision_id,
            evaluation_id=impact_entry.evaluation_id,
            impact_state=impact_state,
            previous_state=None if previous is None else previous.state,
            replacement_state=replacement_state,
            reason_codes=tuple(dict.fromkeys(reason_codes)),
            limitations=tuple(dict.fromkeys(limitations)),
        )


@dataclass(frozen=True, slots=True)
class MarketOptionPreservationWarningService:
    """Explains supplied before/after option impact without operational advice."""

    def explain(
        self,
        *,
        event_context: MarketOptionEventContext,
        before: MarketOptionAssessment | None,
        after: MarketOptionAssessment | None,
    ) -> MarketOptionPreservationWarning:
        if before is not None:
            _ensure_assessment_matches_event(before, event_context, "before")
        if after is not None:
            _ensure_assessment_matches_event(after, event_context, "after")

        limitations = [
            "MARKET_OPTION_WARNING_IS_EXPLANATORY_NOT_OPERATIONAL_COMMAND",
            "DO_NOT_OMIT_OR_DELAY_REQUIRED_FACT_RECORDING",
        ]
        if event_context.welfare_or_legal_duty:
            limitations.append("ANIMAL_WELFARE_OR_LEGAL_DUTY_OVERRIDES_MARKET_OPTIONALITY")

        if before is None or after is None:
            warning_state = MarketOptionPreservationWarningState.INSUFFICIENT_MATERIAL
            reversibility = MarketOptionReversibility.UNKNOWN
        else:
            warning_state = _classify_preservation_warning(before.state, after.state)
            reversibility = _warning_reversibility(warning_state, after.reversibility)
            limitations.extend(before.limitations)
            limitations.extend(after.limitations)

        reason_codes: list[str] = []
        if before is not None:
            reason_codes.extend(before.reason_codes)
        if after is not None:
            reason_codes.extend(after.reason_codes)

        return MarketOptionPreservationWarning(
            event_context=event_context,
            before_state=None if before is None else before.state,
            after_state=None if after is None else after.state,
            warning_state=warning_state,
            reversibility=reversibility,
            reason_codes=tuple(dict.fromkeys(reason_codes)),
            limitations=tuple(dict.fromkeys(limitations)),
        )


@dataclass(frozen=True, slots=True)
class MarketOptionExplanationGuardService:
    """Prepares and validates AI-facing explanation material over canonical outputs."""

    def prepare_context(
        self,
        *,
        assessment: MarketOptionAssessment,
        audience: MarketOptionExplanationAudience = (
            MarketOptionExplanationAudience.INTERNAL_OPERATOR
        ),
    ) -> MarketOptionExplanationContext:
        references = {
            "organization_id": str(assessment.context.organization_id),
            "subject_id": str(assessment.context.subject_id),
            "policy_id": str(assessment.context.policy_id),
            "policy_version": str(assessment.context.policy_version),
            "market_purpose": assessment.context.market_purpose,
            "reference_time": assessment.context.reference_time.isoformat(),
            "knowledge_cutoff": assessment.context.knowledge_cutoff.isoformat(),
            "result_boundary": assessment.result_boundary,
        }
        if assessment.decision_id is not None:
            references["decision_id"] = str(assessment.decision_id)
        if assessment.evaluation_id is not None:
            references["evaluation_id"] = str(assessment.evaluation_id)

        return MarketOptionExplanationContext(
            assessment=assessment,
            audience=audience,
            source_references=MappingProxyType(references),
            allowed_claims=_allowed_explanation_claims(assessment),
            allowed_option_state=assessment.state,
            allowed_reason_codes=assessment.reason_codes,
            allowed_missing_evidence_types=assessment.missing_evidence_types,
            allowed_limitations=assessment.limitations,
        )

    def validate_draft(
        self,
        *,
        context: MarketOptionExplanationContext,
        draft: MarketOptionExplanationDraft,
    ) -> MarketOptionExplanationValidation:
        violations: list[MarketOptionExplanationViolation] = []
        assessment = context.assessment

        if draft.decision_id != assessment.decision_id:
            violations.append(MarketOptionExplanationViolation.DECISION_REFERENCE_MISMATCH)
        if draft.evaluation_id != assessment.evaluation_id:
            violations.append(MarketOptionExplanationViolation.EVALUATION_REFERENCE_MISMATCH)
        if (
            draft.policy_id != assessment.context.policy_id
            or draft.policy_version != assessment.context.policy_version
        ):
            violations.append(MarketOptionExplanationViolation.POLICY_REFERENCE_MISMATCH)
        if draft.option_state is not context.allowed_option_state:
            violations.append(MarketOptionExplanationViolation.OPTION_STATE_MISMATCH)
        if (assessment.decision_id is not None and draft.decision_id is None) or (
            assessment.evaluation_id is not None and draft.evaluation_id is None
        ):
            violations.append(MarketOptionExplanationViolation.MISSING_CANONICAL_REFERENCE)
        if not set(draft.referenced_claims).issubset(context.allowed_claims):
            violations.append(MarketOptionExplanationViolation.INVENTED_CLAIM)
        if not set(draft.referenced_reason_codes).issubset(context.allowed_reason_codes):
            violations.append(MarketOptionExplanationViolation.INVENTED_REASON_CODE)
        if not set(draft.referenced_missing_evidence_types).issubset(
            context.allowed_missing_evidence_types
        ):
            violations.append(MarketOptionExplanationViolation.INVENTED_MISSING_EVIDENCE_TYPE)
        if not set(draft.referenced_limitations).issubset(context.allowed_limitations):
            violations.append(MarketOptionExplanationViolation.INVENTED_LIMITATION)
        if any(
            assertion is not MarketOptionExplanationAssertion.CANONICAL_SUMMARY
            for assertion in draft.assertions
        ):
            violations.append(MarketOptionExplanationViolation.PROHIBITED_AUTHORITATIVE_ASSERTION)

        return MarketOptionExplanationValidation(
            accepted=not violations,
            violations=tuple(dict.fromkeys(violations)),
            limitations=context.limitations,
        )


@dataclass(frozen=True, slots=True)
class DeterministicMarketOptionExplanationDraftProvider:
    """Local fake provider for tests; it never calls an external model."""

    def draft(
        self,
        *,
        explanation_context: MarketOptionExplanationContext,
        run_context: MarketOptionExplanationRunContext,
    ) -> MarketOptionExplanationDraft:
        assessment = explanation_context.assessment
        return MarketOptionExplanationDraft(
            text=(
                "Resumo canônico sintético: estado "
                f"{assessment.state.value} para {assessment.context.market_purpose}."
            ),
            decision_id=assessment.decision_id,
            evaluation_id=assessment.evaluation_id,
            policy_id=assessment.context.policy_id,
            policy_version=assessment.context.policy_version,
            option_state=assessment.state,
            referenced_reason_codes=assessment.reason_codes,
            referenced_missing_evidence_types=assessment.missing_evidence_types,
            referenced_limitations=assessment.limitations,
            referenced_claims=explanation_context.allowed_claims,
        )


@dataclass(frozen=True, slots=True)
class MarketOptionExplanationPipelineService:
    """Composes draft generation with deterministic guards before releasing text."""

    draft_provider: MarketOptionExplanationDraftProvider = (
        DeterministicMarketOptionExplanationDraftProvider()
    )
    guard_service: MarketOptionExplanationGuardService = MarketOptionExplanationGuardService()

    def explain(
        self,
        *,
        assessment: MarketOptionAssessment,
        run_context: MarketOptionExplanationRunContext,
        audience: MarketOptionExplanationAudience = (
            MarketOptionExplanationAudience.INTERNAL_OPERATOR
        ),
    ) -> MarketOptionExplanationResult:
        explanation_context = self.guard_service.prepare_context(
            assessment=assessment,
            audience=audience,
        )
        draft = self.draft_provider.draft(
            explanation_context=explanation_context,
            run_context=run_context,
        )
        validation = self.guard_service.validate_draft(
            context=explanation_context,
            draft=draft,
        )
        return MarketOptionExplanationResult(
            run_context=run_context,
            explanation_context=explanation_context,
            validation=validation,
            released_text=draft.text if validation.accepted else None,
            canonical_fallback=_canonical_explanation_fallback(assessment),
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


def _canonical_explanation_fallback(
    assessment: MarketOptionAssessment,
) -> Mapping[str, str]:
    return MappingProxyType(
        {
            "state": assessment.state.value,
            "reversibility": assessment.reversibility.value,
            "policy_id": str(assessment.context.policy_id),
            "policy_version": str(assessment.context.policy_version),
            "reference_time": assessment.context.reference_time.isoformat(),
            "knowledge_cutoff": assessment.context.knowledge_cutoff.isoformat(),
            "result_boundary": assessment.result_boundary,
        }
    )


def _allowed_explanation_claims(
    assessment: MarketOptionAssessment,
) -> tuple[MarketOptionExplanationClaim, ...]:
    source = _primary_claim_source_reference(assessment)
    claims = [
        MarketOptionExplanationClaim(
            claim_type=MarketOptionExplanationClaimType.STATUS,
            value=assessment.state.value,
            source_reference=source,
        ),
        MarketOptionExplanationClaim(
            claim_type=MarketOptionExplanationClaimType.REVERSIBILITY,
            value=assessment.reversibility.value,
            source_reference=source,
        ),
        MarketOptionExplanationClaim(
            claim_type=MarketOptionExplanationClaimType.TEMPORAL_CONTEXT,
            value=(
                f"reference_time={assessment.context.reference_time.isoformat()};"
                f"knowledge_cutoff={assessment.context.knowledge_cutoff.isoformat()}"
            ),
            source_reference="market_option_context",
        ),
        MarketOptionExplanationClaim(
            claim_type=MarketOptionExplanationClaimType.AUTHORITY_BOUNDARY,
            value="MARKET_OPTIONALITY_IS_EXPLANATORY_NOT_AUTHORITY",
            source_reference="adr:0073",
        ),
    ]
    claims.extend(
        MarketOptionExplanationClaim(
            claim_type=MarketOptionExplanationClaimType.REASON_CODE,
            value=reason_code,
            source_reference=source,
        )
        for reason_code in assessment.reason_codes
    )
    claims.extend(
        MarketOptionExplanationClaim(
            claim_type=MarketOptionExplanationClaimType.MISSING_INFORMATION,
            value=missing,
            source_reference=source,
        )
        for missing in assessment.missing_evidence_types
    )
    claims.extend(
        MarketOptionExplanationClaim(
            claim_type=MarketOptionExplanationClaimType.LIMITATION,
            value=limitation,
            source_reference=source,
        )
        for limitation in assessment.limitations
    )
    return tuple(dict.fromkeys(claims))


def _primary_claim_source_reference(assessment: MarketOptionAssessment) -> str:
    if assessment.decision_id is not None:
        return str(assessment.decision_id)
    if assessment.evaluation_id is not None:
        return str(assessment.evaluation_id)
    return "market_option_assessment"


def _missing_evidence_types(evaluation: Evaluation) -> tuple[str, ...]:
    values: list[str] = []
    for result in evaluation.rule_results:
        if result.status is RuleResultStatus.PENDENTE:
            values.extend(result.missing_evidence_types)
    return tuple(sorted(set(values)))


def _has_irreversible_marker(codes: Iterable[str]) -> bool:
    return any("IRREVERSIBLE" in code.upper() for code in codes)


def _ensure_same_report_coordinates(
    first: MarketOptionContext,
    candidate: MarketOptionContext,
) -> None:
    if candidate.organization_id != first.organization_id:
        raise ValueError("todos os mercados do relatório devem usar a mesma Organization.")
    if candidate.subject_id != first.subject_id:
        raise ValueError("todos os mercados do relatório devem usar o mesmo subject_id.")
    if candidate.reference_time != first.reference_time:
        raise ValueError("todos os mercados devem preservar o mesmo reference_time.")
    if candidate.knowledge_cutoff != first.knowledge_cutoff:
        raise ValueError("todos os mercados devem preservar o mesmo knowledge_cutoff.")
    if candidate.target_window_from != first.target_window_from:
        raise ValueError("todos os mercados devem usar a mesma target_window_from.")
    if candidate.target_window_until != first.target_window_until:
        raise ValueError("todos os mercados devem usar a mesma target_window_until.")
    if candidate.result_boundary != first.result_boundary:
        raise ValueError("todos os mercados devem preservar o mesmo result_boundary.")


def _index_option_assessments(
    assessments: tuple[MarketOptionAssessment, ...],
    label: str,
) -> dict[TypedId, MarketOptionAssessment]:
    indexed: dict[TypedId, MarketOptionAssessment] = {}
    for assessment in assessments:
        subject_id = assessment.context.subject_id
        if subject_id in indexed:
            raise ValueError(f"{label} assessments possuem subject_id duplicado.")
        indexed[subject_id] = assessment
    return indexed


def _ensure_assessment_matches_impact_entry(
    assessment: MarketOptionAssessment,
    impact_entry: MarketChangeImpactEntry,
    label: str,
) -> None:
    if assessment.context.subject_id != impact_entry.subject_id:
        raise ValueError(f"{label} assessment deve referenciar o mesmo subject_id.")
    if assessment.decision_id != impact_entry.decision_id:
        raise ValueError(f"{label} assessment deve referenciar a mesma Decision.")
    if assessment.evaluation_id != impact_entry.evaluation_id:
        raise ValueError(f"{label} assessment deve referenciar a mesma Evaluation.")


def _classify_replacement_optionality(
    state: MarketOptionState,
) -> MarketOptionChangeImpactState:
    if state is MarketOptionState.OPTION_OPEN:
        return MarketOptionChangeImpactState.OPTIONALITY_PRESERVED
    if state is MarketOptionState.OPTION_AT_RISK:
        return MarketOptionChangeImpactState.OPTIONALITY_AT_RISK
    if state in {
        MarketOptionState.TEMPORARILY_INCOMPATIBLE,
        MarketOptionState.IRREVERSIBLY_INCOMPATIBLE,
    }:
        return MarketOptionChangeImpactState.OPTIONALITY_LOST
    return MarketOptionChangeImpactState.OPTIONALITY_UNKNOWN_UNDER_REPLACEMENT


def _ensure_assessment_matches_event(
    assessment: MarketOptionAssessment,
    event_context: MarketOptionEventContext,
    label: str,
) -> None:
    if assessment.context.organization_id != event_context.organization_id:
        raise ValueError(f"{label} assessment deve usar a mesma Organization.")
    if assessment.context.subject_id != event_context.subject_id:
        raise ValueError(f"{label} assessment deve usar o mesmo subject_id.")
    if assessment.context.market_purpose != event_context.purpose:
        raise ValueError(f"{label} assessment deve usar o mesmo purpose.")
    if assessment.context.knowledge_cutoff > event_context.knowledge_cutoff:
        raise ValueError(f"{label} assessment não pode usar conhecimento posterior ao warning.")


def _classify_preservation_warning(
    before: MarketOptionState,
    after: MarketOptionState,
) -> MarketOptionPreservationWarningState:
    if before is not MarketOptionState.OPTION_OPEN:
        if after in {
            MarketOptionState.UNKNOWN,
            MarketOptionState.MISSING_EVIDENCE,
            MarketOptionState.POLICY_UNAVAILABLE,
            MarketOptionState.NOT_EVALUATED,
        }:
            return MarketOptionPreservationWarningState.IMPACT_UNKNOWN
        return MarketOptionPreservationWarningState.NO_KNOWN_OPTION_IMPACT
    if after is MarketOptionState.OPTION_OPEN:
        return MarketOptionPreservationWarningState.NO_KNOWN_OPTION_IMPACT
    if after is MarketOptionState.OPTION_AT_RISK:
        return MarketOptionPreservationWarningState.OPTION_AT_RISK
    if after in {
        MarketOptionState.TEMPORARILY_INCOMPATIBLE,
        MarketOptionState.IRREVERSIBLY_INCOMPATIBLE,
    }:
        return MarketOptionPreservationWarningState.OPTION_LOSS_INDICATED
    return MarketOptionPreservationWarningState.IMPACT_UNKNOWN


def _warning_reversibility(
    warning_state: MarketOptionPreservationWarningState,
    after_reversibility: MarketOptionReversibility,
) -> MarketOptionReversibility:
    if warning_state is MarketOptionPreservationWarningState.NO_KNOWN_OPTION_IMPACT:
        return MarketOptionReversibility.NOT_APPLICABLE
    if warning_state is MarketOptionPreservationWarningState.OPTION_LOSS_INDICATED:
        return after_reversibility
    if warning_state is MarketOptionPreservationWarningState.OPTION_AT_RISK:
        return MarketOptionReversibility.POTENTIALLY_RESOLVABLE
    return MarketOptionReversibility.UNKNOWN
