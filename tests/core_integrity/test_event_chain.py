from dataclasses import replace

from packages.core_domain import CanonicalPayload, DomainEvent
from packages.core_integrity import (
    ChainVerificationStatus,
    EventChainVerifier,
    build_event_chain_entry,
)
from tests.core_domain.test_domain_event import valid_event


def _event_with_version(version: int) -> DomainEvent:
    event = valid_event()
    return replace(event, aggregate_version=version)


def test_verifies_deterministic_chain_without_external_state() -> None:
    first_event = _event_with_version(1)
    first = build_event_chain_entry(first_event, None)
    repeated = build_event_chain_entry(first_event, None)
    second = build_event_chain_entry(_event_with_version(2), first.current_hash)

    report = EventChainVerifier().verify((first, second))

    assert report.status is ChainVerificationStatus.VALIDA
    assert report.reason_code == "CADEIA_INTEGRA"
    assert report.verified_count == 2
    assert repeated.event_canonical_bytes == first.event_canonical_bytes
    assert repeated.current_hash == first.current_hash


def test_detects_exact_tampered_event_position() -> None:
    first = build_event_chain_entry(_event_with_version(1), None)
    second = build_event_chain_entry(_event_with_version(2), first.current_hash)
    tampered_event = replace(
        second.event,
        payload=CanonicalPayload.from_mapping(
            schema=second.event.payload.schema,
            version=second.event.payload.version,
            value={"alterado": True},
        ),
    )

    report = EventChainVerifier().verify((first, replace(second, event=tampered_event)))

    assert report.status is ChainVerificationStatus.INVALIDA
    assert report.reason_code == "EVENTO_CANONICO_DIVERGENTE"
    assert report.divergence_position == 2


def test_unsupported_profile_is_indeterminate_not_valid() -> None:
    entry = build_event_chain_entry(_event_with_version(1), None)

    report = EventChainVerifier().verify((replace(entry, hash_algorithm="SHA-1"),))

    assert report.status is ChainVerificationStatus.INDETERMINADA
    assert report.reason_code == "PERFIL_NAO_SUPORTADO"
