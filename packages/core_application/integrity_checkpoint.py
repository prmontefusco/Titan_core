"""Coordenação da criação imutável de IntegrityCheckpoint."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from packages.core_integrity import (
    EventChainEntry,
    IntegrityCheckpoint,
    build_integrity_checkpoint,
)
from packages.shared_kernel import TypedId, UniversalReference


class IntegrityCheckpointWriter(Protocol):
    def add(self, checkpoint: IntegrityCheckpoint) -> None: ...


@dataclass(frozen=True, slots=True)
class IntegrityCheckpointService:
    writer: IntegrityCheckpointWriter

    def create(
        self,
        *,
        checkpoint_id: TypedId,
        entries: tuple[EventChainEntry, ...],
        observed_at: datetime,
        producer_reference: UniversalReference,
        correlation_id: TypedId,
        causation_id: TypedId | None,
    ) -> IntegrityCheckpoint:
        checkpoint = build_integrity_checkpoint(
            checkpoint_id=checkpoint_id,
            entries=entries,
            observed_at=observed_at,
            producer_reference=producer_reference,
            correlation_id=correlation_id,
            causation_id=causation_id,
        )
        self.writer.add(checkpoint)
        return checkpoint
