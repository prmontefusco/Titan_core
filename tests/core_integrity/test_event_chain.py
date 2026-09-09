from dataclasses import replace
from datetime import UTC, datetime

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from packages.core_domain import CanonicalPayload, DomainEvent
from packages.core_integrity import (
    EVENT_INTEGRITY_SIGNATURE_ALGORITHM,
    EVENT_INTEGRITY_SIGNATURE_PROFILE,
    EVENT_INTEGRITY_SIGNATURE_PROFILE_VERSION,
    ChainVerificationStatus,
    EventChainEntry,
    EventChainVerifier,
    build_event_chain_entry,
    build_event_integrity_signature_payload,
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


def _signed_entry(entry: EventChainEntry) -> EventChainEntry:
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    unsigned = replace(
        entry,
        signature_algorithm=EVENT_INTEGRITY_SIGNATURE_ALGORITHM,
        signature_profile=EVENT_INTEGRITY_SIGNATURE_PROFILE,
        signature_profile_version=EVENT_INTEGRITY_SIGNATURE_PROFILE_VERSION,
        signature_key_id="test-key",
        signature_public_key=public_key,
        signature_signed_at=datetime(2026, 9, 9, 12, tzinfo=UTC),
    )
    return replace(
        unsigned,
        signature_bytes=private_key.sign(build_event_integrity_signature_payload(unsigned)),
    )


def test_verifies_ed25519_signature_when_present() -> None:
    first = _signed_entry(build_event_chain_entry(_event_with_version(1), None))

    report = EventChainVerifier().verify((first,))

    assert report.status is ChainVerificationStatus.VALIDA
    assert report.reason_code == "CADEIA_INTEGRA"


def test_detects_tampered_ed25519_signature_metadata() -> None:
    first = _signed_entry(build_event_chain_entry(_event_with_version(1), None))

    report = EventChainVerifier().verify((replace(first, signature_key_id="other-key"),))

    assert report.status is ChainVerificationStatus.INVALIDA
    assert report.reason_code == "ASSINATURA_DE_INTEGRIDADE_INVALIDA"


def test_detects_tampered_ed25519_signature_bytes() -> None:
    first = _signed_entry(build_event_chain_entry(_event_with_version(1), None))
    assert first.signature_bytes is not None

    tampered_signature = bytes([first.signature_bytes[0] ^ 1]) + first.signature_bytes[1:]
    report = EventChainVerifier().verify((replace(first, signature_bytes=tampered_signature),))

    assert report.status is ChainVerificationStatus.INVALIDA
    assert report.reason_code == "ASSINATURA_DE_INTEGRIDADE_INVALIDA"


def test_incomplete_ed25519_signature_is_indeterminate() -> None:
    first = _signed_entry(build_event_chain_entry(_event_with_version(1), None))

    report = EventChainVerifier().verify((replace(first, signature_public_key=None),))

    assert report.status is ChainVerificationStatus.INDETERMINADA
    assert report.reason_code == "ASSINATURA_DE_INTEGRIDADE_INDETERMINADA"
