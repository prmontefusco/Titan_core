"""Cadeia de hashes reproduzível sem banco, segredo ou provider externo."""

import base64
import hashlib
from dataclasses import dataclass
from enum import StrEnum

from packages.core_domain import DomainEvent
from packages.shared_kernel import CanonicalSerializer, UniversalReference
from packages.shared_kernel.serialization import CanonicalValue

HASH_ALGORITHM = "SHA-256"
EVENT_CHAIN_PROFILE = "titan-event-chain"
EVENT_CHAIN_PROFILE_VERSION = 1
CANONICAL_SERIALIZATION_VERSION = CanonicalSerializer.version


class ChainVerificationStatus(StrEnum):
    VALIDA = "VALIDA"
    INVALIDA = "INVALIDA"
    INDETERMINADA = "INDETERMINADA"


@dataclass(frozen=True, slots=True)
class EventChainEntry:
    event: DomainEvent
    previous_hash: bytes | None
    current_hash: bytes
    event_canonical_bytes: bytes
    hash_algorithm: str = HASH_ALGORITHM
    hash_profile: str = EVENT_CHAIN_PROFILE
    hash_profile_version: int = EVENT_CHAIN_PROFILE_VERSION
    canonical_serialization_version: str = CANONICAL_SERIALIZATION_VERSION


@dataclass(frozen=True, slots=True)
class ChainVerificationReport:
    status: ChainVerificationStatus
    reason_code: str
    verified_count: int
    divergence_position: int | None


def build_event_chain_entry(event: DomainEvent, previous_hash: bytes | None) -> EventChainEntry:
    if not isinstance(event, DomainEvent):
        raise TypeError("event deve ser um DomainEvent.")
    _validate_hash(previous_hash, field_name="previous_hash", allow_none=True)
    event_bytes = _canonical_event_bytes(event)
    current_hash = _calculate_hash(event_bytes, previous_hash)
    return EventChainEntry(
        event=event,
        previous_hash=previous_hash,
        current_hash=current_hash,
        event_canonical_bytes=event_bytes,
    )


@dataclass(frozen=True, slots=True)
class EventChainVerifier:
    """Verifica uma cadeia fornecida sem consultar estado mutável do Titan."""

    def verify(self, entries: tuple[EventChainEntry, ...]) -> ChainVerificationReport:
        if not isinstance(entries, tuple):
            raise TypeError("entries deve ser uma tupla.")
        if not entries:
            return ChainVerificationReport(
                ChainVerificationStatus.INDETERMINADA,
                "CADEIA_VAZIA",
                0,
                None,
            )

        expected_previous: bytes | None = None
        for position, entry in enumerate(entries, start=1):
            if not isinstance(entry, EventChainEntry):
                raise TypeError("Cada item deve ser EventChainEntry.")
            if not _supported_profile(entry):
                return ChainVerificationReport(
                    ChainVerificationStatus.INDETERMINADA,
                    "PERFIL_NAO_SUPORTADO",
                    position - 1,
                    position,
                )
            if entry.event.aggregate_version != position:
                return _invalid("SEQUENCIA_INVALIDA", position)
            if entry.previous_hash != expected_previous:
                return _invalid("HASH_ANTERIOR_DIVERGENTE", position)
            calculated_event_bytes = _canonical_event_bytes(entry.event)
            if calculated_event_bytes != entry.event_canonical_bytes:
                return _invalid("EVENTO_CANONICO_DIVERGENTE", position)
            calculated_hash = _calculate_hash(calculated_event_bytes, expected_previous)
            if calculated_hash != entry.current_hash:
                return _invalid("HASH_ATUAL_DIVERGENTE", position)
            expected_previous = entry.current_hash

        return ChainVerificationReport(
            ChainVerificationStatus.VALIDA,
            "CADEIA_INTEGRA",
            len(entries),
            None,
        )


def _invalid(reason_code: str, position: int) -> ChainVerificationReport:
    return ChainVerificationReport(
        ChainVerificationStatus.INVALIDA,
        reason_code,
        position - 1,
        position,
    )


def _supported_profile(entry: EventChainEntry) -> bool:
    return (
        entry.hash_algorithm == HASH_ALGORITHM
        and entry.hash_profile == EVENT_CHAIN_PROFILE
        and entry.hash_profile_version == EVENT_CHAIN_PROFILE_VERSION
        and entry.canonical_serialization_version == CANONICAL_SERIALIZATION_VERSION
    )


def _calculate_hash(event_bytes: bytes, previous_hash: bytes | None) -> bytes:
    serializer = CanonicalSerializer()
    protected_bytes = serializer.serialize(
        {
            "canonical_serialization_version": CANONICAL_SERIALIZATION_VERSION,
            "event_canonical_bytes_base64": base64.b64encode(event_bytes).decode("ascii"),
            "hash_algorithm": HASH_ALGORITHM,
            "hash_profile": EVENT_CHAIN_PROFILE,
            "hash_profile_version": EVENT_CHAIN_PROFILE_VERSION,
            "previous_hash_hex": None if previous_hash is None else previous_hash.hex(),
        }
    )
    return hashlib.sha256(protected_bytes).digest()


def _canonical_event_bytes(event: DomainEvent) -> bytes:
    serializer = CanonicalSerializer()
    aggregate = event.aggregate_reference
    return serializer.serialize(
        {
            "actor": _reference_value(event.actor_reference),
            "aggregate": _reference_value(aggregate),
            "aggregate_version": event.aggregate_version,
            "causation_id": None if event.causation_id is None else str(event.causation_id),
            "correlation_id": str(event.correlation_id),
            "event_id": str(event.event_id),
            "event_type": event.event_type,
            "event_version": event.event_version,
            "occurred_at": event.timestamps.occurred_at,
            "organization_id": str(event.organization_id),
            "payload_canonical_bytes_base64": base64.b64encode(
                event.payload.canonical_bytes
            ).decode("ascii"),
            "payload_schema": event.payload.schema,
            "payload_version": event.payload.version,
            "recorded_at": event.timestamps.recorded_at,
            "source": _reference_value(event.source_reference),
        }
    )


def _reference_value(reference: object) -> dict[str, CanonicalValue]:
    if not isinstance(reference, UniversalReference):
        raise TypeError("reference deve ser UniversalReference.")
    return {
        "contract_version": reference.contract_version,
        "organization_id": (
            None if reference.organization_id is None else str(reference.organization_id)
        ),
        "target_id": str(reference.target_id),
    }


def _validate_hash(value: bytes | None, *, field_name: str, allow_none: bool) -> None:
    if value is None and allow_none:
        return
    if not isinstance(value, bytes):
        raise TypeError(f"{field_name} deve ser bytes.")
    if len(value) != hashlib.sha256().digest_size:
        raise ValueError(f"{field_name} deve possuir 32 bytes para SHA-256.")
