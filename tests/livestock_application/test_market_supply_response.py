from dataclasses import replace
from datetime import UTC, datetime

import pytest

from packages.livestock_application.market_supply_audit import (
    MarketSupplyAggregateQueryAuditEnvelope,
    MarketSupplyAuditExternalDisposition,
    MarketSupplyAuditOutcome,
)
from packages.livestock_application.market_supply_authorization import (
    MARKET_SUPPLY_AGGREGATE_ASSESSMENT,
    MARKET_SUPPLY_AGGREGATE_FIELD_SCOPE,
)
from packages.livestock_application.market_supply_privacy import AggregationQueryFingerprint
from packages.livestock_application.market_supply_response import (
    MARKET_SUPPLY_NO_STORE_HEADERS,
    MARKET_SUPPLY_PUBLIC_AGGREGATE_RESPONSE_SCHEMA,
    MARKET_SUPPLY_PUBLIC_AGGREGATE_RESPONSE_VERSION,
    MarketSupplyPublicResponseMapper,
    MarketSupplyPublicResponseStatus,
)
from packages.shared_kernel import OrganizationId, TypedId

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)


def _envelope(
    *,
    outcome: MarketSupplyAuditOutcome = MarketSupplyAuditOutcome.RELEASED,
    disposition: MarketSupplyAuditExternalDisposition = (
        MarketSupplyAuditExternalDisposition.RELEASE_AGGREGATE
    ),
) -> MarketSupplyAggregateQueryAuditEnvelope:
    requester = OrganizationId.new()
    beneficiary = OrganizationId.new()
    return MarketSupplyAggregateQueryAuditEnvelope(
        audit_owner_organization_id=OrganizationId.new(),
        requester_organization_id=requester,
        beneficiary_organization_id=beneficiary,
        policy_id=TypedId.new("policy"),
        access_purpose=MARKET_SUPPLY_AGGREGATE_ASSESSMENT,
        field_scope_profile=MARKET_SUPPLY_AGGREGATE_FIELD_SCOPE,
        query_fingerprint=AggregationQueryFingerprint(
            requester_organization_id=requester,
            beneficiary_organization_id=beneficiary,
            access_purpose=MARKET_SUPPLY_AGGREGATE_ASSESSMENT,
            policy_context_digest="policy:v1:reference:2026-08-28",
            filter_fingerprint="region=macro-a",
            result_subject_count=42,
            requested_at=NOW,
        ),
        recorded_at=NOW,
        outcome=outcome,
        external_disposition=disposition,
        authorization_reason="PERMITTED",
        privacy_reasons=("PERMITTED",),
    )


def test_authorization_denial_and_privacy_suppression_have_same_public_shape() -> None:
    denied = _envelope(
        outcome=MarketSupplyAuditOutcome.DENIED_BY_AUTHORIZATION,
        disposition=MarketSupplyAuditExternalDisposition.UNIFORM_NOT_RELEASED,
    )
    suppressed = replace(
        denied,
        outcome=MarketSupplyAuditOutcome.SUPPRESSED_BY_PRIVACY,
        authorization_reason="PERMITTED",
        privacy_reasons=("DIFFERENCING_RISK",),
    )

    mapper = MarketSupplyPublicResponseMapper()

    assert mapper.map_aggregate(envelope=denied, aggregate_payload=None) == mapper.map_aggregate(
        envelope=suppressed,
        aggregate_payload=None,
    )


def test_not_released_public_response_does_not_expose_internal_reasons() -> None:
    response = MarketSupplyPublicResponseMapper().map_aggregate(
        envelope=_envelope(
            outcome=MarketSupplyAuditOutcome.SUPPRESSED_BY_PRIVACY,
            disposition=MarketSupplyAuditExternalDisposition.UNIFORM_NOT_RELEASED,
        ),
        aggregate_payload={"ready_now": 42},
    )

    assert response.status is MarketSupplyPublicResponseStatus.NOT_RELEASED
    assert response.released is False
    assert response.aggregate is None


def test_released_response_contains_only_supplied_aggregate_payload() -> None:
    response = MarketSupplyPublicResponseMapper().map_aggregate(
        envelope=_envelope(),
        aggregate_payload={"ready_now": 42, "not_ready": 3},
    )

    assert response.status is MarketSupplyPublicResponseStatus.RELEASED
    assert response.released is True
    assert response.aggregate == {"ready_now": 42, "not_ready": 3}


def test_released_response_rejects_field_outside_public_allow_list() -> None:
    with pytest.raises(ValueError, match="schema publico"):
        MarketSupplyPublicResponseMapper().map_aggregate(
            envelope=_envelope(),
            aggregate_payload={"ready_now": 42, "raw_fact": "hidden"},
        )


def test_released_response_rejects_individual_identifiers() -> None:
    with pytest.raises(ValueError, match="identificadores"):
        MarketSupplyPublicResponseMapper().map_aggregate(
            envelope=_envelope(),
            aggregate_payload={"animal_id": "animal-1"},
        )


def test_released_response_rejects_identifier_like_gap_values() -> None:
    with pytest.raises(ValueError, match="membership protegido"):
        MarketSupplyPublicResponseMapper().map_aggregate(
            envelope=_envelope(),
            aggregate_payload={"gap_summary": [{"code": "PROPERTY_123", "count": 1}]},
        )


def test_released_response_accepts_only_aggregate_gap_summary_shape() -> None:
    response = MarketSupplyPublicResponseMapper().map_aggregate(
        envelope=_envelope(),
        aggregate_payload={
            "readiness_counts": {
                "READY": 3,
                "CONDITIONED": 2,
                "INDETERMINATE": 1,
                "NOT_READY": 1,
                "NOT_EVALUATED": 1,
                "REASSESSMENT_REQUIRED": 0,
            },
            "gap_summary": [{"code": "DOCUMENTATION_GAP", "count": 1}],
            "limitations": ["synthetic aggregate only"],
        },
    )

    assert response.aggregate == {
        "readiness_counts": {
            "READY": 3,
            "CONDITIONED": 2,
            "INDETERMINATE": 1,
            "NOT_READY": 1,
            "NOT_EVALUATED": 1,
            "REASSESSMENT_REQUIRED": 0,
        },
        "gap_summary": ({"code": "DOCUMENTATION_GAP", "count": 1},),
        "limitations": ("synthetic aggregate only",),
    }


def test_released_response_rejects_nested_unapproved_readiness_key() -> None:
    with pytest.raises(ValueError, match="schema publico"):
        MarketSupplyPublicResponseMapper().map_aggregate(
            envelope=_envelope(),
            aggregate_payload={"readiness_counts": {"READY": 3, "EU_ELIGIBLE": 1}},
        )


def test_public_response_builds_stable_canonical_payload_for_idempotent_replay() -> None:
    response = MarketSupplyPublicResponseMapper().map_aggregate(
        envelope=_envelope(),
        aggregate_payload={"ready_now": 42, "not_ready": 3},
    )
    same_response = MarketSupplyPublicResponseMapper().map_aggregate(
        envelope=_envelope(),
        aggregate_payload={"not_ready": 3, "ready_now": 42},
    )

    payload = response.to_canonical_payload()

    assert payload.schema == MARKET_SUPPLY_PUBLIC_AGGREGATE_RESPONSE_SCHEMA
    assert payload.version == MARKET_SUPPLY_PUBLIC_AGGREGATE_RESPONSE_VERSION
    assert payload.canonical_bytes == same_response.to_canonical_payload().canonical_bytes


def test_not_released_canonical_payload_omits_aggregate_and_internal_reason() -> None:
    denied = MarketSupplyPublicResponseMapper().map_aggregate(
        envelope=_envelope(
            outcome=MarketSupplyAuditOutcome.PURPOSE_MISMATCH,
            disposition=MarketSupplyAuditExternalDisposition.UNIFORM_NOT_RELEASED,
        ),
        aggregate_payload={"ready_now": 42},
    )
    suppressed = MarketSupplyPublicResponseMapper().map_aggregate(
        envelope=_envelope(
            outcome=MarketSupplyAuditOutcome.SUPPRESSED_BY_PRIVACY,
            disposition=MarketSupplyAuditExternalDisposition.UNIFORM_NOT_RELEASED,
        ),
        aggregate_payload={"ready_now": 42},
    )

    assert denied.to_canonical_payload().canonical_bytes == (
        suppressed.to_canonical_payload().canonical_bytes
    )
    assert b"ready_now" not in denied.to_canonical_payload().canonical_bytes
    assert b"PURPOSE_MISMATCH" not in denied.to_canonical_payload().canonical_bytes


def test_released_response_requires_aggregate_payload() -> None:
    with pytest.raises(ValueError, match="aggregate_payload"):
        MarketSupplyPublicResponseMapper().map_aggregate(
            envelope=_envelope(),
            aggregate_payload=None,
        )


def test_market_supply_public_response_headers_are_no_store_for_release_and_non_release() -> None:
    mapper = MarketSupplyPublicResponseMapper()

    assert mapper.sensitive_response_headers() == MARKET_SUPPLY_NO_STORE_HEADERS
    assert mapper.sensitive_response_headers() == {
        "Cache-Control": "no-store",
        "Pragma": "no-cache",
    }
