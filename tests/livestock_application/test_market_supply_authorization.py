from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from packages.core_domain.policy_sharing import AuthorizationGrant
from packages.livestock_application.market_supply_authorization import (
    MARKET_SUPPLY_AGGREGATE_ASSESSMENT,
    MARKET_SUPPLY_AGGREGATE_FIELD_SCOPE,
    MARKET_SUPPLY_CANDIDATE_DISCLOSURE,
    MARKET_SUPPLY_CANDIDATE_DISCLOSURE_FIELD_SCOPE,
    MarketSupplyAuthorizationReason,
    MarketSupplyAuthorizationRequest,
    MarketSupplyAuthorizationService,
)
from packages.shared_kernel import OrganizationId, TypedId

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)


def _request(
    *,
    owner: OrganizationId | None = None,
    beneficiary: OrganizationId | None = None,
    policy_id: TypedId | None = None,
    purpose: str = MARKET_SUPPLY_AGGREGATE_ASSESSMENT,
    field_scope: str = MARKET_SUPPLY_AGGREGATE_FIELD_SCOPE,
    requested_at: datetime = NOW,
) -> MarketSupplyAuthorizationRequest:
    return MarketSupplyAuthorizationRequest(
        owner_organization_id=owner or OrganizationId.new(),
        beneficiary_organization_id=beneficiary or OrganizationId.new(),
        policy_id=policy_id or TypedId.new("policy"),
        access_purpose=purpose,
        field_scope_profile=field_scope,
        requested_at=requested_at,
    )


def _grant(
    request: MarketSupplyAuthorizationRequest,
    *,
    purpose: str | None = None,
    field_scope: str | None = None,
    status: str = "ATIVO",
    valid_from: datetime | None = None,
    valid_until: datetime | None = None,
    revoked_at: datetime | None = None,
) -> AuthorizationGrant:
    return AuthorizationGrant(
        grant_id=uuid4(),
        owner_organization_id=request.owner_organization_id,
        beneficiary_organization_id=request.beneficiary_organization_id,
        policy_id=request.policy_id,
        policy_version_id=TypedId.new("rule"),
        access_purpose=purpose or request.access_purpose,
        field_scope_profile=field_scope or request.field_scope_profile,
        valid_from=valid_from or NOW - timedelta(days=1),
        valid_until=valid_until or NOW + timedelta(days=1),
        status=status,
        created_at=NOW - timedelta(days=1),
        created_by="actor:test",
        revoked_at=revoked_at,
    )


def test_aggregate_assessment_requires_active_matching_grant() -> None:
    request = _request()
    grant = _grant(request)

    assessment = MarketSupplyAuthorizationService().assess_aggregate_access(
        request=request,
        grant=grant,
    )

    assert assessment.permitted is True
    assert assessment.reason is MarketSupplyAuthorizationReason.PERMITTED


def test_missing_grant_denies_without_implying_data_absence() -> None:
    request = _request()

    assessment = MarketSupplyAuthorizationService().assess_aggregate_access(
        request=request,
        grant=None,
    )

    assert assessment.permitted is False
    assert assessment.reason is MarketSupplyAuthorizationReason.MISSING_GRANT


@pytest.mark.parametrize(
    "case",
    [
        "revoked",
        "expired",
        "owner_mismatch",
        "beneficiary_mismatch",
        "policy_mismatch",
        "purpose_mismatch",
        "field_scope_mismatch",
    ],
)
def test_aggregate_assessment_denies_non_matching_grants(case: str) -> None:
    request = _request()
    base_grant = _grant(request)
    expected = {
        "revoked": MarketSupplyAuthorizationReason.INACTIVE_GRANT,
        "expired": MarketSupplyAuthorizationReason.EXPIRED_OR_NOT_YET_VALID,
        "owner_mismatch": MarketSupplyAuthorizationReason.OWNER_ORGANIZATION_MISMATCH,
        "beneficiary_mismatch": MarketSupplyAuthorizationReason.BENEFICIARY_ORGANIZATION_MISMATCH,
        "policy_mismatch": MarketSupplyAuthorizationReason.POLICY_MISMATCH,
        "purpose_mismatch": MarketSupplyAuthorizationReason.PURPOSE_MISMATCH,
        "field_scope_mismatch": MarketSupplyAuthorizationReason.FIELD_SCOPE_MISMATCH,
    }
    grant = {
        "revoked": replace(base_grant, status="REVOGADO"),
        "expired": replace(base_grant, valid_until=NOW),
        "owner_mismatch": replace(base_grant, owner_organization_id=OrganizationId.new()),
        "beneficiary_mismatch": replace(
            base_grant,
            beneficiary_organization_id=OrganizationId.new(),
        ),
        "policy_mismatch": replace(base_grant, policy_id=TypedId.new("policy")),
        "purpose_mismatch": replace(base_grant, access_purpose="MARKET_SUPPLY"),
        "field_scope_mismatch": replace(
            base_grant,
            field_scope_profile="BROAD_MARKET_SUPPLY",
        ),
    }[case]

    assessment = MarketSupplyAuthorizationService().assess_aggregate_access(
        request=request,
        grant=grant,
    )

    assert assessment.permitted is False
    assert assessment.reason is expected[case]


def test_aggregate_purpose_never_authorizes_candidate_disclosure() -> None:
    aggregate_request = _request()
    aggregate_grant = _grant(aggregate_request)
    candidate_request = _request(
        owner=aggregate_request.owner_organization_id,
        beneficiary=aggregate_request.beneficiary_organization_id,
        policy_id=aggregate_request.policy_id,
        purpose=MARKET_SUPPLY_CANDIDATE_DISCLOSURE,
        field_scope=MARKET_SUPPLY_CANDIDATE_DISCLOSURE_FIELD_SCOPE,
    )

    assessment = MarketSupplyAuthorizationService().assess_candidate_disclosure(
        request=candidate_request,
        grant=aggregate_grant,
    )

    assert assessment.permitted is False
    assert assessment.reason is MarketSupplyAuthorizationReason.PURPOSE_MISMATCH


def test_candidate_disclosure_requires_its_own_purpose_and_field_scope() -> None:
    request = _request(
        purpose=MARKET_SUPPLY_CANDIDATE_DISCLOSURE,
        field_scope=MARKET_SUPPLY_CANDIDATE_DISCLOSURE_FIELD_SCOPE,
    )
    grant = _grant(request)

    assessment = MarketSupplyAuthorizationService().assess_candidate_disclosure(
        request=request,
        grant=grant,
    )

    assert assessment.permitted is True
    assert assessment.access_purpose == MARKET_SUPPLY_CANDIDATE_DISCLOSURE


def test_revoked_at_blocks_access_from_effective_instant_even_if_status_is_stale() -> None:
    request = _request()
    grant = _grant(request, revoked_at=NOW)

    assessment = MarketSupplyAuthorizationService().assess_aggregate_access(
        request=request,
        grant=grant,
    )

    assert assessment.permitted is False
    assert assessment.reason is MarketSupplyAuthorizationReason.REVOKED_GRANT


def test_revoked_at_is_prospective_and_does_not_block_past_request() -> None:
    revoked_at = NOW + timedelta(minutes=1)
    request = _request(requested_at=NOW)
    grant = _grant(request, revoked_at=revoked_at)

    assessment = MarketSupplyAuthorizationService().assess_aggregate_access(
        request=request,
        grant=grant,
    )

    assert assessment.permitted is True


def test_revoked_at_blocks_later_request() -> None:
    revoked_at = NOW - timedelta(minutes=1)
    request = _request(requested_at=NOW)
    grant = _grant(request, revoked_at=revoked_at)

    assessment = MarketSupplyAuthorizationService().assess_aggregate_access(
        request=request,
        grant=grant,
    )

    assert assessment.permitted is False
    assert assessment.reason is MarketSupplyAuthorizationReason.REVOKED_GRANT


def test_request_requires_policy_id_and_utc_requested_at() -> None:
    with pytest.raises(ValueError, match="policy_id"):
        _request(policy_id=TypedId.new("animal"))

    with pytest.raises(ValueError, match="requested_at"):
        _request(requested_at=datetime(2026, 8, 28, 12, 0))
