from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from packages.core_domain.policy_sharing import AuthorizationGrant
from packages.livestock_application.market_supply_authorization import (
    MARKET_SUPPLY_AGGREGATE_ASSESSMENT,
    MARKET_SUPPLY_AGGREGATE_FIELD_SCOPE,
    MarketSupplyAuthorizationReason,
)
from packages.livestock_application.market_supply_population import (
    AuthorizedCandidatePopulationContribution,
    AuthorizedCandidatePopulationRejection,
    AuthorizedCandidatePopulationResolver,
    CandidatePopulationCriteria,
    CandidatePopulationResolver,
    CandidatePopulationSnapshot,
    CandidatePopulationSubject,
)
from packages.shared_kernel import OrganizationId, TypedId

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)


def _criteria(
    *,
    organization_id: OrganizationId | None = None,
    excluded_subject_ids: tuple[TypedId, ...] = (),
    required_tags: tuple[str, ...] = ("approved-network",),
) -> CandidatePopulationCriteria:
    return CandidatePopulationCriteria(
        organization_id=organization_id or OrganizationId.new(),
        purpose="MARKET_SUPPLY_AGGREGATE_ASSESSMENT",
        policy_id=TypedId.new("policy"),
        policy_version=1,
        reference_time=NOW,
        knowledge_cutoff=NOW,
        commercial_window_start=NOW + timedelta(days=1),
        commercial_window_end=NOW + timedelta(days=30),
        required_tags=required_tags,
        excluded_subject_ids=excluded_subject_ids,
    )


def _subject(
    criteria: CandidatePopulationCriteria,
    *,
    subject_id: TypedId | None = None,
    organization_id: OrganizationId | None = None,
    property_id: TypedId | None = None,
    tags: tuple[str, ...] = ("approved-network",),
    accessible: bool = True,
    known_at: datetime | None = NOW - timedelta(days=1),
) -> CandidatePopulationSubject:
    return CandidatePopulationSubject(
        subject_id=subject_id or TypedId.new("animal"),
        organization_id=organization_id or criteria.organization_id,
        property_id=property_id,
        tags=tags,
        accessible=accessible,
        known_at=known_at,
    )


def _grant(
    *,
    criteria: CandidatePopulationCriteria,
    buyer_organization_id: OrganizationId,
    status: str = "ATIVO",
    revoked_at: datetime | None = None,
    owner_organization_id: OrganizationId | None = None,
) -> AuthorizationGrant:
    return AuthorizationGrant(
        grant_id=uuid4(),
        owner_organization_id=owner_organization_id or criteria.organization_id,
        beneficiary_organization_id=buyer_organization_id,
        policy_id=criteria.policy_id,
        policy_version_id=TypedId.new("policy_version"),
        access_purpose=MARKET_SUPPLY_AGGREGATE_ASSESSMENT,
        field_scope_profile=MARKET_SUPPLY_AGGREGATE_FIELD_SCOPE,
        valid_from=NOW - timedelta(days=1),
        valid_until=NOW + timedelta(days=1),
        status=status,
        created_at=NOW - timedelta(days=2),
        created_by="test",
        revoked_at=revoked_at,
    )


def test_resolver_builds_reproducible_snapshot_independent_of_input_order() -> None:
    criteria = _criteria()
    first = _subject(criteria)
    second = _subject(criteria)

    snapshot_a = CandidatePopulationResolver().resolve(
        criteria=criteria,
        subjects=(first, second),
        resolved_at=NOW,
    )
    snapshot_b = CandidatePopulationResolver().resolve(
        criteria=criteria,
        subjects=(second, first),
        resolved_at=NOW,
    )

    assert snapshot_a.included_count == 2
    assert snapshot_a.excluded_count == 0
    assert snapshot_a.criteria_digest == snapshot_b.criteria_digest
    assert snapshot_a.snapshot_digest == snapshot_b.snapshot_digest


def test_policy_context_digest_relates_queries_without_collapsing_snapshot_identity() -> None:
    subject_to_exclude = TypedId.new("animal")
    base = _criteria(required_tags=("approved-network",))
    narrowed = replace(
        base,
        required_tags=("approved-network", "finished"),
        excluded_subject_ids=(subject_to_exclude,),
    )
    first_subject = _subject(base, subject_id=subject_to_exclude, tags=("approved-network",))
    second_subject = _subject(base, tags=("approved-network", "finished"))

    base_snapshot = CandidatePopulationResolver().resolve(
        criteria=base,
        subjects=(first_subject, second_subject),
        resolved_at=NOW,
    )
    narrowed_snapshot = CandidatePopulationResolver().resolve(
        criteria=narrowed,
        subjects=(first_subject, second_subject),
        resolved_at=NOW,
    )

    assert base.policy_context_digest() == narrowed.policy_context_digest()
    assert base.digest() != narrowed.digest()
    assert base_snapshot.snapshot_digest != narrowed_snapshot.snapshot_digest


def test_resolver_records_explicit_and_authorization_exclusions_as_counts() -> None:
    explicitly_excluded = TypedId.new("animal")
    criteria = _criteria(excluded_subject_ids=(explicitly_excluded,))
    subjects = (
        _subject(criteria, subject_id=explicitly_excluded),
        _subject(criteria, accessible=False),
        _subject(criteria),
    )

    snapshot = CandidatePopulationResolver().resolve(
        criteria=criteria,
        subjects=subjects,
        resolved_at=NOW,
    )

    assert snapshot.included_count == 1
    assert snapshot.excluded_count == 2
    assert [(item.reason, item.count) for item in snapshot.excluded_summary] == [
        ("EXPLICITLY_EXCLUDED", 1),
        ("NOT_AUTHORIZED_OR_INACCESSIBLE", 1),
    ]


def test_later_known_subject_is_excluded_without_interpreting_absence_as_negative() -> None:
    criteria = _criteria()
    subject = _subject(criteria, known_at=NOW + timedelta(seconds=1))

    snapshot = CandidatePopulationResolver().resolve(
        criteria=criteria,
        subjects=(subject,),
        resolved_at=NOW,
    )

    assert snapshot.included_count == 0
    assert snapshot.excluded_summary[0].reason == "NOT_KNOWN_AT_CUTOFF"


def test_subject_from_other_organization_is_excluded_from_snapshot() -> None:
    criteria = _criteria()
    subject = _subject(criteria, organization_id=OrganizationId.new())

    snapshot = CandidatePopulationResolver().resolve(
        criteria=criteria,
        subjects=(subject,),
        resolved_at=NOW,
    )

    assert snapshot.included_count == 0
    assert snapshot.excluded_summary[0].reason == "ORGANIZATION_MISMATCH"


def test_public_summary_omits_individual_subject_ids() -> None:
    criteria = _criteria()
    subject = _subject(criteria)

    snapshot = CandidatePopulationResolver().resolve(
        criteria=criteria,
        subjects=(subject,),
        resolved_at=NOW,
    )

    summary = snapshot.public_summary()

    assert summary["included_count"] == 1
    assert "included_subject_ids" not in summary
    assert str(subject.subject_id.value) not in repr(summary)


def test_internal_universe_summary_carries_digests_and_counts_without_public_ids() -> None:
    criteria = _criteria()
    property_id = TypedId.new("property")
    included = _subject(criteria, property_id=property_id)
    inaccessible = _subject(criteria, accessible=False)

    snapshot = CandidatePopulationResolver().resolve(
        criteria=criteria,
        subjects=(included, inaccessible),
        resolved_at=NOW,
    )

    summary = snapshot.internal_universe_summary()

    assert summary.authorized_sources_digest
    assert summary.selection_criteria_digest == snapshot.criteria_digest
    assert summary.population_digest
    assert summary.population_size == 2
    assert summary.organization_count == 1
    assert summary.property_count == 1
    assert summary.subject_count == 1
    assert str(included.subject_id.value) not in repr(snapshot.public_summary())
    assert str(property_id.value) not in repr(snapshot.public_summary())


def test_internal_universe_summary_marks_property_count_unknown_when_subject_lacks_property() -> (
    None
):
    criteria = _criteria()

    snapshot = CandidatePopulationResolver().resolve(
        criteria=criteria,
        subjects=(_subject(criteria),),
        resolved_at=NOW,
    )

    assert snapshot.internal_universe_summary().property_count is None


def test_snapshot_rejects_tampered_digest() -> None:
    criteria = _criteria()
    snapshot = CandidatePopulationResolver().resolve(
        criteria=criteria,
        subjects=(_subject(criteria),),
        resolved_at=NOW,
    )

    with pytest.raises(ValueError, match="snapshot_digest"):
        CandidatePopulationSnapshot(
            criteria=snapshot.criteria,
            resolved_at=snapshot.resolved_at,
            included_subject_ids=snapshot.included_subject_ids,
            included_organization_ids=snapshot.included_organization_ids,
            included_property_ids=snapshot.included_property_ids,
            excluded_summary=snapshot.excluded_summary,
            criteria_digest=snapshot.criteria_digest,
            snapshot_digest="0" * 64,
        )


def test_criteria_validates_temporal_and_policy_semantics() -> None:
    with pytest.raises(ValueError, match="reference_time"):
        CandidatePopulationCriteria(
            organization_id=OrganizationId.new(),
            purpose="MARKET_SUPPLY_AGGREGATE_ASSESSMENT",
            policy_id=TypedId.new("policy"),
            policy_version=1,
            reference_time=datetime(2026, 8, 28, 12, 0),
            knowledge_cutoff=NOW,
        )

    with pytest.raises(ValueError, match="policy_id"):
        replace(_criteria(), policy_id=TypedId.new("animal"))

    with pytest.raises(ValueError, match="commercial_window_start"):
        replace(
            _criteria(),
            commercial_window_start=NOW + timedelta(days=2),
            commercial_window_end=NOW + timedelta(days=1),
        )


def test_authorized_population_resolver_snapshots_only_grant_authorized_contributions() -> None:
    buyer = OrganizationId.new()
    authorized_criteria = _criteria()
    unauthorized_criteria = _criteria()
    authorized_subject = _subject(authorized_criteria)
    unauthorized_subject = _subject(unauthorized_criteria)

    result = AuthorizedCandidatePopulationResolver().resolve_authorized(
        buyer_organization_id=buyer,
        contributions=(
            AuthorizedCandidatePopulationContribution(
                criteria=authorized_criteria,
                subjects=(authorized_subject,),
                grant=_grant(criteria=authorized_criteria, buyer_organization_id=buyer),
            ),
            AuthorizedCandidatePopulationContribution(
                criteria=unauthorized_criteria,
                subjects=(unauthorized_subject,),
                grant=None,
            ),
        ),
        resolved_at=NOW,
    )

    assert result.included_count == 1
    assert result.rejected_subject_count == 1
    assert len(result.snapshots) == 1
    assert result.snapshots[0].criteria.organization_id == authorized_criteria.organization_id
    assert result.rejected_contributions == (
        AuthorizedCandidatePopulationRejection(
            owner_organization_id=unauthorized_criteria.organization_id,
            reason=MarketSupplyAuthorizationReason.MISSING_GRANT,
            subject_count=1,
        ),
    )


def test_authorized_population_resolver_rejects_revoked_contribution_without_snapshot() -> None:
    buyer = OrganizationId.new()
    criteria = _criteria()

    result = AuthorizedCandidatePopulationResolver().resolve_authorized(
        buyer_organization_id=buyer,
        contributions=(
            AuthorizedCandidatePopulationContribution(
                criteria=criteria,
                subjects=(_subject(criteria),),
                grant=_grant(
                    criteria=criteria,
                    buyer_organization_id=buyer,
                    revoked_at=NOW - timedelta(minutes=1),
                ),
            ),
        ),
        resolved_at=NOW,
    )

    assert result.snapshots == ()
    assert result.rejected_contributions[0].reason is MarketSupplyAuthorizationReason.REVOKED_GRANT
    assert result.rejected_subject_count == 1


def test_authorized_population_resolver_rejects_owner_mismatch_before_snapshot() -> None:
    buyer = OrganizationId.new()
    criteria = _criteria()

    result = AuthorizedCandidatePopulationResolver().resolve_authorized(
        buyer_organization_id=buyer,
        contributions=(
            AuthorizedCandidatePopulationContribution(
                criteria=criteria,
                subjects=(_subject(criteria),),
                grant=_grant(
                    criteria=criteria,
                    buyer_organization_id=buyer,
                    owner_organization_id=OrganizationId.new(),
                ),
            ),
        ),
        resolved_at=NOW,
    )

    assert result.snapshots == ()
    assert result.rejected_contributions[0].reason is (
        MarketSupplyAuthorizationReason.OWNER_ORGANIZATION_MISMATCH
    )
