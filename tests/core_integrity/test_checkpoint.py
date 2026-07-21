from dataclasses import replace
from datetime import UTC, datetime

from packages.core_integrity import (
    CheckpointVerificationStatus,
    EventChainEntry,
    IntegrityCheckpoint,
    IntegrityCheckpointVerifier,
    build_event_chain_entry,
    build_integrity_checkpoint,
)
from packages.shared_kernel import TypedId
from tests.core_domain.test_domain_event import reference, valid_event


def _chain() -> tuple[EventChainEntry, EventChainEntry]:
    first_event = replace(valid_event(), aggregate_version=1)
    second_event = replace(
        valid_event(),
        organization_id=first_event.organization_id,
        aggregate_reference=first_event.aggregate_reference,
        aggregate_version=2,
    )
    first = build_event_chain_entry(first_event, None)
    return first, build_event_chain_entry(second_event, first.current_hash)


def _checkpoint() -> tuple[tuple[EventChainEntry, EventChainEntry], IntegrityCheckpoint]:
    entries = _chain()
    return entries, build_integrity_checkpoint(
        checkpoint_id=TypedId.new("integrity_checkpoint"),
        entries=entries,
        observed_at=datetime(2026, 7, 21, 18, 0, tzinfo=UTC),
        producer_reference=reference("service_identity", entries[0].event.organization_id),
        correlation_id=TypedId.new("correlation"),
        causation_id=entries[-1].event.event_id,
    )


def test_checkpoint_is_deterministic_and_verifiable_without_database() -> None:
    entries, checkpoint = _checkpoint()

    report = IntegrityCheckpointVerifier().verify(checkpoint, entries)

    assert report.status is CheckpointVerificationStatus.VALIDO
    assert checkpoint.record_count == 2
    assert checkpoint.first_sequence == 1
    assert checkpoint.last_sequence == 2
    assert tuple(item.event_id for item in checkpoint.event_references) == tuple(
        item.event.event_id for item in entries
    )


def test_omitted_event_is_detected_as_covered_set_divergence() -> None:
    entries, checkpoint = _checkpoint()

    report = IntegrityCheckpointVerifier().verify(checkpoint, entries[:1])

    assert report.status is CheckpointVerificationStatus.INVALIDO
    assert report.reason_code == "CONJUNTO_COBERTO_DIVERGENTE"
    assert report.divergence_position == 2


def test_modified_checkpoint_digest_is_detected() -> None:
    entries, checkpoint = _checkpoint()

    report = IntegrityCheckpointVerifier().verify(
        replace(checkpoint, checkpoint_digest=b"\x00" * 32), entries
    )

    assert report.status is CheckpointVerificationStatus.INVALIDO
    assert report.reason_code == "DIGEST_DIVERGENTE"


def test_unsupported_checkpoint_profile_is_indeterminate() -> None:
    entries, checkpoint = _checkpoint()

    report = IntegrityCheckpointVerifier().verify(
        replace(checkpoint, checkpoint_profile_version=2), entries
    )

    assert report.status is CheckpointVerificationStatus.INDETERMINADO
    assert report.reason_code == "PERFIL_NAO_SUPORTADO"


def test_checkpoint_cannot_claim_another_organization_scope() -> None:
    entries, checkpoint = _checkpoint()
    other_event = valid_event()

    report = IntegrityCheckpointVerifier().verify(
        replace(checkpoint, organization_id=other_event.organization_id), entries
    )

    assert report.status is CheckpointVerificationStatus.INVALIDO
    assert report.reason_code == "ESCOPO_DIVERGENTE"
