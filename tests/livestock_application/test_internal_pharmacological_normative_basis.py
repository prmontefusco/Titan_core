from datetime import UTC, datetime, timedelta
from uuid import uuid4

from packages.livestock_application.eligibility import (
    ELIGIBILITY_PURPOSE,
    InternalPharmacologicalNormativeBasisSnapshotProvider,
    build_eligibility_policy,
    build_eligibility_rule,
)
from packages.shared_kernel import OrganizationId

NOW = datetime(2026, 8, 13, 12, tzinfo=UTC)


def test_internal_baseline_preserves_temporal_snapshot_for_pharmacological_policy() -> None:
    organization_id = OrganizationId(uuid4())
    policy = build_eligibility_policy(organization_id, published_at=NOW - timedelta(days=1))
    rule = build_eligibility_rule(policy.policy_id, organization_id)

    snapshot = InternalPharmacologicalNormativeBasisSnapshotProvider().select(
        policy=policy,
        rules=(rule,),
        purpose=ELIGIBILITY_PURPOSE,
        reference_time=NOW,
        knowledge_cutoff=NOW,
    )

    assert snapshot is not None
    assert snapshot.policy_id == policy.policy_id
    assert snapshot.reference_time == NOW
    assert snapshot.knowledge_cutoff == NOW
    assert snapshot.references[0].source_classification.value == "internal_test"
    assert "RECOGNITION_BOUNDARY:INTERNAL_ONLY" in snapshot.limitations


def test_internal_baseline_refuses_policy_unknown_at_the_knowledge_cutoff() -> None:
    organization_id = OrganizationId(uuid4())
    policy = build_eligibility_policy(organization_id, published_at=NOW + timedelta(seconds=1))
    rule = build_eligibility_rule(policy.policy_id, organization_id)

    snapshot = InternalPharmacologicalNormativeBasisSnapshotProvider().select(
        policy=policy,
        rules=(rule,),
        purpose=ELIGIBILITY_PURPOSE,
        reference_time=NOW,
        knowledge_cutoff=NOW,
    )

    assert snapshot is None
