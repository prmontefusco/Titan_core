"""Aggregation privacy controls for future Market Supply visibility.

This module evaluates an already-built aggregate result before release. It does
not resolve cross-tenant populations, persist audit records, expose APIs, or
define a production privacy profile.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from packages.shared_kernel import OrganizationId
from packages.shared_kernel.temporal import require_utc

MARKET_SUPPLY_AGGREGATION_PRIVACY_POLICY_VERSION = 1
MARKET_SUPPLY_PRIVACY_PROFILE_CONFIG_KEYS = (
    "PROFILE_ID",
    "POLICY_VERSION",
    "MINIMUM_ORGANIZATIONS",
    "MINIMUM_PROPERTIES",
    "MINIMUM_SUBJECTS",
    "MAX_FILTER_COUNT_WITHOUT_REVIEW",
    "REPEATED_QUERY_WINDOW_SECONDS",
)


class AggregationGeographicPrecision(StrEnum):
    NONE = "NONE"
    REGION = "REGION"
    MUNICIPALITY = "MUNICIPALITY"
    PROPERTY = "PROPERTY"
    PRECISE = "PRECISE"


class AggregationPrivacyDecision(StrEnum):
    PERMITTED = "PERMITTED"
    SUPPRESSED = "SUPPRESSED"


class DisclosureDecisionState(StrEnum):
    ALLOW = "ALLOW"
    GENERALIZE = "GENERALIZE"
    SUPPRESS = "SUPPRESS"
    DENY = "DENY"


class AggregationPrivacyReason(StrEnum):
    PERMITTED = "PERMITTED"
    INSUFFICIENT_ORGANIZATION_COHORT = "INSUFFICIENT_ORGANIZATION_COHORT"
    INSUFFICIENT_PROPERTY_COHORT = "INSUFFICIENT_PROPERTY_COHORT"
    INSUFFICIENT_SUBJECT_COHORT = "INSUFFICIENT_SUBJECT_COHORT"
    HIGH_GEOGRAPHIC_PRECISION = "HIGH_GEOGRAPHIC_PRECISION"
    RARE_ATTRIBUTE_FILTER = "RARE_ATTRIBUTE_FILTER"
    EXCESSIVE_FILTER_COMBINATION = "EXCESSIVE_FILTER_COMBINATION"
    DIFFERENCING_RISK = "DIFFERENCING_RISK"
    REPEATED_QUERY_RISK = "REPEATED_QUERY_RISK"


@dataclass(frozen=True, slots=True)
class AggregationPrivacyPolicy:
    """Explicit policy profile selected by the caller.

    Titan intentionally ships no global production threshold here. Product and
    Security must approve concrete profile values before buyer-facing use.
    """

    policy_version: int
    minimum_organizations: int
    minimum_properties: int
    minimum_subjects: int
    max_filter_count_without_review: int
    repeated_query_window: timedelta

    def __post_init__(self) -> None:
        for field_name in (
            "policy_version",
            "minimum_organizations",
            "minimum_properties",
            "minimum_subjects",
            "max_filter_count_without_review",
        ):
            if getattr(self, field_name) < 1:
                raise ValueError(f"{field_name} deve ser maior ou igual a 1.")
        if self.repeated_query_window <= timedelta(0):
            raise ValueError("repeated_query_window deve ser positivo.")


@dataclass(frozen=True, slots=True)
class AggregationPrivacyProfile:
    """Versioned privacy profile explicitly supplied by deployment/configuration."""

    profile_id: str
    policy: AggregationPrivacyPolicy

    def __post_init__(self) -> None:
        if not self.profile_id.strip():
            raise ValueError("profile_id deve ser texto nao vazio.")


def load_aggregation_privacy_profile(
    values: Mapping[str, str],
    *,
    prefix: str = "TITAN_MARKET_SUPPLY_PRIVACY_",
) -> AggregationPrivacyProfile:
    """Builds a profile only from explicit configuration values.

    This intentionally has no production defaults. Missing configuration keeps
    F3.5 fail-closed instead of smuggling arbitrary thresholds into the domain.
    """

    raw = {
        key: _required_config(values, f"{prefix}{key}")
        for key in MARKET_SUPPLY_PRIVACY_PROFILE_CONFIG_KEYS
    }
    return AggregationPrivacyProfile(
        profile_id=raw["PROFILE_ID"],
        policy=AggregationPrivacyPolicy(
            policy_version=_positive_int(raw["POLICY_VERSION"], field_name="POLICY_VERSION"),
            minimum_organizations=_positive_int(
                raw["MINIMUM_ORGANIZATIONS"],
                field_name="MINIMUM_ORGANIZATIONS",
            ),
            minimum_properties=_positive_int(
                raw["MINIMUM_PROPERTIES"],
                field_name="MINIMUM_PROPERTIES",
            ),
            minimum_subjects=_positive_int(raw["MINIMUM_SUBJECTS"], field_name="MINIMUM_SUBJECTS"),
            max_filter_count_without_review=_positive_int(
                raw["MAX_FILTER_COUNT_WITHOUT_REVIEW"],
                field_name="MAX_FILTER_COUNT_WITHOUT_REVIEW",
            ),
            repeated_query_window=timedelta(
                seconds=_positive_int(
                    raw["REPEATED_QUERY_WINDOW_SECONDS"],
                    field_name="REPEATED_QUERY_WINDOW_SECONDS",
                ),
            ),
        ),
    )


@dataclass(frozen=True, slots=True)
class AggregationQueryFingerprint:
    requester_organization_id: OrganizationId
    beneficiary_organization_id: OrganizationId
    access_purpose: str
    policy_context_digest: str
    filter_fingerprint: str
    result_subject_count: int
    requested_at: datetime

    def __post_init__(self) -> None:
        if not self.access_purpose.strip():
            raise ValueError("access_purpose deve ser texto nao vazio.")
        if not self.policy_context_digest.strip():
            raise ValueError("policy_context_digest deve ser texto nao vazio.")
        if not self.filter_fingerprint.strip():
            raise ValueError("filter_fingerprint deve ser texto nao vazio.")
        if self.result_subject_count < 0:
            raise ValueError("result_subject_count nao pode ser negativo.")
        require_utc(self.requested_at, field_name="requested_at")


@dataclass(frozen=True, slots=True)
class AggregationPrivacyInput:
    privacy_policy: AggregationPrivacyPolicy
    organization_count: int
    property_count: int
    subject_count: int
    geographic_precision: AggregationGeographicPrecision
    filter_count: int
    rare_attribute_filters: tuple[str, ...]
    current_query: AggregationQueryFingerprint
    previous_queries: tuple[AggregationQueryFingerprint, ...] = ()

    def __post_init__(self) -> None:
        for field_name in ("organization_count", "property_count", "subject_count", "filter_count"):
            if getattr(self, field_name) < 0:
                raise ValueError(f"{field_name} nao pode ser negativo.")
        if self.current_query.result_subject_count != self.subject_count:
            raise ValueError("current_query.result_subject_count deve refletir subject_count.")


@dataclass(frozen=True, slots=True)
class AggregationPrivacyAssessment:
    decision: AggregationPrivacyDecision
    reasons: tuple[AggregationPrivacyReason, ...]
    policy_version: int

    @property
    def permitted(self) -> bool:
        return self.decision is AggregationPrivacyDecision.PERMITTED

    def to_disclosure_decision(
        self,
        *,
        query_fingerprint: AggregationQueryFingerprint,
        candidate_population_digest: str,
        evaluated_at: datetime,
    ) -> "DisclosureDecision":
        state = (
            DisclosureDecisionState.ALLOW
            if self.decision is AggregationPrivacyDecision.PERMITTED
            else DisclosureDecisionState.SUPPRESS
        )
        return DisclosureDecision(
            state=state,
            reason_codes=tuple(reason.value for reason in self.reasons),
            privacy_policy_version=self.policy_version,
            query_fingerprint=query_fingerprint,
            candidate_population_digest=candidate_population_digest,
            evaluated_at=evaluated_at,
        )


@dataclass(frozen=True, slots=True)
class DisclosureDecision:
    """Immutable disclosure decision for an aggregate Market Supply query.

    This is not a regulatory Evaluation or Decision. It only states whether an
    analytical aggregate can be externally disclosed in the current context.
    """

    state: DisclosureDecisionState
    reason_codes: tuple[str, ...]
    privacy_policy_version: int
    query_fingerprint: AggregationQueryFingerprint
    candidate_population_digest: str
    evaluated_at: datetime

    def __post_init__(self) -> None:
        if self.privacy_policy_version < 1:
            raise ValueError("privacy_policy_version deve ser inteiro >= 1.")
        if not self.candidate_population_digest.strip():
            raise ValueError("candidate_population_digest deve ser texto nao vazio.")
        if not self.reason_codes:
            raise ValueError("reason_codes deve conter ao menos um codigo.")
        for reason in self.reason_codes:
            if not reason.strip():
                raise ValueError("reason_codes nao aceita valor vazio.")
        require_utc(self.evaluated_at, field_name="evaluated_at")

    @property
    def allows_external_release(self) -> bool:
        return self.state in {
            DisclosureDecisionState.ALLOW,
            DisclosureDecisionState.GENERALIZE,
        }


class AggregationPrivacyAssessmentService:
    """Assesses whether an aggregate can be released without field-level detail."""

    def assess(self, privacy_input: AggregationPrivacyInput) -> AggregationPrivacyAssessment:
        reasons: list[AggregationPrivacyReason] = []
        policy = privacy_input.privacy_policy

        if privacy_input.organization_count < policy.minimum_organizations:
            reasons.append(AggregationPrivacyReason.INSUFFICIENT_ORGANIZATION_COHORT)
        if privacy_input.property_count < policy.minimum_properties:
            reasons.append(AggregationPrivacyReason.INSUFFICIENT_PROPERTY_COHORT)
        if privacy_input.subject_count < policy.minimum_subjects:
            reasons.append(AggregationPrivacyReason.INSUFFICIENT_SUBJECT_COHORT)
        if privacy_input.geographic_precision in (
            AggregationGeographicPrecision.PROPERTY,
            AggregationGeographicPrecision.PRECISE,
        ):
            reasons.append(AggregationPrivacyReason.HIGH_GEOGRAPHIC_PRECISION)
        if privacy_input.rare_attribute_filters:
            reasons.append(AggregationPrivacyReason.RARE_ATTRIBUTE_FILTER)
        if privacy_input.filter_count > policy.max_filter_count_without_review:
            reasons.append(AggregationPrivacyReason.EXCESSIVE_FILTER_COMBINATION)
        if _has_differencing_risk(privacy_input):
            reasons.append(AggregationPrivacyReason.DIFFERENCING_RISK)
        if _has_repeated_query_risk(privacy_input):
            reasons.append(AggregationPrivacyReason.REPEATED_QUERY_RISK)

        if reasons:
            return AggregationPrivacyAssessment(
                decision=AggregationPrivacyDecision.SUPPRESSED,
                reasons=tuple(reasons),
                policy_version=policy.policy_version,
            )
        return AggregationPrivacyAssessment(
            decision=AggregationPrivacyDecision.PERMITTED,
            reasons=(AggregationPrivacyReason.PERMITTED,),
            policy_version=policy.policy_version,
        )


def _has_differencing_risk(privacy_input: AggregationPrivacyInput) -> bool:
    current = privacy_input.current_query
    minimum_subjects = privacy_input.privacy_policy.minimum_subjects
    for previous in privacy_input.previous_queries:
        if not _same_context(current, previous):
            continue
        if current.filter_fingerprint == previous.filter_fingerprint:
            continue
        if abs(current.result_subject_count - previous.result_subject_count) < minimum_subjects:
            return True
    return False


def _has_repeated_query_risk(privacy_input: AggregationPrivacyInput) -> bool:
    current = privacy_input.current_query
    window = privacy_input.privacy_policy.repeated_query_window
    for previous in privacy_input.previous_queries:
        if not _same_context(current, previous):
            continue
        if current.filter_fingerprint != previous.filter_fingerprint:
            continue
        elapsed = current.requested_at - previous.requested_at
        if timedelta(0) <= elapsed < window:
            return True
    return False


def _same_context(
    current: AggregationQueryFingerprint,
    previous: AggregationQueryFingerprint,
) -> bool:
    return (
        current.requester_organization_id == previous.requester_organization_id
        and current.beneficiary_organization_id == previous.beneficiary_organization_id
        and current.access_purpose == previous.access_purpose
        and current.policy_context_digest == previous.policy_context_digest
    )


def _required_config(values: Mapping[str, str], name: str) -> str:
    value = values.get(name, "").strip()
    if not value:
        raise ValueError(f"{name} deve ser configurado explicitamente.")
    return value


def _positive_int(value: str, *, field_name: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise ValueError(f"{field_name} deve ser inteiro positivo.") from error
    if parsed < 1:
        raise ValueError(f"{field_name} deve ser inteiro positivo.")
    return parsed
