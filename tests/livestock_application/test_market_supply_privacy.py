from datetime import UTC, datetime, timedelta

import pytest

from packages.livestock_application.market_supply_privacy import (
    MARKET_SUPPLY_AGGREGATION_PRIVACY_POLICY_VERSION,
    AggregationGeographicPrecision,
    AggregationPrivacyAssessmentService,
    AggregationPrivacyDecision,
    AggregationPrivacyInput,
    AggregationPrivacyPolicy,
    AggregationPrivacyProfile,
    AggregationPrivacyReason,
    AggregationQueryFingerprint,
    DisclosureDecisionState,
    load_aggregation_privacy_profile,
)
from packages.shared_kernel import OrganizationId

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)


def _policy() -> AggregationPrivacyPolicy:
    return AggregationPrivacyPolicy(
        policy_version=MARKET_SUPPLY_AGGREGATION_PRIVACY_POLICY_VERSION,
        minimum_organizations=3,
        minimum_properties=5,
        minimum_subjects=20,
        max_filter_count_without_review=4,
        repeated_query_window=timedelta(hours=6),
    )


def _fingerprint(
    *,
    requester: OrganizationId | None = None,
    beneficiary: OrganizationId | None = None,
    access_purpose: str = "MARKET_SUPPLY_AGGREGATE_ASSESSMENT",
    policy_context_digest: str = "policy:v1:reference:2026-08-28",
    filter_fingerprint: str = "region=macro-a|breed=all",
    result_subject_count: int = 100,
    requested_at: datetime = NOW,
) -> AggregationQueryFingerprint:
    return AggregationQueryFingerprint(
        requester_organization_id=requester or OrganizationId.new(),
        beneficiary_organization_id=beneficiary or OrganizationId.new(),
        access_purpose=access_purpose,
        policy_context_digest=policy_context_digest,
        filter_fingerprint=filter_fingerprint,
        result_subject_count=result_subject_count,
        requested_at=requested_at,
    )


def _privacy_input(
    *,
    organization_count: int = 4,
    property_count: int = 8,
    subject_count: int = 100,
    geographic_precision: AggregationGeographicPrecision = AggregationGeographicPrecision.REGION,
    filter_count: int = 2,
    rare_attribute_filters: tuple[str, ...] = (),
    current_query: AggregationQueryFingerprint | None = None,
    previous_queries: tuple[AggregationQueryFingerprint, ...] = (),
) -> AggregationPrivacyInput:
    query = current_query or _fingerprint(result_subject_count=subject_count)
    return AggregationPrivacyInput(
        privacy_policy=_policy(),
        organization_count=organization_count,
        property_count=property_count,
        subject_count=subject_count,
        geographic_precision=geographic_precision,
        filter_count=filter_count,
        rare_attribute_filters=rare_attribute_filters,
        current_query=query,
        previous_queries=previous_queries,
    )


def test_aggregate_release_is_permitted_when_policy_controls_pass() -> None:
    assessment = AggregationPrivacyAssessmentService().assess(_privacy_input())

    assert assessment.permitted is True
    assert assessment.decision is AggregationPrivacyDecision.PERMITTED
    assert assessment.reasons == (AggregationPrivacyReason.PERMITTED,)
    assert assessment.policy_version == MARKET_SUPPLY_AGGREGATION_PRIVACY_POLICY_VERSION

    disclosure = assessment.to_disclosure_decision(
        query_fingerprint=_fingerprint(),
        candidate_population_digest="population:sha256:abc",
        evaluated_at=NOW,
    )

    assert disclosure.state is DisclosureDecisionState.ALLOW
    assert disclosure.allows_external_release is True
    assert disclosure.reason_codes == ("PERMITTED",)


def test_aggregate_release_is_suppressed_when_cohorts_are_too_small() -> None:
    assessment = AggregationPrivacyAssessmentService().assess(
        _privacy_input(
            organization_count=2,
            property_count=4,
            subject_count=19,
        ),
    )

    assert assessment.permitted is False
    assert assessment.reasons == (
        AggregationPrivacyReason.INSUFFICIENT_ORGANIZATION_COHORT,
        AggregationPrivacyReason.INSUFFICIENT_PROPERTY_COHORT,
        AggregationPrivacyReason.INSUFFICIENT_SUBJECT_COHORT,
    )


@pytest.mark.parametrize(
    "precision",
    [
        AggregationGeographicPrecision.PROPERTY,
        AggregationGeographicPrecision.PRECISE,
    ],
)
def test_property_or_precise_geography_is_suppressed(
    precision: AggregationGeographicPrecision,
) -> None:
    assessment = AggregationPrivacyAssessmentService().assess(
        _privacy_input(geographic_precision=precision),
    )

    assert assessment.permitted is False
    assert assessment.reasons == (AggregationPrivacyReason.HIGH_GEOGRAPHIC_PRECISION,)


def test_rare_attributes_and_excessive_filter_combinations_are_suppressed() -> None:
    assessment = AggregationPrivacyAssessmentService().assess(
        _privacy_input(
            filter_count=5,
            rare_attribute_filters=("rare-breed", "small-window"),
        ),
    )

    assert assessment.permitted is False
    assert assessment.reasons == (
        AggregationPrivacyReason.RARE_ATTRIBUTE_FILTER,
        AggregationPrivacyReason.EXCESSIVE_FILTER_COMBINATION,
    )


def test_related_query_with_small_delta_is_suppressed_as_differencing_risk() -> None:
    requester = OrganizationId.new()
    beneficiary = OrganizationId.new()
    previous = _fingerprint(
        requester=requester,
        beneficiary=beneficiary,
        filter_fingerprint="region=macro-a",
        result_subject_count=112,
        requested_at=NOW - timedelta(days=1),
    )
    current = _fingerprint(
        requester=requester,
        beneficiary=beneficiary,
        filter_fingerprint="region=macro-a|breed=nelore",
        result_subject_count=100,
        requested_at=NOW,
    )

    assessment = AggregationPrivacyAssessmentService().assess(
        _privacy_input(
            subject_count=100,
            current_query=current,
            previous_queries=(previous,),
        ),
    )

    assert assessment.permitted is False
    assert assessment.reasons == (AggregationPrivacyReason.DIFFERENCING_RISK,)

    disclosure = assessment.to_disclosure_decision(
        query_fingerprint=current,
        candidate_population_digest="population:sha256:abc",
        evaluated_at=NOW,
    )

    assert disclosure.state is DisclosureDecisionState.SUPPRESS
    assert disclosure.allows_external_release is False
    assert disclosure.reason_codes == ("DIFFERENCING_RISK",)


def test_unrelated_previous_query_does_not_create_differencing_risk() -> None:
    previous = _fingerprint(
        requester=OrganizationId.new(),
        beneficiary=OrganizationId.new(),
        filter_fingerprint="region=macro-a",
        result_subject_count=112,
        requested_at=NOW - timedelta(days=1),
    )

    assessment = AggregationPrivacyAssessmentService().assess(
        _privacy_input(previous_queries=(previous,)),
    )

    assert assessment.permitted is True


def test_repeated_query_inside_policy_window_is_suppressed() -> None:
    requester = OrganizationId.new()
    beneficiary = OrganizationId.new()
    previous = _fingerprint(
        requester=requester,
        beneficiary=beneficiary,
        result_subject_count=100,
        requested_at=NOW - timedelta(hours=1),
    )
    current = _fingerprint(
        requester=requester,
        beneficiary=beneficiary,
        result_subject_count=100,
        requested_at=NOW,
    )

    assessment = AggregationPrivacyAssessmentService().assess(
        _privacy_input(current_query=current, previous_queries=(previous,)),
    )

    assert assessment.permitted is False
    assert assessment.reasons == (AggregationPrivacyReason.REPEATED_QUERY_RISK,)


def test_policy_and_query_inputs_validate_temporal_and_count_semantics() -> None:
    with pytest.raises(ValueError, match="minimum_subjects"):
        AggregationPrivacyPolicy(
            policy_version=1,
            minimum_organizations=1,
            minimum_properties=1,
            minimum_subjects=0,
            max_filter_count_without_review=1,
            repeated_query_window=timedelta(hours=1),
        )

    with pytest.raises(ValueError, match="requested_at"):
        _fingerprint(requested_at=datetime(2026, 8, 28, 12, 0))

    with pytest.raises(ValueError, match="result_subject_count"):
        _privacy_input(
            subject_count=100,
            current_query=_fingerprint(result_subject_count=99),
        )


def test_disclosure_decision_requires_population_digest_and_utc_evaluation_time() -> None:
    assessment = AggregationPrivacyAssessmentService().assess(_privacy_input())

    with pytest.raises(ValueError, match="candidate_population_digest"):
        assessment.to_disclosure_decision(
            query_fingerprint=_fingerprint(),
            candidate_population_digest="",
            evaluated_at=NOW,
        )

    with pytest.raises(ValueError, match="evaluated_at"):
        assessment.to_disclosure_decision(
            query_fingerprint=_fingerprint(),
            candidate_population_digest="population:sha256:abc",
            evaluated_at=datetime(2026, 8, 28, 12, 0),
        )


def test_privacy_profile_loader_requires_explicit_configuration_without_defaults() -> None:
    with pytest.raises(ValueError, match="TITAN_MARKET_SUPPLY_PRIVACY_PROFILE_ID"):
        load_aggregation_privacy_profile({})


def test_privacy_profile_loader_builds_versioned_profile_from_explicit_values() -> None:
    profile = load_aggregation_privacy_profile(
        {
            "TITAN_MARKET_SUPPLY_PRIVACY_PROFILE_ID": "market-supply-aggregate-v1",
            "TITAN_MARKET_SUPPLY_PRIVACY_POLICY_VERSION": "7",
            "TITAN_MARKET_SUPPLY_PRIVACY_MINIMUM_ORGANIZATIONS": "4",
            "TITAN_MARKET_SUPPLY_PRIVACY_MINIMUM_PROPERTIES": "8",
            "TITAN_MARKET_SUPPLY_PRIVACY_MINIMUM_SUBJECTS": "40",
            "TITAN_MARKET_SUPPLY_PRIVACY_MAX_FILTER_COUNT_WITHOUT_REVIEW": "3",
            "TITAN_MARKET_SUPPLY_PRIVACY_REPEATED_QUERY_WINDOW_SECONDS": "21600",
        },
    )

    assert profile == AggregationPrivacyProfile(
        profile_id="market-supply-aggregate-v1",
        policy=AggregationPrivacyPolicy(
            policy_version=7,
            minimum_organizations=4,
            minimum_properties=8,
            minimum_subjects=40,
            max_filter_count_without_review=3,
            repeated_query_window=timedelta(hours=6),
        ),
    )


def test_privacy_profile_loader_rejects_invalid_numeric_values() -> None:
    values = {
        "TITAN_MARKET_SUPPLY_PRIVACY_PROFILE_ID": "market-supply-aggregate-v1",
        "TITAN_MARKET_SUPPLY_PRIVACY_POLICY_VERSION": "7",
        "TITAN_MARKET_SUPPLY_PRIVACY_MINIMUM_ORGANIZATIONS": "0",
        "TITAN_MARKET_SUPPLY_PRIVACY_MINIMUM_PROPERTIES": "8",
        "TITAN_MARKET_SUPPLY_PRIVACY_MINIMUM_SUBJECTS": "40",
        "TITAN_MARKET_SUPPLY_PRIVACY_MAX_FILTER_COUNT_WITHOUT_REVIEW": "3",
        "TITAN_MARKET_SUPPLY_PRIVACY_REPEATED_QUERY_WINDOW_SECONDS": "21600",
    }

    with pytest.raises(ValueError, match="MINIMUM_ORGANIZATIONS"):
        load_aggregation_privacy_profile(values)
