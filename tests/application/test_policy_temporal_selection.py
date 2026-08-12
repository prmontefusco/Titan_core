from dataclasses import replace
from datetime import UTC, datetime

from packages.core_application.policy_temporal_selection import (
    PolicySelectionOutcome,
    PolicySelectionReason,
    PolicySelectionRequest,
    PolicyTemporalCandidate,
    PolicyTemporalResolver,
)
from packages.core_domain.policy import Policy, PolicyStatus
from packages.shared_kernel import OrganizationId, TypedId

ORG = OrganizationId.new()
BOUNDARY = datetime(2026, 7, 1, tzinfo=UTC)


def policy(version: int, start: datetime, end: datetime | None) -> Policy:
    return Policy(
        policy_id=TypedId.new("policy"),
        organization_id=ORG,
        code="market_test_a",
        name=f"Market Test A v{version}",
        description="Policy inteiramente fictícia.",
        version=version,
        status=PolicyStatus.PUBLISHED if version == 2 else PolicyStatus.SUPERSEDED,
        valid_from=start,
        valid_to=end,
        published_at=start,
    )


def candidate(item: Policy, known_at: datetime | None = None) -> PolicyTemporalCandidate:
    return PolicyTemporalCandidate(
        policy=item,
        purpose="market-test-a",
        known_at=known_at or item.published_at or item.valid_from,  # type: ignore[arg-type]
        knowledge_basis="TITAN_INTERNAL_PUBLICATION",
    )


def request(
    reference_time: datetime, knowledge_cutoff: datetime | None = None
) -> PolicySelectionRequest:
    return PolicySelectionRequest(
        organization_id=ORG,
        policy_code="MARKET_TEST_A",
        purpose="market-test-a",
        reference_time=reference_time,
        knowledge_cutoff=knowledge_cutoff or reference_time,
    )


def versions() -> tuple[PolicyTemporalCandidate, ...]:
    return (
        candidate(policy(1, datetime(2026, 1, 1, tzinfo=UTC), BOUNDARY)),
        candidate(policy(2, BOUNDARY, None)),
    )


def test_selects_version_one_for_may() -> None:
    result = PolicyTemporalResolver().resolve(request(datetime(2026, 5, 1, tzinfo=UTC)), versions())
    assert result.outcome is PolicySelectionOutcome.SELECTED
    assert result.selected_policy is not None and result.selected_policy.version == 1


def test_selects_version_two_for_august() -> None:
    result = PolicyTemporalResolver().resolve(request(datetime(2026, 8, 1, tzinfo=UTC)), versions())
    assert result.outcome is PolicySelectionOutcome.SELECTED
    assert result.selected_policy is not None and result.selected_policy.version == 2


def test_valid_to_is_exclusive_at_boundary() -> None:
    result = PolicyTemporalResolver().resolve(request(BOUNDARY), versions())
    assert result.outcome is PolicySelectionOutcome.SELECTED
    assert result.selected_policy is not None and result.selected_policy.version == 2


def test_policy_known_after_cutoff_produces_gap_without_fallback() -> None:
    v1, v2 = versions()
    late_v2 = replace(v2, known_at=datetime(2026, 7, 10, tzinfo=UTC))
    result = PolicyTemporalResolver().resolve(
        request(datetime(2026, 7, 5, tzinfo=UTC), datetime(2026, 7, 6, tzinfo=UTC)),
        (v1, late_v2),
    )
    assert result.outcome is PolicySelectionOutcome.TEMPORAL_GAP
    assert result.reason_codes == (PolicySelectionReason.LACUNA_TEMPORAL,)


def test_retrospective_selection_can_use_later_declared_knowledge() -> None:
    v1, v2 = versions()
    late_v2 = replace(v2, known_at=datetime(2026, 7, 10, tzinfo=UTC))
    result = PolicyTemporalResolver().resolve(
        request(datetime(2026, 7, 5, tzinfo=UTC), datetime(2026, 7, 15, tzinfo=UTC)),
        (v1, late_v2),
    )
    assert result.outcome is PolicySelectionOutcome.SELECTED
    assert result.selected_policy is not None and result.selected_policy.version == 2


def test_overlap_is_ambiguous_and_never_chooses_highest_version() -> None:
    v1, v2 = versions()
    overlapping_v1 = replace(v1, policy=replace(v1.policy, valid_to=None))
    result = PolicyTemporalResolver().resolve(
        request(datetime(2026, 8, 1, tzinfo=UTC)), (overlapping_v1, v2)
    )
    assert result.outcome is PolicySelectionOutcome.AMBIGUOUS
    assert result.selected_policy is None
    assert {item.version for item in result.candidates} == {1, 2}


def test_unknown_code_is_not_found() -> None:
    query = replace(request(datetime(2026, 8, 1, tzinfo=UTC)), policy_code="OTHER")
    result = PolicyTemporalResolver().resolve(query, versions())
    assert result.outcome is PolicySelectionOutcome.NOT_FOUND
    assert result.reason_codes == (PolicySelectionReason.POLITICA_APLICAVEL_AUSENTE,)


def test_draft_is_not_temporally_eligible() -> None:
    v1, _ = versions()
    draft = replace(v1, policy=replace(v1.policy, status=PolicyStatus.DRAFT))
    result = PolicyTemporalResolver().resolve(request(datetime(2026, 5, 1, tzinfo=UTC)), (draft,))
    assert result.outcome is PolicySelectionOutcome.TEMPORAL_GAP
