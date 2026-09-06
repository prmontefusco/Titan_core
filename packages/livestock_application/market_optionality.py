"""Market optionality projection for policy-versioned temporal readiness.

This module is intentionally application-only and transient. It derives option
states and multi-market reports from canonical Evaluation/Decision material; it
does not execute Rules, emit Decision, persist artifacts, forecast future
eligibility, or mutate Animal.
"""

import hashlib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
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
from packages.shared_kernel import (
    CanonicalSerializer,
    OrganizationId,
    TypedId,
    canonicalize_for_hash,
)
from packages.shared_kernel.temporal import require_utc

MARKET_OPTIONALITY_AI_EXPLANATION_SYNTHETIC_CONTRACT_ID = (
    "MARKET_OPTIONALITY_AI_EXPLANATION_SYNTHETIC_V1"
)
MARKET_OPTIONALITY_AI_EXPLANATION_CONTRACT_VERSION = 1
MARKET_OPTIONALITY_AI_EXPLANATION_SCHEMA = "MARKET_OPTIONALITY_AI_EXPLANATION_CONTEXT_V1"
MARKET_OPTIONALITY_AI_EXPLANATION_DRAFT_SCHEMA = "MARKET_OPTIONALITY_AI_EXPLANATION_DRAFT_V1"
MARKET_OPTIONALITY_AI_EXPLANATION_PROMPT_TEMPLATE_ID = (
    "market-optionality-explanation-canonical-summary"
)
MARKET_OPTIONALITY_AI_EXPLANATION_PROMPT_TEMPLATE_VERSION = 1
MARKET_OPTIONALITY_AI_EXPLANATION_GUARD_VERSION = 1
MARKET_OPTIONALITY_AI_EXPLANATION_PROMPT_TEMPLATE_TEXT = (
    "Explain only the structured allowed claims in the supplied Titan context. "
    "Do not add facts, decisions, forecasts, eligibility, external recognition, "
    "instructions, identifiers, or claims not present in the allowed claims list."
)
MARKET_OPTIONALITY_AI_EXPLANATION_PROVIDER_PROFILE_ID = "LOCAL_DETERMINISTIC_FAKE"
MARKET_OPTIONALITY_AI_EXPLANATION_PROVIDER_PROFILE_VERSION = 1
MARKET_OPTIONALITY_AI_EXPLANATION_PROCESSING_AUTHORIZATION_REFERENCE = (
    "SYNTHETIC_AI_EXPLANATION_PROCESSING_AUTHORIZATION"
)
MARKET_OPTIONALITY_AI_EXPLANATION_PROCESSING_AUTHORIZATION_VERSION = 1
MARKET_OPTIONALITY_AI_EXPLANATION_OUTPUT_CLASSIFICATION = "PROTECTED_DERIVED_CANONICAL_EXPLANATION"
MARKET_OPTIONALITY_AI_EXPLANATION_DISCLOSURE_RESTRICTIONS = (
    "DERIVED_KNOWLEDGE_INHERITS_SOURCE_RESTRICTIONS",
    "GENERATION_NEVER_DECLASSIFIES_INFORMATION",
    "NO_REUSE_FOR_EXPORT_INFERENCE_OR_REDISTRIBUTION",
)


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
    DRAFT_SCHEMA_MISMATCH = "DRAFT_SCHEMA_MISMATCH"
    UNKNOWN_CLAIM_REFERENCE = "UNKNOWN_CLAIM_REFERENCE"
    PROHIBITED_TEXT_CONTENT = "PROHIBITED_TEXT_CONTENT"
    PROHIBITED_AUTHORITATIVE_ASSERTION = "PROHIBITED_AUTHORITATIVE_ASSERTION"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    PROVIDER_PROFILE_UNAVAILABLE = "PROVIDER_PROFILE_UNAVAILABLE"
    PROVIDER_PROCESSING_UNAUTHORIZED = "PROVIDER_PROCESSING_UNAUTHORIZED"


class MarketOptionExplanationProviderProfileState(StrEnum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    SUSPENDED = "SUSPENDED"
    REVOKED = "REVOKED"
    SUPERSEDED = "SUPERSEDED"


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
class MarketOptionExplanationDraftSection:
    claim_refs: tuple[str, ...]
    text: str

    def __post_init__(self) -> None:
        if not self.claim_refs:
            raise ValueError("draft section deve referenciar ao menos um claim autorizado.")
        if not isinstance(self.text, str) or not self.text.strip():
            raise ValueError("draft section deve possuir texto não vazio.")
        for claim_ref in self.claim_refs:
            if not isinstance(claim_ref, str) or not claim_ref.strip():
                raise ValueError("draft section claim_ref deve ser texto não vazio.")


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
    schema: str = MARKET_OPTIONALITY_AI_EXPLANATION_DRAFT_SCHEMA
    sections: tuple[MarketOptionExplanationDraftSection, ...] = ()
    assertions: tuple[MarketOptionExplanationAssertion, ...] = (
        MarketOptionExplanationAssertion.CANONICAL_SUMMARY,
    )

    def __post_init__(self) -> None:
        if not isinstance(self.text, str) or not self.text.strip():
            raise ValueError("explanation draft deve possuir texto não vazio.")
        if not self.sections:
            raise ValueError("explanation draft deve possuir seções estruturadas.")


@dataclass(frozen=True, slots=True)
class MarketOptionExplanationValidation:
    accepted: bool
    violations: tuple[MarketOptionExplanationViolation, ...]
    limitations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MarketOptionCanonicalExplanation:
    state: MarketOptionState
    reversibility: MarketOptionReversibility
    policy_id: TypedId
    policy_version: int
    reference_time: datetime
    knowledge_cutoff: datetime
    output_classification: str = MARKET_OPTIONALITY_AI_EXPLANATION_OUTPUT_CLASSIFICATION
    disclosure_restrictions: tuple[str, ...] = (
        MARKET_OPTIONALITY_AI_EXPLANATION_DISCLOSURE_RESTRICTIONS
    )
    result_boundary: str = MARKET_ELIGIBILITY_RESULT_BOUNDARY

    def __post_init__(self) -> None:
        require_utc(self.reference_time, field_name="reference_time")
        require_utc(self.knowledge_cutoff, field_name="knowledge_cutoff")
        if not isinstance(self.output_classification, str) or (
            not self.output_classification.strip()
        ):
            raise ValueError("output_classification deve ser texto não vazio.")
        if not self.disclosure_restrictions:
            raise ValueError("disclosure_restrictions deve preservar ao menos uma restrição.")
        if any(
            not isinstance(item, str) or not item.strip() for item in self.disclosure_restrictions
        ):
            raise ValueError("disclosure_restrictions deve conter textos não vazios.")

    def as_mapping(self) -> Mapping[str, str | tuple[str, ...]]:
        return MappingProxyType(
            {
                "state": self.state.value,
                "reversibility": self.reversibility.value,
                "policy_id": str(self.policy_id),
                "policy_version": str(self.policy_version),
                "reference_time": self.reference_time.isoformat(),
                "knowledge_cutoff": self.knowledge_cutoff.isoformat(),
                "output_classification": self.output_classification,
                "disclosure_restrictions": self.disclosure_restrictions,
                "result_boundary": self.result_boundary,
            }
        )


@dataclass(frozen=True, slots=True)
class MarketOptionExplanationProviderProfile:
    profile_id: str = MARKET_OPTIONALITY_AI_EXPLANATION_PROVIDER_PROFILE_ID
    profile_version: int = MARKET_OPTIONALITY_AI_EXPLANATION_PROVIDER_PROFILE_VERSION
    lifecycle_state: MarketOptionExplanationProviderProfileState = (
        MarketOptionExplanationProviderProfileState.APPROVED
    )
    effective_from: datetime | None = None
    effective_until: datetime | None = None
    provider_side_retention: str = "NONE"
    telemetry: str = "NONE"
    abuse_logging: str = "NONE"
    secondary_use: str = "PROHIBITED"
    training_use: str = "PROHIBITED"
    tool_execution: str = "PROHIBITED"
    profile_digest: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.profile_id, str) or not self.profile_id.strip():
            raise ValueError("provider profile_id deve ser texto não vazio.")
        if not isinstance(self.profile_version, int) or self.profile_version < 1:
            raise ValueError("provider profile_version deve ser inteiro >= 1.")
        if not isinstance(self.lifecycle_state, MarketOptionExplanationProviderProfileState):
            raise TypeError("lifecycle_state deve ser MarketOptionExplanationProviderProfileState.")
        if self.effective_from is not None:
            require_utc(self.effective_from, field_name="effective_from")
        if self.effective_until is not None:
            require_utc(self.effective_until, field_name="effective_until")
        if (
            self.effective_from is not None
            and self.effective_until is not None
            and self.effective_until <= self.effective_from
        ):
            raise ValueError("effective_until deve ser posterior a effective_from.")
        expected = {
            "provider_side_retention": "NONE",
            "telemetry": "NONE",
            "abuse_logging": "NONE",
            "secondary_use": "PROHIBITED",
            "training_use": "PROHIBITED",
            "tool_execution": "PROHIBITED",
        }
        for field_name, expected_value in expected.items():
            if getattr(self, field_name) != expected_value:
                raise ValueError(f"{field_name} não está aprovado para AI Explanation.")
        expected_digest = _canonical_digest(
            "titan.livestock.market_optionality.ai_provider_profile",
            {
                "profile_id": self.profile_id,
                "profile_version": self.profile_version,
                "lifecycle_state": self.lifecycle_state.value,
                "effective_from": (
                    None if self.effective_from is None else self.effective_from.isoformat()
                ),
                "effective_until": (
                    None if self.effective_until is None else self.effective_until.isoformat()
                ),
                "provider_side_retention": self.provider_side_retention,
                "telemetry": self.telemetry,
                "abuse_logging": self.abuse_logging,
                "secondary_use": self.secondary_use,
                "training_use": self.training_use,
                "tool_execution": self.tool_execution,
            },
        )
        if self.profile_digest and self.profile_digest != expected_digest:
            raise ValueError("provider profile_digest não corresponde ao perfil declarado.")
        object.__setattr__(self, "profile_digest", expected_digest)

    def is_available_at(self, at_time: datetime) -> bool:
        require_utc(at_time, field_name="at_time")
        if self.lifecycle_state is not MarketOptionExplanationProviderProfileState.APPROVED:
            return False
        if self.effective_from is not None and at_time < self.effective_from:
            return False
        return not (self.effective_until is not None and at_time >= self.effective_until)


@dataclass(frozen=True, slots=True)
class MarketOptionExplanationProviderProcessingAuthorization:
    organization_id: OrganizationId
    purpose: str
    provider_profile: str
    provider_profile_version: int
    data_contract_id: str
    data_contract_version: int
    classification_ceiling: str = MARKET_OPTIONALITY_AI_EXPLANATION_OUTPUT_CLASSIFICATION
    authorization_reference: str = (
        MARKET_OPTIONALITY_AI_EXPLANATION_PROCESSING_AUTHORIZATION_REFERENCE
    )
    authorization_version: int = MARKET_OPTIONALITY_AI_EXPLANATION_PROCESSING_AUTHORIZATION_VERSION
    effective_from: datetime | None = None
    effective_until: datetime | None = None
    authorization_digest: str = ""

    def __post_init__(self) -> None:
        for field_name in (
            "purpose",
            "provider_profile",
            "data_contract_id",
            "classification_ceiling",
            "authorization_reference",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} deve ser texto não vazio.")
        for field_name in (
            "provider_profile_version",
            "data_contract_version",
            "authorization_version",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, int) or value < 1:
                raise ValueError(f"{field_name} deve ser inteiro >= 1.")
        if self.effective_from is not None:
            require_utc(self.effective_from, field_name="effective_from")
        if self.effective_until is not None:
            require_utc(self.effective_until, field_name="effective_until")
        if (
            self.effective_from is not None
            and self.effective_until is not None
            and self.effective_until <= self.effective_from
        ):
            raise ValueError("effective_until deve ser posterior a effective_from.")
        expected_digest = _canonical_digest(
            "titan.livestock.market_optionality.ai_processing_authorization",
            {
                "organization_id": str(self.organization_id),
                "purpose": self.purpose,
                "provider_profile": self.provider_profile,
                "provider_profile_version": self.provider_profile_version,
                "data_contract_id": self.data_contract_id,
                "data_contract_version": self.data_contract_version,
                "classification_ceiling": self.classification_ceiling,
                "authorization_reference": self.authorization_reference,
                "authorization_version": self.authorization_version,
                "effective_from": (
                    None if self.effective_from is None else self.effective_from.isoformat()
                ),
                "effective_until": (
                    None if self.effective_until is None else self.effective_until.isoformat()
                ),
            },
        )
        if self.authorization_digest and self.authorization_digest != expected_digest:
            raise ValueError("authorization_digest não corresponde à autorização declarada.")
        object.__setattr__(self, "authorization_digest", expected_digest)

    def is_effective_at(self, at_time: datetime) -> bool:
        require_utc(at_time, field_name="at_time")
        if self.effective_from is not None and at_time < self.effective_from:
            return False
        return not (self.effective_until is not None and at_time >= self.effective_until)

    def is_compatible_with(
        self,
        *,
        assessment: MarketOptionAssessment,
        run_context: "MarketOptionExplanationRunContext",
    ) -> bool:
        context = assessment.context
        if self.organization_id != context.organization_id:
            return False
        if self.purpose != context.market_purpose:
            return False
        if self.provider_profile != run_context.provider_profile:
            return False
        if self.provider_profile_version != run_context.provider_profile_version:
            return False
        if self.data_contract_id != run_context.data_contract_id:
            return False
        if self.data_contract_version != run_context.data_contract_version:
            return False
        if self.classification_ceiling != MARKET_OPTIONALITY_AI_EXPLANATION_OUTPUT_CLASSIFICATION:
            return False
        return self.is_effective_at(context.knowledge_cutoff)


@dataclass(frozen=True, slots=True)
class MarketOptionExplanationRunContext:
    data_contract_id: str
    data_contract_version: int
    processing_activity: str
    model_name: str
    processing_authorization_organization_id: OrganizationId
    processing_authorization_purpose: str
    provider_profile: str = MARKET_OPTIONALITY_AI_EXPLANATION_PROVIDER_PROFILE_ID
    provider_profile_version: int = MARKET_OPTIONALITY_AI_EXPLANATION_PROVIDER_PROFILE_VERSION
    provider_profile_state: MarketOptionExplanationProviderProfileState = (
        MarketOptionExplanationProviderProfileState.APPROVED
    )
    provider_profile_effective_from: datetime | None = None
    provider_profile_effective_until: datetime | None = None
    provider_profile_digest: str = ""
    processing_authorization_reference: str = (
        MARKET_OPTIONALITY_AI_EXPLANATION_PROCESSING_AUTHORIZATION_REFERENCE
    )
    processing_authorization_version: int = (
        MARKET_OPTIONALITY_AI_EXPLANATION_PROCESSING_AUTHORIZATION_VERSION
    )
    processing_authorization_effective_from: datetime | None = None
    processing_authorization_effective_until: datetime | None = None
    processing_authorization_digest: str = ""

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
        profile = MarketOptionExplanationProviderProfile(
            profile_id=self.provider_profile,
            profile_version=self.provider_profile_version,
            lifecycle_state=self.provider_profile_state,
            effective_from=self.provider_profile_effective_from,
            effective_until=self.provider_profile_effective_until,
            profile_digest=self.provider_profile_digest,
        )
        object.__setattr__(self, "provider_profile_digest", profile.profile_digest)
        authorization = MarketOptionExplanationProviderProcessingAuthorization(
            organization_id=self.processing_authorization_organization_id,
            purpose=self.processing_authorization_purpose,
            provider_profile=self.provider_profile,
            provider_profile_version=self.provider_profile_version,
            data_contract_id=self.data_contract_id,
            data_contract_version=self.data_contract_version,
            authorization_reference=self.processing_authorization_reference,
            authorization_version=self.processing_authorization_version,
            effective_from=self.processing_authorization_effective_from,
            effective_until=self.processing_authorization_effective_until,
            authorization_digest=self.processing_authorization_digest,
        )
        object.__setattr__(
            self,
            "processing_authorization_digest",
            authorization.authorization_digest,
        )

    def provider_profile_snapshot(self) -> MarketOptionExplanationProviderProfile:
        return MarketOptionExplanationProviderProfile(
            profile_id=self.provider_profile,
            profile_version=self.provider_profile_version,
            lifecycle_state=self.provider_profile_state,
            effective_from=self.provider_profile_effective_from,
            effective_until=self.provider_profile_effective_until,
            profile_digest=self.provider_profile_digest,
        )

    def provider_processing_authorization_snapshot(
        self,
    ) -> MarketOptionExplanationProviderProcessingAuthorization:
        return MarketOptionExplanationProviderProcessingAuthorization(
            organization_id=self.processing_authorization_organization_id,
            purpose=self.processing_authorization_purpose,
            provider_profile=self.provider_profile,
            provider_profile_version=self.provider_profile_version,
            data_contract_id=self.data_contract_id,
            data_contract_version=self.data_contract_version,
            authorization_reference=self.processing_authorization_reference,
            authorization_version=self.processing_authorization_version,
            effective_from=self.processing_authorization_effective_from,
            effective_until=self.processing_authorization_effective_until,
            authorization_digest=self.processing_authorization_digest,
        )


def _canonical_digest(schema: str, value: object) -> str:
    canonical = CanonicalSerializer().serialize(
        {
            "schema": schema,
            "value": canonicalize_for_hash(value),
        }
    )
    return hashlib.sha256(canonical).hexdigest()


MarketOptionExplanationPromptValue = str | tuple[str, ...] | tuple[Mapping[str, str], ...]


@dataclass(frozen=True, slots=True)
class MarketOptionExplanationPromptTemplate:
    template_id: str = MARKET_OPTIONALITY_AI_EXPLANATION_PROMPT_TEMPLATE_ID
    template_version: int = MARKET_OPTIONALITY_AI_EXPLANATION_PROMPT_TEMPLATE_VERSION
    template_text: str = MARKET_OPTIONALITY_AI_EXPLANATION_PROMPT_TEMPLATE_TEXT
    explanation_schema: str = MARKET_OPTIONALITY_AI_EXPLANATION_SCHEMA
    guard_version: int = MARKET_OPTIONALITY_AI_EXPLANATION_GUARD_VERSION
    template_digest: str = ""
    guard_digest: str = ""

    def __post_init__(self) -> None:
        for field_name in ("template_id", "template_text", "explanation_schema"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} deve ser texto não vazio.")
        if not isinstance(self.template_version, int) or self.template_version < 1:
            raise ValueError("template_version deve ser inteiro >= 1.")
        if not isinstance(self.guard_version, int) or self.guard_version < 1:
            raise ValueError("guard_version deve ser inteiro >= 1.")

        expected_template_digest = _canonical_digest(
            "titan.livestock.market_optionality.ai_prompt_template",
            {
                "template_id": self.template_id,
                "template_version": self.template_version,
                "template_text": self.template_text,
                "explanation_schema": self.explanation_schema,
            },
        )
        expected_guard_digest = _canonical_digest(
            "titan.livestock.market_optionality.ai_explanation_guard",
            {
                "guard_version": self.guard_version,
                "violations": tuple(
                    violation.value for violation in MarketOptionExplanationViolation
                ),
                "allowed_assertion": MarketOptionExplanationAssertion.CANONICAL_SUMMARY.value,
            },
        )
        if self.template_digest and self.template_digest != expected_template_digest:
            raise ValueError("template_digest não corresponde ao prompt template.")
        if self.guard_digest and self.guard_digest != expected_guard_digest:
            raise ValueError("guard_digest não corresponde ao guard declarado.")
        object.__setattr__(self, "template_digest", expected_template_digest)
        object.__setattr__(self, "guard_digest", expected_guard_digest)


@dataclass(frozen=True, slots=True)
class MarketOptionExplanationPromptPayload:
    data_contract_id: str
    data_contract_version: int
    schema: str
    prompt_template_id: str
    prompt_template_version: int
    prompt_template_digest: str
    guard_version: int
    guard_digest: str
    payload_digest: str
    fields: Mapping[str, MarketOptionExplanationPromptValue]
    source_reference_aliases: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class MarketOptionExplanationAuditEnvelope:
    data_contract_id: str
    data_contract_version: int
    processing_activity: str
    processing_authorization_reference: str
    processing_authorization_version: int
    processing_authorization_digest: str
    provider_profile: str
    provider_profile_version: int
    provider_profile_digest: str
    model_name: str
    explanation_schema: str
    prompt_template_id: str
    prompt_template_version: int
    prompt_template_digest: str
    guard_version: int
    guard_digest: str
    prompt_payload_digest: str
    source_reference_digest: str
    canonical_fallback_digest: str
    released_output_digest: str | None
    accepted: bool
    violation_codes: tuple[str, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.accepted and self.released_output_digest is None:
            raise ValueError("released_output_digest é obrigatório para explicação liberada.")
        if not self.accepted and self.released_output_digest is not None:
            raise ValueError("released_output_digest deve ficar ausente quando guard rejeita.")


@dataclass(frozen=True, slots=True)
class MarketOptionExplanationResult:
    run_context: MarketOptionExplanationRunContext
    explanation_context: MarketOptionExplanationContext
    prompt_payload: MarketOptionExplanationPromptPayload
    audit_envelope: MarketOptionExplanationAuditEnvelope
    validation: MarketOptionExplanationValidation
    released_text: str | None
    canonical_fallback: MarketOptionCanonicalExplanation


class MarketOptionExplanationTextProvider(Protocol):
    def generate_text(
        self,
        *,
        prompt_payload: MarketOptionExplanationPromptPayload,
        run_context: MarketOptionExplanationRunContext,
    ) -> str: ...


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

        if draft.schema != MARKET_OPTIONALITY_AI_EXPLANATION_DRAFT_SCHEMA:
            violations.append(MarketOptionExplanationViolation.DRAFT_SCHEMA_MISMATCH)
        allowed_claim_refs = set(_claim_refs_for_context(context))
        draft_claim_refs = {
            claim_ref for section in draft.sections for claim_ref in section.claim_refs
        }
        if not draft_claim_refs.issubset(allowed_claim_refs):
            violations.append(MarketOptionExplanationViolation.UNKNOWN_CLAIM_REFERENCE)
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
        if _contains_prohibited_explanation_text(draft.text):
            violations.append(MarketOptionExplanationViolation.PROHIBITED_TEXT_CONTENT)
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
class DeterministicMarketOptionExplanationTextProvider:
    """Local fake text provider for tests; it receives only the prompt payload."""

    def generate_text(
        self,
        *,
        prompt_payload: MarketOptionExplanationPromptPayload,
        run_context: MarketOptionExplanationRunContext,
    ) -> str:
        return (
            "Resumo canônico sintético: estado "
            f"{prompt_payload.fields['option_state']} para "
            f"{prompt_payload.fields['market_purpose']}."
        )


@dataclass(frozen=True, slots=True)
class MarketOptionExplanationDataContractService:
    """Builds the minimal provider-facing payload allowed by ADR-0074."""

    data_contract_id: str = MARKET_OPTIONALITY_AI_EXPLANATION_SYNTHETIC_CONTRACT_ID
    data_contract_version: int = MARKET_OPTIONALITY_AI_EXPLANATION_CONTRACT_VERSION
    schema: str = MARKET_OPTIONALITY_AI_EXPLANATION_SCHEMA
    prompt_template: MarketOptionExplanationPromptTemplate = field(
        default_factory=MarketOptionExplanationPromptTemplate
    )
    allowed_fields: tuple[str, ...] = (
        "audience",
        "subject_type",
        "market_purpose",
        "policy_version",
        "reference_time",
        "knowledge_cutoff",
        "option_state",
        "reversibility",
        "claims",
        "reason_aliases",
        "missing_evidence_aliases",
        "limitation_aliases",
        "context_limitation_aliases",
        "output_classification",
        "disclosure_restrictions",
    )

    def build_prompt_payload(
        self,
        *,
        explanation_context: MarketOptionExplanationContext,
        run_context: MarketOptionExplanationRunContext,
    ) -> MarketOptionExplanationPromptPayload:
        if run_context.data_contract_id != self.data_contract_id:
            raise ValueError("data_contract_id não está aprovado para AI Explanation.")
        if run_context.data_contract_version != self.data_contract_version:
            raise ValueError("data_contract_version não está aprovada para AI Explanation.")

        aliases: dict[str, str] = {}
        claims: list[Mapping[str, str]] = []
        for index, claim in enumerate(explanation_context.allowed_claims, start=1):
            alias = f"claim_source:{index}"
            aliases[alias] = claim.source_reference
            claims.append(
                MappingProxyType(
                    {
                        "claim_ref": _claim_ref(index),
                        "type": claim.claim_type.value,
                        "value": claim.value,
                        "source_alias": alias,
                    }
                )
            )

        assessment = explanation_context.assessment
        fields: dict[str, MarketOptionExplanationPromptValue] = {
            "audience": explanation_context.audience.value,
            "subject_type": assessment.context.subject_id.entity_type,
            "market_purpose": assessment.context.market_purpose,
            "policy_version": str(assessment.context.policy_version),
            "reference_time": assessment.context.reference_time.isoformat(),
            "knowledge_cutoff": assessment.context.knowledge_cutoff.isoformat(),
            "option_state": assessment.state.value,
            "reversibility": assessment.reversibility.value,
            "claims": tuple(claims),
            "reason_aliases": _provider_safe_alias_tuple("reason", assessment.reason_codes),
            "missing_evidence_aliases": _provider_safe_alias_tuple(
                "missing_evidence", assessment.missing_evidence_types
            ),
            "limitation_aliases": _provider_safe_alias_tuple("limitation", assessment.limitations),
            "context_limitation_aliases": _provider_safe_alias_tuple(
                "context_limitation", explanation_context.limitations
            ),
            "output_classification": MARKET_OPTIONALITY_AI_EXPLANATION_OUTPUT_CLASSIFICATION,
            "disclosure_restrictions": (MARKET_OPTIONALITY_AI_EXPLANATION_DISCLOSURE_RESTRICTIONS),
        }
        unexpected = set(fields) - set(self.allowed_fields)
        missing = set(self.allowed_fields) - set(fields)
        if unexpected or missing:
            raise ValueError("AI Explanation DataContract field set inválido.")
        payload_digest = _canonical_digest(
            "titan.livestock.market_optionality.ai_prompt_payload",
            {
                "data_contract_id": self.data_contract_id,
                "data_contract_version": self.data_contract_version,
                "schema": self.schema,
                "prompt_template_id": self.prompt_template.template_id,
                "prompt_template_version": self.prompt_template.template_version,
                "prompt_template_digest": self.prompt_template.template_digest,
                "guard_version": self.prompt_template.guard_version,
                "guard_digest": self.prompt_template.guard_digest,
                "fields": fields,
            },
        )

        return MarketOptionExplanationPromptPayload(
            data_contract_id=self.data_contract_id,
            data_contract_version=self.data_contract_version,
            schema=self.schema,
            prompt_template_id=self.prompt_template.template_id,
            prompt_template_version=self.prompt_template.template_version,
            prompt_template_digest=self.prompt_template.template_digest,
            guard_version=self.prompt_template.guard_version,
            guard_digest=self.prompt_template.guard_digest,
            payload_digest=payload_digest,
            fields=MappingProxyType(fields),
            source_reference_aliases=MappingProxyType(aliases),
        )


@dataclass(frozen=True, slots=True)
class MarketOptionExplanationAuditEnvelopeService:
    """Creates minimized audit material; it does not persist prompts or outputs."""

    def build(
        self,
        *,
        run_context: MarketOptionExplanationRunContext,
        explanation_context: MarketOptionExplanationContext,
        prompt_payload: MarketOptionExplanationPromptPayload,
        validation: MarketOptionExplanationValidation,
        released_text: str | None,
        canonical_fallback: MarketOptionCanonicalExplanation,
    ) -> MarketOptionExplanationAuditEnvelope:
        source_reference_digest = _canonical_digest(
            "titan.livestock.market_optionality.ai_source_references",
            dict(explanation_context.source_references),
        )
        fallback_digest = _canonical_digest(
            "titan.livestock.market_optionality.ai_canonical_fallback",
            canonical_fallback.as_mapping(),
        )
        released_output_digest = (
            _canonical_digest(
                "titan.livestock.market_optionality.ai_released_output",
                {
                    "text": released_text,
                    "prompt_payload_digest": prompt_payload.payload_digest,
                    "guard_digest": prompt_payload.guard_digest,
                },
            )
            if validation.accepted and released_text is not None
            else None
        )

        return MarketOptionExplanationAuditEnvelope(
            data_contract_id=prompt_payload.data_contract_id,
            data_contract_version=prompt_payload.data_contract_version,
            processing_activity=run_context.processing_activity,
            processing_authorization_reference=(run_context.processing_authorization_reference),
            processing_authorization_version=run_context.processing_authorization_version,
            processing_authorization_digest=run_context.processing_authorization_digest,
            provider_profile=run_context.provider_profile,
            provider_profile_version=run_context.provider_profile_version,
            provider_profile_digest=run_context.provider_profile_digest,
            model_name=run_context.model_name,
            explanation_schema=prompt_payload.schema,
            prompt_template_id=prompt_payload.prompt_template_id,
            prompt_template_version=prompt_payload.prompt_template_version,
            prompt_template_digest=prompt_payload.prompt_template_digest,
            guard_version=prompt_payload.guard_version,
            guard_digest=prompt_payload.guard_digest,
            prompt_payload_digest=prompt_payload.payload_digest,
            source_reference_digest=source_reference_digest,
            canonical_fallback_digest=fallback_digest,
            released_output_digest=released_output_digest,
            accepted=validation.accepted,
            violation_codes=tuple(violation.value for violation in validation.violations),
            limitations=validation.limitations,
        )


@dataclass(frozen=True, slots=True)
class MarketOptionExplanationPipelineService:
    """Composes draft generation with deterministic guards before releasing text."""

    text_provider: MarketOptionExplanationTextProvider = (
        DeterministicMarketOptionExplanationTextProvider()
    )
    guard_service: MarketOptionExplanationGuardService = MarketOptionExplanationGuardService()
    data_contract_service: MarketOptionExplanationDataContractService = (
        MarketOptionExplanationDataContractService()
    )
    audit_envelope_service: MarketOptionExplanationAuditEnvelopeService = (
        MarketOptionExplanationAuditEnvelopeService()
    )

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
        prompt_payload = self.data_contract_service.build_prompt_payload(
            explanation_context=explanation_context,
            run_context=run_context,
        )
        canonical_fallback = _canonical_explanation_fallback(assessment)
        provider_profile = run_context.provider_profile_snapshot()
        processing_authorization = run_context.provider_processing_authorization_snapshot()
        if not processing_authorization.is_compatible_with(
            assessment=assessment,
            run_context=run_context,
        ):
            validation = MarketOptionExplanationValidation(
                accepted=False,
                violations=(MarketOptionExplanationViolation.PROVIDER_PROCESSING_UNAUTHORIZED,),
                limitations=explanation_context.limitations,
            )
            released_text = None
        elif not provider_profile.is_available_at(assessment.context.knowledge_cutoff):
            validation = MarketOptionExplanationValidation(
                accepted=False,
                violations=(MarketOptionExplanationViolation.PROVIDER_PROFILE_UNAVAILABLE,),
                limitations=explanation_context.limitations,
            )
            released_text = None
        else:
            try:
                provider_text = self.text_provider.generate_text(
                    prompt_payload=prompt_payload,
                    run_context=run_context,
                )
            except Exception:
                validation = MarketOptionExplanationValidation(
                    accepted=False,
                    violations=(MarketOptionExplanationViolation.PROVIDER_UNAVAILABLE,),
                    limitations=explanation_context.limitations,
                )
                released_text = None
            else:
                validation, released_text = self._validate_provider_text_for_release(
                    provider_text=provider_text,
                    explanation_context=explanation_context,
                    run_context=run_context,
                    provider_profile=provider_profile,
                )
        audit_envelope = self.audit_envelope_service.build(
            run_context=run_context,
            explanation_context=explanation_context,
            prompt_payload=prompt_payload,
            validation=validation,
            released_text=released_text,
            canonical_fallback=canonical_fallback,
        )
        return MarketOptionExplanationResult(
            run_context=run_context,
            explanation_context=explanation_context,
            prompt_payload=prompt_payload,
            audit_envelope=audit_envelope,
            validation=validation,
            released_text=released_text,
            canonical_fallback=canonical_fallback,
        )

    def _validate_provider_text_for_release(
        self,
        *,
        provider_text: str,
        explanation_context: MarketOptionExplanationContext,
        run_context: MarketOptionExplanationRunContext,
        provider_profile: MarketOptionExplanationProviderProfile,
    ) -> tuple[MarketOptionExplanationValidation, str | None]:
        draft = _draft_from_provider_text(
            provider_text=provider_text,
            explanation_context=explanation_context,
        )
        validation = self.guard_service.validate_draft(
            context=explanation_context,
            draft=draft,
        )
        if not validation.accepted:
            return validation, None
        if not provider_profile.is_available_at(
            explanation_context.assessment.context.knowledge_cutoff
        ):
            return (
                MarketOptionExplanationValidation(
                    accepted=False,
                    violations=(MarketOptionExplanationViolation.PROVIDER_PROFILE_UNAVAILABLE,),
                    limitations=explanation_context.limitations,
                ),
                None,
            )
        return validation, draft.text


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
) -> MarketOptionCanonicalExplanation:
    return MarketOptionCanonicalExplanation(
        state=assessment.state,
        reversibility=assessment.reversibility,
        policy_id=assessment.context.policy_id,
        policy_version=assessment.context.policy_version,
        reference_time=assessment.context.reference_time,
        knowledge_cutoff=assessment.context.knowledge_cutoff,
        output_classification=MARKET_OPTIONALITY_AI_EXPLANATION_OUTPUT_CLASSIFICATION,
        disclosure_restrictions=MARKET_OPTIONALITY_AI_EXPLANATION_DISCLOSURE_RESTRICTIONS,
        result_boundary=assessment.result_boundary,
    )


def _provider_safe_alias_tuple(
    namespace: str,
    values: tuple[str, ...],
) -> tuple[Mapping[str, str], ...]:
    return tuple(
        MappingProxyType(
            {
                "alias": f"{namespace}:{index}",
            }
        )
        for index, _value in enumerate(values, start=1)
    )


def _claim_ref(index: int) -> str:
    return f"claim:{index}"


def _claim_refs_for_context(
    context: MarketOptionExplanationContext,
) -> tuple[str, ...]:
    return tuple(_claim_ref(index) for index, _claim in enumerate(context.allowed_claims, start=1))


def _draft_from_provider_text(
    *,
    provider_text: str,
    explanation_context: MarketOptionExplanationContext,
) -> MarketOptionExplanationDraft:
    assessment = explanation_context.assessment
    return MarketOptionExplanationDraft(
        text=provider_text,
        decision_id=assessment.decision_id,
        evaluation_id=assessment.evaluation_id,
        policy_id=assessment.context.policy_id,
        policy_version=assessment.context.policy_version,
        option_state=assessment.state,
        referenced_reason_codes=assessment.reason_codes,
        referenced_missing_evidence_types=assessment.missing_evidence_types,
        referenced_limitations=assessment.limitations,
        referenced_claims=explanation_context.allowed_claims,
        sections=(
            MarketOptionExplanationDraftSection(
                claim_refs=_claim_refs_for_context(explanation_context),
                text=provider_text,
            ),
        ),
    )


def _contains_prohibited_explanation_text(text: str) -> bool:
    normalized = text.casefold()
    prohibited_fragments = (
        "certificado",
        "certificate",
        "export_allowed",
        "export allowed",
        "eligible",
        "elegível",
        "elegivel",
        "future eligibility",
        "garantia futura",
        "reconhecimento oficial",
        "official recognition",
    )
    return any(fragment in normalized for fragment in prohibited_fragments)


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
