"""Checkpoint imutável e verificável da cabeça de uma cadeia de eventos."""

import hashlib
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from packages.core_integrity.event_chain import (
    CANONICAL_SERIALIZATION_VERSION,
    EVENT_CHAIN_PROFILE,
    EVENT_CHAIN_PROFILE_VERSION,
    HASH_ALGORITHM,
    ChainVerificationStatus,
    EventChainEntry,
    EventChainVerifier,
)
from packages.shared_kernel import (
    CanonicalSerializer,
    OrganizationId,
    TypedId,
    UniversalReference,
)
from packages.shared_kernel.temporal import require_utc

CHECKPOINT_PROFILE = "titan-integrity-checkpoint"
CHECKPOINT_PROFILE_VERSION = 1


class CheckpointVerificationStatus(StrEnum):
    VALIDO = "VALIDO"
    INVALIDO = "INVALIDO"
    INDETERMINADO = "INDETERMINADO"


@dataclass(frozen=True, slots=True)
class CheckpointEventReference:
    event_id: TypedId
    sequence: int
    event_hash: bytes

    def __post_init__(self) -> None:
        if self.event_id.entity_type != "domain_event":
            raise ValueError("event_id deve possuir tipo lógico 'domain_event'.")
        if isinstance(self.sequence, bool) or not isinstance(self.sequence, int):
            raise TypeError("sequence deve ser inteiro.")
        if self.sequence < 1:
            raise ValueError("sequence deve ser positiva.")
        if not isinstance(self.event_hash, bytes) or len(self.event_hash) != 32:
            raise ValueError("event_hash deve possuir 32 bytes.")


@dataclass(frozen=True, slots=True)
class IntegrityCheckpoint:
    checkpoint_id: TypedId
    organization_id: OrganizationId
    aggregate_reference: UniversalReference
    first_sequence: int
    last_sequence: int
    record_count: int
    event_references: tuple[CheckpointEventReference, ...]
    initial_hash: bytes
    final_hash: bytes
    hash_algorithm: str
    event_chain_profile: str
    event_chain_profile_version: int
    checkpoint_profile: str
    checkpoint_profile_version: int
    canonical_serialization_version: str
    observed_at: datetime
    producer_reference: UniversalReference
    correlation_id: TypedId
    causation_id: TypedId | None
    checkpoint_canonical_bytes: bytes
    checkpoint_digest: bytes


@dataclass(frozen=True, slots=True)
class CheckpointVerificationReport:
    status: CheckpointVerificationStatus
    reason_code: str
    verified_count: int
    divergence_position: int | None


def checkpoint_reference(entry: EventChainEntry) -> CheckpointEventReference:
    return CheckpointEventReference(
        event_id=entry.event.event_id,
        sequence=entry.event.aggregate_version,
        event_hash=entry.current_hash,
    )


def build_integrity_checkpoint(
    *,
    checkpoint_id: TypedId,
    entries: tuple[EventChainEntry, ...],
    observed_at: datetime,
    producer_reference: UniversalReference,
    correlation_id: TypedId,
    causation_id: TypedId | None,
) -> IntegrityCheckpoint:
    _validate_identifiers(checkpoint_id, correlation_id, causation_id)
    require_utc(observed_at, field_name="observed_at")
    chain_report = EventChainVerifier().verify(entries)
    if chain_report.status is not ChainVerificationStatus.VALIDA:
        raise ValueError(f"A cadeia não pode ser ancorada: {chain_report.reason_code}.")
    first_event = entries[0].event
    aggregate = first_event.aggregate_reference
    if any(
        entry.event.organization_id != first_event.organization_id
        or entry.event.aggregate_reference != aggregate
        for entry in entries
    ):
        raise ValueError("Checkpoint não pode combinar Organizations ou agregados.")
    references = tuple(checkpoint_reference(entry) for entry in entries)
    canonical_bytes = _checkpoint_bytes(
        checkpoint_id=checkpoint_id,
        organization_id=first_event.organization_id,
        aggregate_reference=aggregate,
        event_references=references,
        observed_at=observed_at,
        producer_reference=producer_reference,
        correlation_id=correlation_id,
        causation_id=causation_id,
    )
    return IntegrityCheckpoint(
        checkpoint_id=checkpoint_id,
        organization_id=first_event.organization_id,
        aggregate_reference=aggregate,
        first_sequence=1,
        last_sequence=len(entries),
        record_count=len(entries),
        event_references=references,
        initial_hash=entries[0].current_hash,
        final_hash=entries[-1].current_hash,
        hash_algorithm=HASH_ALGORITHM,
        event_chain_profile=EVENT_CHAIN_PROFILE,
        event_chain_profile_version=EVENT_CHAIN_PROFILE_VERSION,
        checkpoint_profile=CHECKPOINT_PROFILE,
        checkpoint_profile_version=CHECKPOINT_PROFILE_VERSION,
        canonical_serialization_version=CANONICAL_SERIALIZATION_VERSION,
        observed_at=observed_at,
        producer_reference=producer_reference,
        correlation_id=correlation_id,
        causation_id=causation_id,
        checkpoint_canonical_bytes=canonical_bytes,
        checkpoint_digest=hashlib.sha256(canonical_bytes).digest(),
    )


@dataclass(frozen=True, slots=True)
class IntegrityCheckpointVerifier:
    def verify(
        self,
        checkpoint: IntegrityCheckpoint,
        entries: tuple[EventChainEntry, ...],
    ) -> CheckpointVerificationReport:
        if not isinstance(checkpoint, IntegrityCheckpoint):
            raise TypeError("checkpoint deve ser IntegrityCheckpoint.")
        if not _supported(checkpoint):
            return _report(CheckpointVerificationStatus.INDETERMINADO, "PERFIL_NAO_SUPORTADO")
        chain_report = EventChainVerifier().verify(entries)
        if chain_report.status is ChainVerificationStatus.INDETERMINADA:
            return _report(CheckpointVerificationStatus.INDETERMINADO, chain_report.reason_code)
        if chain_report.status is ChainVerificationStatus.INVALIDA:
            return CheckpointVerificationReport(
                CheckpointVerificationStatus.INVALIDO,
                chain_report.reason_code,
                chain_report.verified_count,
                chain_report.divergence_position,
            )
        if (
            checkpoint.organization_id != entries[0].event.organization_id
            or checkpoint.aggregate_reference != entries[0].event.aggregate_reference
        ):
            return _report(CheckpointVerificationStatus.INVALIDO, "ESCOPO_DIVERGENTE")
        references = tuple(checkpoint_reference(entry) for entry in entries)
        if references != checkpoint.event_references:
            return _first_reference_divergence(checkpoint.event_references, references)
        if checkpoint.record_count != len(entries):
            return _report(CheckpointVerificationStatus.INVALIDO, "CONTAGEM_DIVERGENTE")
        if checkpoint.first_sequence != 1 or checkpoint.last_sequence != len(entries):
            return _report(CheckpointVerificationStatus.INVALIDO, "DELIMITADORES_DIVERGENTES")
        if checkpoint.initial_hash != entries[0].current_hash:
            return _report(CheckpointVerificationStatus.INVALIDO, "HASH_INICIAL_DIVERGENTE")
        if checkpoint.final_hash != entries[-1].current_hash:
            return _report(CheckpointVerificationStatus.INVALIDO, "HASH_FINAL_DIVERGENTE")
        canonical_bytes = _checkpoint_bytes(
            checkpoint_id=checkpoint.checkpoint_id,
            organization_id=checkpoint.organization_id,
            aggregate_reference=checkpoint.aggregate_reference,
            event_references=checkpoint.event_references,
            observed_at=checkpoint.observed_at,
            producer_reference=checkpoint.producer_reference,
            correlation_id=checkpoint.correlation_id,
            causation_id=checkpoint.causation_id,
        )
        if canonical_bytes != checkpoint.checkpoint_canonical_bytes:
            return _report(CheckpointVerificationStatus.INVALIDO, "CHECKPOINT_CANONICO_DIVERGENTE")
        if hashlib.sha256(canonical_bytes).digest() != checkpoint.checkpoint_digest:
            return _report(CheckpointVerificationStatus.INVALIDO, "DIGEST_DIVERGENTE")
        return CheckpointVerificationReport(
            CheckpointVerificationStatus.VALIDO,
            "CHECKPOINT_INTEGRO",
            len(entries),
            None,
        )


def _checkpoint_bytes(
    *,
    checkpoint_id: TypedId,
    organization_id: OrganizationId,
    aggregate_reference: UniversalReference,
    event_references: tuple[CheckpointEventReference, ...],
    observed_at: datetime,
    producer_reference: UniversalReference,
    correlation_id: TypedId,
    causation_id: TypedId | None,
) -> bytes:
    return CanonicalSerializer().serialize(
        {
            "aggregate_contract_version": aggregate_reference.contract_version,
            "aggregate_id": str(aggregate_reference.target_id),
            "canonical_serialization_version": CANONICAL_SERIALIZATION_VERSION,
            "causation_id": None if causation_id is None else str(causation_id),
            "checkpoint_id": str(checkpoint_id),
            "checkpoint_profile": CHECKPOINT_PROFILE,
            "checkpoint_profile_version": CHECKPOINT_PROFILE_VERSION,
            "correlation_id": str(correlation_id),
            "event_chain_profile": EVENT_CHAIN_PROFILE,
            "event_chain_profile_version": EVENT_CHAIN_PROFILE_VERSION,
            "event_references": [
                {
                    "event_hash_hex": reference.event_hash.hex(),
                    "event_id": str(reference.event_id),
                    "sequence": reference.sequence,
                }
                for reference in event_references
            ],
            "first_sequence": 1,
            "hash_algorithm": HASH_ALGORITHM,
            "initial_hash_hex": event_references[0].event_hash.hex(),
            "last_sequence": len(event_references),
            "observed_at": observed_at,
            "organization_id": str(organization_id),
            "producer_contract_version": producer_reference.contract_version,
            "producer_id": str(producer_reference.target_id),
            "producer_organization_id": (
                None
                if producer_reference.organization_id is None
                else str(producer_reference.organization_id)
            ),
            "record_count": len(event_references),
            "final_hash_hex": event_references[-1].event_hash.hex(),
        }
    )


def _validate_identifiers(
    checkpoint_id: TypedId, correlation_id: TypedId, causation_id: TypedId | None
) -> None:
    if checkpoint_id.entity_type != "integrity_checkpoint":
        raise ValueError("checkpoint_id deve possuir tipo lógico 'integrity_checkpoint'.")
    if correlation_id.entity_type != "correlation":
        raise ValueError("correlation_id deve possuir tipo lógico 'correlation'.")
    if causation_id is not None and causation_id.entity_type != "domain_event":
        raise ValueError("causation_id deve possuir tipo lógico 'domain_event'.")


def _supported(checkpoint: IntegrityCheckpoint) -> bool:
    return (
        checkpoint.hash_algorithm == HASH_ALGORITHM
        and checkpoint.event_chain_profile == EVENT_CHAIN_PROFILE
        and checkpoint.event_chain_profile_version == EVENT_CHAIN_PROFILE_VERSION
        and checkpoint.checkpoint_profile == CHECKPOINT_PROFILE
        and checkpoint.checkpoint_profile_version == CHECKPOINT_PROFILE_VERSION
        and checkpoint.canonical_serialization_version == CANONICAL_SERIALIZATION_VERSION
    )


def _report(status: CheckpointVerificationStatus, reason_code: str) -> CheckpointVerificationReport:
    return CheckpointVerificationReport(status, reason_code, 0, None)


def _first_reference_divergence(
    expected: tuple[CheckpointEventReference, ...],
    actual: tuple[CheckpointEventReference, ...],
) -> CheckpointVerificationReport:
    common = min(len(expected), len(actual))
    for index in range(common):
        if expected[index] != actual[index]:
            return CheckpointVerificationReport(
                CheckpointVerificationStatus.INVALIDO,
                "CONJUNTO_COBERTO_DIVERGENTE",
                index,
                index + 1,
            )
    return CheckpointVerificationReport(
        CheckpointVerificationStatus.INVALIDO,
        "CONJUNTO_COBERTO_DIVERGENTE",
        common,
        common + 1,
    )
