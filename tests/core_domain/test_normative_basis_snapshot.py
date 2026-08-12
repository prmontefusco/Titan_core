"""Provas do contrato normativo tipado do NEXT-02/Corte 2."""

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from packages.core_domain.evaluation import compute_context_hash
from packages.core_domain.normative import (
    NormativeBasisSnapshot,
    NormativeReferenceSnapshot,
    NormativeSourceClassification,
)
from packages.shared_kernel import TypedId


def _reference(
    code: str = "TEST-INSTRUMENT-A",
    provision: str | None = "section-1",
    digest: str = "a" * 64,
) -> NormativeReferenceSnapshot:
    return NormativeReferenceSnapshot(
        instrument_code=code,
        instrument_version="1",
        provision=provision,
        content_digest=digest,
        digest_algorithm="sha256",
        source_classification=NormativeSourceClassification.INTERNAL_TEST,
    )


def _snapshot(**changes: object) -> NormativeBasisSnapshot:
    values: dict[str, object] = {
        "schema_version": 1,
        "normative_basis_id": TypedId.new("normative_basis"),
        "normative_basis_code": "TEST-BASIS-A",
        "normative_basis_version": 1,
        "policy_id": TypedId.new("policy"),
        "policy_code": "MARKET_TEST_A",
        "policy_version": 1,
        "rule_versions": (("SANITARY-RULE", 1), ("IDENTITY-RULE", 1)),
        "purpose": "MARKET_ELIGIBILITY",
        "jurisdiction": "TEST-JURISDICTION",
        "intended_use": "INTERNAL_TEST_ONLY",
        "reference_time": datetime(2026, 5, 1, tzinfo=UTC),
        "knowledge_cutoff": datetime(2026, 5, 1, tzinfo=UTC),
        "approved_by": "actor:test-reviewer",
        "approval_authority": "INTERNAL_TEST_AUTHORITY",
        "approved_at": datetime(2025, 12, 1, tzinfo=UTC),
        "references": (_reference("B"), _reference("A")),
        "applicability_conditions": ("bovine", "identified"),
        "exceptions": ("exception-b", "exception-a"),
        "conflicts": (),
        "gaps": (),
        "limitations": ("not-an-official-market-decision",),
    }
    values.update(changes)
    return NormativeBasisSnapshot(**values)  # type: ignore[arg-type]


def test_snapshot_is_typed_versioned_and_computes_its_digest() -> None:
    snapshot = _snapshot()

    assert snapshot.schema_version == 1
    assert len(snapshot.snapshot_digest) == 64
    assert snapshot.compute_digest() == snapshot.snapshot_digest


def test_digest_is_stable_when_semantically_unordered_collections_are_reordered() -> None:
    original = _snapshot()
    reordered = replace(
        original,
        references=tuple(reversed(original.references)),
        rule_versions=tuple(reversed(original.rule_versions)),
        applicability_conditions=tuple(reversed(original.applicability_conditions)),
        exceptions=tuple(reversed(original.exceptions)),
        snapshot_digest="",
    )

    assert reordered.snapshot_digest == original.snapshot_digest


def test_changed_reference_provision_changes_snapshot_and_context_identity() -> None:
    original = _snapshot()
    changed = replace(
        original,
        references=(_reference("B", provision="section-2"), _reference("A")),
        snapshot_digest="",
    )
    assert changed.snapshot_digest != original.snapshot_digest
    assert compute_context_hash(
        policy_id=original.policy_id,
        policy_version=original.policy_version,
        purpose=original.purpose,
        engine_version=1,
        rule_versions=original.rule_versions,
        normative_basis_snapshot_digest=changed.snapshot_digest,
    ) != compute_context_hash(
        policy_id=original.policy_id,
        policy_version=original.policy_version,
        purpose=original.purpose,
        engine_version=1,
        rule_versions=original.rule_versions,
        normative_basis_snapshot_digest=original.snapshot_digest,
    )


def test_same_snapshot_reproduces_same_context_hash() -> None:
    original = _snapshot()
    reconstructed = replace(original, snapshot_digest="")

    first = compute_context_hash(
        policy_id=original.policy_id,
        policy_version=original.policy_version,
        purpose=original.purpose,
        engine_version=1,
        rule_versions=original.rule_versions,
        normative_basis_snapshot_digest=original.snapshot_digest,
    )
    second = compute_context_hash(
        policy_id=reconstructed.policy_id,
        policy_version=reconstructed.policy_version,
        purpose=reconstructed.purpose,
        engine_version=1,
        rule_versions=reconstructed.rule_versions,
        normative_basis_snapshot_digest=reconstructed.snapshot_digest,
    )

    assert first == second


def test_legacy_context_without_normative_snapshot_remains_supported() -> None:
    snapshot = _snapshot()

    legacy = compute_context_hash(
        policy_id=snapshot.policy_id,
        policy_version=1,
        purpose=snapshot.purpose,
        engine_version=1,
        rule_versions=snapshot.rule_versions,
    )
    explicit = compute_context_hash(
        policy_id=snapshot.policy_id,
        policy_version=1,
        purpose=snapshot.purpose,
        engine_version=1,
        rule_versions=snapshot.rule_versions,
        normative_basis_snapshot_digest=snapshot.snapshot_digest,
    )

    assert legacy != explicit


def test_snapshot_rejects_digest_that_does_not_match_content() -> None:
    with pytest.raises(ValueError, match="não corresponde"):
        _snapshot(snapshot_digest="digest-adulterado")
